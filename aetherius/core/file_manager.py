"""
Aetherius文件管理系统
==================

提供安全的文件管理功能，支持Web组件的文件操作需求
"""

import hashlib
import logging
import mimetypes
import shutil
import tempfile
import zipfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """文件信息数据结构"""

    name: str
    path: str
    size: int
    modified: datetime
    created: datetime
    is_directory: bool
    mime_type: Optional[str] = None
    permissions: Optional[str] = None
    owner: Optional[str] = None
    hash_md5: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        # 转换datetime为ISO格式字符串
        data["modified"] = self.modified.isoformat() if self.modified else None
        data["created"] = self.created.isoformat() if self.created else None
        return data


@dataclass
class UploadInfo:
    """文件上传信息"""

    filename: str
    size: int
    mime_type: str
    upload_time: datetime
    hash_md5: str
    destination: str

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        data["upload_time"] = self.upload_time.isoformat()
        return data


class FileManager:
    """文件管理器"""

    # 允许的文件类型（可配置）
    ALLOWED_EXTENSIONS = {
        "text": [".txt", ".md", ".yml", ".yaml", ".json", ".xml", ".csv"],
        "config": [".conf", ".cfg", ".ini", ".properties"],
        "log": [".log"],
        "image": [".png", ".jpg", ".jpeg", ".gif", ".svg"],
        "document": [".pdf", ".docx", ".xlsx"],
        "archive": [".zip", ".tar", ".gz"],
        "minecraft": [".jar", ".mcmeta"],
    }

    # 禁止的文件类型
    FORBIDDEN_EXTENSIONS = [".exe", ".bat", ".cmd", ".sh", ".ps1", ".vbs", ".scr"]

    # 最大文件大小（字节）
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

    def __init__(self, base_directory: Optional[str | Path] = None):
        """
        初始化文件管理器

        Args:
            base_directory: 基础目录，所有操作限制在此目录内
        """
        self.base_dir = Path(base_directory) if base_directory else Path.cwd()
        self.base_dir = self.base_dir.resolve()  # 获取绝对路径

        # 确保基础目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # 安全设置
        self._safe_mode = True
        self._allowed_extensions = set()
        for ext_list in self.ALLOWED_EXTENSIONS.values():
            self._allowed_extensions.update(ext_list)

        # 上传历史
        self._upload_history: list[UploadInfo] = []
        self._max_history = 1000

        logger.info(f"File manager initialized with base directory: {self.base_dir}")

    def _validate_path(self, path: Union[str, Path]) -> Path:
        """
        验证路径安全性

        Args:
            path: 要验证的路径

        Returns:
            验证后的绝对路径

        Raises:
            ValueError: 路径不安全时抛出
        """
        if isinstance(path, str):
            path = Path(path)

        # 转换为绝对路径
        if not path.is_absolute():
            path = self.base_dir / path
        else:
            path = path.resolve()

        # 检查是否在基础目录内
        try:
            path.relative_to(self.base_dir)
        except ValueError:
            raise ValueError(f"Path {path} is outside base directory {self.base_dir}")

        return path

    def _check_file_extension(
        self, filename: str, allowed_types: Optional[list[str]] = None
    ) -> bool:
        """
        检查文件扩展名是否允许

        Args:
            filename: 文件名
            allowed_types: 允许的文件类型列表

        Returns:
            是否允许
        """
        if not self._safe_mode:
            return True

        ext = Path(filename).suffix.lower()

        # 检查禁止的扩展名
        if ext in self.FORBIDDEN_EXTENSIONS:
            return False

        # 如果指定了允许的类型
        if allowed_types:
            allowed_exts = set()
            for file_type in allowed_types:
                allowed_exts.update(self.ALLOWED_EXTENSIONS.get(file_type, []))
            return ext in allowed_exts

        # 默认检查所有允许的扩展名
        return ext in self._allowed_extensions

    def _calculate_md5(self, file_path: Path) -> str:
        """
        计算文件MD5哈希值

        Args:
            file_path: 文件路径

        Returns:
            MD5哈希值
        """
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def get_file_info(self, path: Union[str, Path]) -> Optional[FileInfo]:
        """
        获取文件或目录信息

        Args:
            path: 文件路径

        Returns:
            文件信息对象或None
        """
        try:
            file_path = self._validate_path(path)

            if not file_path.exists():
                return None

            stat = file_path.stat()

            # 获取MIME类型
            mime_type = None
            if file_path.is_file():
                mime_type, _ = mimetypes.guess_type(str(file_path))

            # 获取权限
            permissions = oct(stat.st_mode)[-3:]

            # 计算MD5（仅对小文件）
            hash_md5 = None
            if file_path.is_file() and stat.st_size < 10 * 1024 * 1024:  # 10MB以下
                try:
                    hash_md5 = self._calculate_md5(file_path)
                except Exception as e:
                    logger.warning(f"Failed to calculate MD5 for {file_path}: {e}")

            return FileInfo(
                name=file_path.name,
                path=str(file_path.relative_to(self.base_dir)),
                size=stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime),
                created=datetime.fromtimestamp(stat.st_ctime),
                is_directory=file_path.is_dir(),
                mime_type=mime_type,
                permissions=permissions,
                hash_md5=hash_md5,
            )

        except Exception as e:
            logger.error(f"Error getting file info for {path}: {e}")
            return None

    def list_directory(
        self,
        path: Union[str, Path] = "",
        recursive: bool = False,
        include_hidden: bool = False,
    ) -> list[FileInfo]:
        """
        列出目录内容

        Args:
            path: 目录路径（相对于基础目录）
            recursive: 是否递归列出
            include_hidden: 是否包含隐藏文件

        Returns:
            文件信息列表
        """
        try:
            dir_path = self._validate_path(path)

            if not dir_path.exists() or not dir_path.is_dir():
                logger.warning(
                    f"Directory {dir_path} does not exist or is not a directory"
                )
                return []

            files = []

            if recursive:
                pattern = "**/*"
            else:
                pattern = "*"

            for item in dir_path.glob(pattern):
                # 跳过隐藏文件（除非明确包含）
                if not include_hidden and item.name.startswith("."):
                    continue

                file_info = self.get_file_info(item)
                if file_info:
                    files.append(file_info)

            # 按名称排序，目录在前
            files.sort(key=lambda x: (not x.is_directory, x.name.lower()))

            return files

        except Exception as e:
            logger.error(f"Error listing directory {path}: {e}")
            return []

    def read_file(
        self, path: Union[str, Path], mode: str = "r", encoding: str = "utf-8"
    ) -> Union[str, bytes, None]:
        """
        读取文件内容

        Args:
            path: 文件路径
            mode: 读取模式 ('r' 或 'rb')
            encoding: 文本编码

        Returns:
            文件内容或None
        """
        try:
            file_path = self._validate_path(path)

            if not file_path.exists() or not file_path.is_file():
                logger.warning(f"File {file_path} does not exist or is not a file")
                return None

            # 检查文件大小
            if file_path.stat().st_size > self.MAX_FILE_SIZE:
                raise ValueError(
                    f"File {file_path} is too large (max {self.MAX_FILE_SIZE} bytes)"
                )

            if mode == "rb":
                with open(file_path, "rb") as f:
                    return f.read()
            else:
                with open(file_path, encoding=encoding) as f:
                    return f.read()

        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            return None

    def write_file(
        self,
        path: Union[str, Path],
        content: Union[str, bytes],
        mode: str = "w",
        encoding: str = "utf-8",
        create_dirs: bool = True,
    ) -> bool:
        """
        写入文件内容

        Args:
            path: 文件路径
            content: 文件内容
            mode: 写入模式 ('w' 或 'wb')
            encoding: 文本编码
            create_dirs: 是否创建父目录

        Returns:
            是否成功
        """
        try:
            file_path = self._validate_path(path)

            # 检查文件扩展名
            if not self._check_file_extension(file_path.name):
                raise ValueError(f"File type not allowed: {file_path.suffix}")

            # 创建父目录
            if create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)

            # 检查内容大小
            content_size = len(content) if isinstance(content, (str, bytes)) else 0
            if content_size > self.MAX_FILE_SIZE:
                raise ValueError(f"Content too large (max {self.MAX_FILE_SIZE} bytes)")

            if mode == "wb":
                with open(file_path, "wb") as f:
                    if not isinstance(content, bytes):
                        raise TypeError("Content must be bytes for 'wb' mode")
                    f.write(content)
            else:
                with open(file_path, "w", encoding=encoding) as f:
                    if not isinstance(content, str):
                        raise TypeError("Content must be str for 'w' mode")
                    f.write(content)

            logger.info(f"File written successfully: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error writing file {path}: {e}")
            return False

    def delete_file(self, path: Union[str, Path]) -> bool:
        """
        删除文件或目录

        Args:
            path: 文件路径

        Returns:
            是否成功
        """
        try:
            file_path = self._validate_path(path)

            if not file_path.exists():
                logger.warning(f"File {file_path} does not exist")
                return False

            if file_path.is_file():
                file_path.unlink()
            elif file_path.is_dir():
                shutil.rmtree(file_path)

            logger.info(f"File deleted successfully: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error deleting file {path}: {e}")
            return False

    def move_file(self, src: Union[str, Path], dst: Union[str, Path]) -> bool:
        """
        移动/重命名文件

        Args:
            src: 源路径
            dst: 目标路径

        Returns:
            是否成功
        """
        try:
            src_path = self._validate_path(src)
            dst_path = self._validate_path(dst)

            if not src_path.exists():
                logger.warning(f"Source file {src_path} does not exist")
                return False

            # 检查目标文件扩展名
            if dst_path.is_file() and not self._check_file_extension(dst_path.name):
                raise ValueError(f"Target file type not allowed: {dst_path.suffix}")

            # 创建目标目录
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            shutil.move(str(src_path), str(dst_path))

            logger.info(f"File moved successfully: {src_path} -> {dst_path}")
            return True

        except Exception as e:
            logger.error(f"Error moving file {src} -> {dst}: {e}")
            return False

    def copy_file(self, src: Union[str, Path], dst: Union[str, Path]) -> bool:
        """
        复制文件

        Args:
            src: 源路径
            dst: 目标路径

        Returns:
            是否成功
        """
        try:
            src_path = self._validate_path(src)
            dst_path = self._validate_path(dst)

            if not src_path.exists():
                logger.warning(f"Source file {src_path} does not exist")
                return False

            # 检查目标文件扩展名
            if not self._check_file_extension(dst_path.name):
                raise ValueError(f"Target file type not allowed: {dst_path.suffix}")

            # 创建目标目录
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            if src_path.is_file():
                shutil.copy2(src_path, dst_path)
            else:
                shutil.copytree(src_path, dst_path)

            logger.info(f"File copied successfully: {src_path} -> {dst_path}")
            return True

        except Exception as e:
            logger.error(f"Error copying file {src} -> {dst}: {e}")
            return False

    def create_directory(self, path: Union[str, Path]) -> bool:
        """
        创建目录

        Args:
            path: 目录路径

        Returns:
            是否成功
        """
        try:
            dir_path = self._validate_path(path)
            dir_path.mkdir(parents=True, exist_ok=True)

            logger.info(f"Directory created successfully: {dir_path}")
            return True

        except Exception as e:
            logger.error(f"Error creating directory {path}: {e}")
            return False

    def upload_file(
        self,
        file_data: BinaryIO,
        filename: str,
        destination: str | Path = "",
        allowed_types: list[str] | None = None,
    ) -> UploadInfo | None:
        """
        上传文件

        Args:
            file_data: 文件数据流
            filename: 文件名
            destination: 目标目录
            allowed_types: 允许的文件类型

        Returns:
            上传信息或None
        """
        try:
            # 检查文件扩展名
            if not self._check_file_extension(filename, allowed_types):
                raise ValueError(f"File type not allowed: {Path(filename).suffix}")

            # 验证目标路径
            dest_dir = self._validate_path(destination)
            if not dest_dir.exists():
                dest_dir.mkdir(parents=True, exist_ok=True)

            file_path = dest_dir / filename

            # 读取文件数据
            file_data.seek(0)
            content = file_data.read()

            # 检查文件大小
            if len(content) > self.MAX_FILE_SIZE:
                raise ValueError(f"File too large (max {self.MAX_FILE_SIZE} bytes)")

            # 写入文件
            with open(file_path, "wb") as f:
                f.write(content)

            # 计算MD5
            hash_md5 = hashlib.md5(content).hexdigest()

            # 获取MIME类型
            mime_type, _ = mimetypes.guess_type(filename)

            # 创建上传信息
            upload_info = UploadInfo(
                filename=filename,
                size=len(content),
                mime_type=mime_type or "application/octet-stream",
                upload_time=datetime.now(),
                hash_md5=hash_md5,
                destination=str(file_path.relative_to(self.base_dir)),
            )

            # 添加到历史记录
            self._upload_history.append(upload_info)
            if len(self._upload_history) > self._max_history:
                self._upload_history.pop(0)

            logger.info(f"File uploaded successfully: {filename} -> {file_path}")
            return upload_info

        except Exception as e:
            logger.error(f"Error uploading file {filename}: {e}")
            return None

    @contextmanager
    def temporary_file(
        self, suffix: Optional[str] = None, prefix: Optional[str] = None
    ):
        """
        创建临时文件上下文管理器

        Args:
            suffix: 文件后缀
            prefix: 文件前缀

        Yields:
            临时文件路径
        """
        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(
                suffix=suffix, prefix=prefix, delete=False
            )
            temp_path = Path(temp_file.name)
            temp_file.close()

            yield temp_path

        finally:
            if temp_file and temp_path.exists():
                temp_path.unlink()

    def create_archive(
        self,
        source_path: Union[str, Path],
        archive_path: Union[str, Path],
        format: str = "zip",
    ) -> bool:
        """
        创建压缩包

        Args:
            source_path: 源路径
            archive_path: 压缩包路径
            format: 压缩格式 ('zip', 'tar', 'gztar')

        Returns:
            是否成功
        """
        try:
            src_path = self._validate_path(source_path)
            archive_path = self._validate_path(archive_path)

            if not src_path.exists():
                logger.warning(f"Source path {src_path} does not exist")
                return False

            # 创建目标目录
            archive_path.parent.mkdir(parents=True, exist_ok=True)

            if format == "zip":
                with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    if src_path.is_file():
                        zipf.write(src_path, src_path.name)
                    else:
                        for file_path in src_path.rglob("*"):
                            if file_path.is_file():
                                arcname = file_path.relative_to(src_path.parent)
                                zipf.write(file_path, arcname)
            else:
                shutil.make_archive(
                    str(archive_path.with_suffix("")),
                    format,
                    str(src_path.parent),
                    str(src_path.name),
                )

            logger.info(f"Archive created successfully: {archive_path}")
            return True

        except Exception as e:
            logger.error(f"Error creating archive {archive_path}: {e}")
            return False

    def extract_archive(
        self, archive_path: Union[str, Path], destination: Union[str, Path]
    ) -> bool:
        """
        解压压缩包

        Args:
            archive_path: 压缩包路径
            destination: 目标目录

        Returns:
            是否成功
        """
        try:
            archive_path = self._validate_path(archive_path)
            dest_path = self._validate_path(destination)

            if not archive_path.exists() or not archive_path.is_file():
                logger.warning(f"Archive {archive_path} does not exist")
                return False

            # 创建目标目录
            dest_path.mkdir(parents=True, exist_ok=True)

            if archive_path.suffix.lower() == ".zip":
                with zipfile.ZipFile(archive_path, "r") as zipf:
                    zipf.extractall(dest_path)
            else:
                shutil.unpack_archive(str(archive_path), str(dest_path))

            logger.info(
                f"Archive extracted successfully: {archive_path} -> {dest_path}"
            )
            return True

        except Exception as e:
            logger.error(f"Error extracting archive {archive_path}: {e}")
            return False

    def get_upload_history(self, limit: int = 100) -> list[UploadInfo]:
        """
        获取上传历史

        Args:
            limit: 返回的最大记录数

        Returns:
            上传信息列表
        """
        return (
            self._upload_history[-limit:]
            if len(self._upload_history) > limit
            else self._upload_history
        )

    def get_disk_usage(self, path: Union[str, Path] = "") -> dict[str, int]:
        """
        获取磁盘使用情况

        Args:
            path: 路径

        Returns:
            磁盘使用信息
        """
        try:
            dir_path = self._validate_path(path)

            total_size = 0
            file_count = 0
            dir_count = 0

            for item in dir_path.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
                    file_count += 1
                elif item.is_dir():
                    dir_count += 1

            return {
                "total_size": total_size,
                "file_count": file_count,
                "directory_count": dir_count,
            }

        except Exception as e:
            logger.error(f"Error getting disk usage for {path}: {e}")
            return {"total_size": 0, "file_count": 0, "directory_count": 0}

    def search_files(
        self, pattern: str, path: Union[str, Path] = "", case_sensitive: bool = False
    ) -> list[FileInfo]:
        """
        搜索文件

        Args:
            pattern: 搜索模式
            path: 搜索路径
            case_sensitive: 是否区分大小写

        Returns:
            匹配的文件列表
        """
        try:
            search_path = self._validate_path(path)

            if not case_sensitive:
                pattern = pattern.lower()

            matches = []
            for item in search_path.rglob("*"):
                item_name = item.name if case_sensitive else item.name.lower()

                if pattern in item_name:
                    file_info = self.get_file_info(item)
                    if file_info:
                        matches.append(file_info)

            return matches

        except Exception as e:
            logger.error(f"Error searching files with pattern '{pattern}': {e}")
            return []

    def set_safe_mode(self, enabled: bool):
        """
        设置安全模式

        Args:
            enabled: 是否启用安全模式
        """
        self._safe_mode = enabled
        logger.info(f"Safe mode {'enabled' if enabled else 'disabled'}")

    def add_allowed_extension(self, extension: str, file_type: str = "custom"):
        """
        添加允许的文件扩展名

        Args:
            extension: 文件扩展名（包含点号）
            file_type: 文件类型
        """
        if file_type not in self.ALLOWED_EXTENSIONS:
            self.ALLOWED_EXTENSIONS[file_type] = []

        self.ALLOWED_EXTENSIONS[file_type].append(extension.lower())
        self._allowed_extensions.add(extension.lower())

        logger.info(f"Added allowed extension: {extension} ({file_type})")

    def get_status(self) -> dict[str, Any]:
        """
        获取文件管理器状态

        Returns:
            状态信息字典
        """
        return {
            "base_directory": str(self.base_dir),
            "safe_mode": self._safe_mode,
            "max_file_size": self.MAX_FILE_SIZE,
            "allowed_extensions": dict(self.ALLOWED_EXTENSIONS),
            "forbidden_extensions": self.FORBIDDEN_EXTENSIONS,
            "upload_history_count": len(self._upload_history),
            "disk_usage": self.get_disk_usage(),
        }
