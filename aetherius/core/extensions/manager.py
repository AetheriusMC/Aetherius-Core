"""
扩展管理器实现

提供完整的扩展生命周期管理功能
"""

import asyncio
import importlib
import importlib.util
import inspect
import sys
import threading
import traceback
from typing import Dict, List, Optional, Set, Type, Any
from pathlib import Path
from collections import defaultdict, deque
import logging
import yaml
import json

from . import (
    IExtensionManager, IExtensionLoader, IExtension, IPlugin, IComponent,
    ExtensionInfo, ExtensionContext, ExtensionType, ExtensionState,
    ExtensionError, ExtensionLoadError, ExtensionDependencyError,
    ExtensionPermission, ExtensionSandbox, VersionChecker
)

logger = logging.getLogger(__name__)


class ExtensionManager(IExtensionManager):
    """扩展管理器实现"""
    
    def __init__(self, 
                 config_manager,
                 event_manager, 
                 di_container,
                 data_dir: Path):
        self.config = config_manager
        self.events = event_manager
        self.services = di_container
        self.data_dir = data_dir
        
        # 扩展存储
        self._extensions: Dict[str, IExtension] = {}
        self._extension_infos: Dict[str, ExtensionInfo] = {}
        self._loaders: List[IExtensionLoader] = []
        self._lock = threading.RLock()
        
        # 依赖关系图
        self._dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self._reverse_dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        
        # 状态跟踪
        self._loading_extensions: Set[str] = set()
        self._startup_order: List[str] = []
        
        # 注册默认加载器
        self._register_default_loaders()
        
        # 创建扩展数据目录
        self.extensions_dir = data_dir / "extensions"
        self.extensions_dir.mkdir(parents=True, exist_ok=True)
    
    async def discover_extensions(self, directories: List[Path]) -> List[ExtensionInfo]:
        """发现扩展"""
        discovered = []
        
        for directory in directories:
            if not directory.exists():
                logger.warning(f"Extension directory not found: {directory}")
                continue
            
            logger.info(f"Discovering extensions in: {directory}")
            
            # 遍历目录查找扩展
            for path in directory.iterdir():
                if path.is_dir():
                    # 目录形式的扩展
                    info = await self._discover_directory_extension(path)
                    if info:
                        discovered.append(info)
                elif path.suffix in ('.py', '.zip', '.egg'):
                    # 文件形式的扩展
                    info = await self._discover_file_extension(path)
                    if info:
                        discovered.append(info)
        
        # 更新扩展信息缓存
        with self._lock:
            for info in discovered:
                self._extension_infos[info.name] = info
        
        logger.info(f"Discovered {len(discovered)} extensions")
        return discovered
    
    async def load_extension(self, name: str) -> bool:
        """加载扩展"""
        if name in self._loading_extensions:
            logger.warning(f"Extension {name} is already being loaded")
            return False
        
        info = self._extension_infos.get(name)
        if not info:
            logger.error(f"Extension {name} not found")
            return False
        
        try:
            self._loading_extensions.add(name)
            
            # 检查依赖关系
            missing_deps = await self._check_and_load_dependencies(info)
            if missing_deps:
                raise ExtensionDependencyError(
                    f"Missing dependencies for {name}: {', '.join(missing_deps)}"
                )
            
            # 检查冲突
            conflicts = self._check_conflicts(info)
            if conflicts:
                raise ExtensionError(
                    f"Extension {name} conflicts with: {', '.join(conflicts)}"
                )
            
            # 检查版本兼容性
            if not self._check_version_compatibility(info):
                raise ExtensionError(f"Extension {name} is not compatible with current Aetherius version")
            
            # 创建扩展上下文
            context = ExtensionContext(
                extension_info=info,
                config_manager=self.config,
                event_manager=self.events,
                di_container=self.services,
                logger=logging.getLogger(f"aetherius.extension.{name}"),
                data_dir=self.data_dir
            )
            
            # 加载扩展
            extension = await self._load_extension_instance(info, context)
            
            # 设置沙箱（如果需要）
            if info.sandbox:
                self._setup_sandbox(extension, info.permissions)
            
            # 注册扩展
            with self._lock:
                self._extensions[name] = extension
                self._update_dependency_graph(info)
            
            # 触发加载事件
            await self.events.publish("extension.loaded", {
                "name": name,
                "info": info,
                "extension": extension
            })
            
            logger.info(f"Extension {name} loaded successfully")
            return True
        
        except Exception as e:
            logger.error(f"Failed to load extension {name}: {e}")
            logger.debug(traceback.format_exc())
            return False
        
        finally:
            self._loading_extensions.discard(name)
    
    async def unload_extension(self, name: str) -> bool:
        """卸载扩展"""
        extension = self._extensions.get(name)
        if not extension:
            logger.warning(f"Extension {name} is not loaded")
            return False
        
        try:
            # 检查是否有其他扩展依赖于此扩展
            dependents = self._reverse_dependency_graph.get(name, set())
            if dependents:
                logger.error(f"Cannot unload {name}, it is required by: {', '.join(dependents)}")
                return False
            
            # 停止扩展
            if extension.state == ExtensionState.RUNNING:
                await self.stop_extension(name)
            
            # 卸载扩展
            await extension.unload()
            extension.state = ExtensionState.UNLOADED
            
            # 从注册表中移除
            with self._lock:
                del self._extensions[name]
                self._remove_from_dependency_graph(name)
            
            # 触发卸载事件
            await self.events.publish("extension.unloaded", {
                "name": name,
                "extension": extension
            })
            
            logger.info(f"Extension {name} unloaded successfully")
            return True
        
        except Exception as e:
            logger.error(f"Failed to unload extension {name}: {e}")
            logger.debug(traceback.format_exc())
            return False
    
    async def start_extension(self, name: str) -> bool:
        """启动扩展"""
        extension = self._extensions.get(name)
        if not extension:
            logger.error(f"Extension {name} is not loaded")
            return False
        
        if extension.state == ExtensionState.RUNNING:
            logger.warning(f"Extension {name} is already running")
            return True
        
        try:
            extension.state = ExtensionState.STARTING
            
            # 确保依赖的扩展已启动
            info = self._extension_infos[name]
            for dep_name in info.dependencies:
                dep_extension = self._extensions.get(dep_name)
                if dep_extension and dep_extension.state != ExtensionState.RUNNING:
                    await self.start_extension(dep_name)
            
            # 启动扩展
            await extension.start()
            extension.state = ExtensionState.RUNNING
            
            # 注册扩展服务
            await self._register_extension_services(extension)
            
            # 触发启动事件
            await self.events.publish("extension.started", {
                "name": name,
                "extension": extension
            })
            
            logger.info(f"Extension {name} started successfully")
            return True
        
        except Exception as e:
            extension.state = ExtensionState.ERROR
            logger.error(f"Failed to start extension {name}: {e}")
            logger.debug(traceback.format_exc())
            return False
    
    async def stop_extension(self, name: str) -> bool:
        """停止扩展"""
        extension = self._extensions.get(name)
        if not extension:
            logger.error(f"Extension {name} is not loaded")
            return False
        
        if extension.state != ExtensionState.RUNNING:
            logger.warning(f"Extension {name} is not running")
            return True
        
        try:
            extension.state = ExtensionState.STOPPING
            
            # 停止依赖于此扩展的其他扩展
            dependents = self._reverse_dependency_graph.get(name, set())
            for dep_name in dependents:
                dep_extension = self._extensions.get(dep_name)
                if dep_extension and dep_extension.state == ExtensionState.RUNNING:
                    await self.stop_extension(dep_name)
            
            # 停止扩展
            await extension.stop()
            extension.state = ExtensionState.STOPPED
            
            # 注销扩展服务
            await self._unregister_extension_services(extension)
            
            # 触发停止事件
            await self.events.publish("extension.stopped", {
                "name": name,
                "extension": extension
            })
            
            logger.info(f"Extension {name} stopped successfully")
            return True
        
        except Exception as e:
            extension.state = ExtensionState.ERROR
            logger.error(f"Failed to stop extension {name}: {e}")
            logger.debug(traceback.format_exc())
            return False
    
    async def reload_extension(self, name: str) -> bool:
        """重新加载扩展"""
        logger.info(f"Reloading extension: {name}")
        
        # 保存当前状态
        was_running = False
        extension = self._extensions.get(name)
        if extension:
            was_running = extension.state == ExtensionState.RUNNING
        
        # 卸载扩展
        if extension:
            await self.unload_extension(name)
        
        # 重新发现扩展信息
        info = self._extension_infos.get(name)
        if info and info.file_path:
            # 重新加载扩展信息
            new_info = None
            for loader in self._loaders:
                if loader.can_load(info.file_path):
                    new_info = loader.get_extension_info(info.file_path)
                    break
            
            if new_info:
                self._extension_infos[name] = new_info
        
        # 重新加载
        success = await self.load_extension(name)
        
        # 如果之前在运行，则重新启动
        if success and was_running:
            success = await self.start_extension(name)
        
        return success
    
    def get_extension(self, name: str) -> Optional[IExtension]:
        """获取扩展实例"""
        return self._extensions.get(name)
    
    def get_extensions(self, 
                      extension_type: Optional[ExtensionType] = None,
                      state: Optional[ExtensionState] = None) -> List[IExtension]:
        """获取扩展列表"""
        extensions = []
        
        for extension in self._extensions.values():
            # 类型过滤
            if extension_type and extension.info.extension_type != extension_type:
                continue
            
            # 状态过滤
            if state and extension.state != state:
                continue
            
            extensions.append(extension)
        
        return extensions
    
    def check_dependencies(self, extension_info: ExtensionInfo) -> List[str]:
        """检查依赖关系"""
        missing = []
        
        for dep_name in extension_info.dependencies:
            if dep_name not in self._extension_infos:
                missing.append(dep_name)
        
        return missing
    
    async def load_all_extensions(self, directories: List[Path]):
        """加载所有扩展"""
        # 发现扩展
        await self.discover_extensions(directories)
        
        # 计算加载顺序
        load_order = self._calculate_load_order()
        
        # 按顺序加载
        for name in load_order:
            if self.config.get(f"extensions.{name}.enabled", True):
                await self.load_extension(name)
    
    async def start_all_extensions(self):
        """启动所有已加载的扩展"""
        # 按依赖顺序启动
        start_order = self._calculate_startup_order()
        
        for name in start_order:
            extension = self._extensions.get(name)
            if extension and extension.state == ExtensionState.LOADED:
                await self.start_extension(name)
    
    async def stop_all_extensions(self):
        """停止所有扩展"""
        # 按依赖顺序的反序停止
        stop_order = list(reversed(self._startup_order))
        
        for name in stop_order:
            extension = self._extensions.get(name)
            if extension and extension.state == ExtensionState.RUNNING:
                await self.stop_extension(name)
    
    def get_extension_status(self) -> Dict[str, Any]:
        """获取扩展状态摘要"""
        status = {
            "total": len(self._extension_infos),
            "loaded": len(self._extensions),
            "running": len([e for e in self._extensions.values() if e.state == ExtensionState.RUNNING]),
            "error": len([e for e in self._extensions.values() if e.state == ExtensionState.ERROR]),
            "extensions": {}
        }
        
        for name, extension in self._extensions.items():
            status["extensions"][name] = extension.get_health_status()
        
        return status
    
    # 私有方法
    
    def _register_default_loaders(self):
        """注册默认加载器"""
        self._loaders.extend([
            PythonModuleLoader(),
            PythonPackageLoader(),
            YamlManifestLoader()
        ])
    
    async def _discover_directory_extension(self, path: Path) -> Optional[ExtensionInfo]:
        """发现目录形式的扩展"""
        for loader in self._loaders:
            if loader.can_load(path):
                return loader.get_extension_info(path)
        return None
    
    async def _discover_file_extension(self, path: Path) -> Optional[ExtensionInfo]:
        """发现文件形式的扩展"""
        for loader in self._loaders:
            if loader.can_load(path):
                return loader.get_extension_info(path)
        return None
    
    async def _check_and_load_dependencies(self, info: ExtensionInfo) -> List[str]:
        """检查并加载依赖"""
        missing = []
        
        for dep_name in info.dependencies:
            if dep_name not in self._extensions:
                # 尝试加载依赖
                if dep_name in self._extension_infos:
                    success = await self.load_extension(dep_name)
                    if not success:
                        missing.append(dep_name)
                else:
                    missing.append(dep_name)
        
        return missing
    
    def _check_conflicts(self, info: ExtensionInfo) -> List[str]:
        """检查冲突"""
        conflicts = []
        
        for conflict_name in info.conflicts:
            if conflict_name in self._extensions:
                conflicts.append(conflict_name)
        
        return conflicts
    
    def _check_version_compatibility(self, info: ExtensionInfo) -> bool:
        """检查版本兼容性"""
        if not info.aetherius_version:
            return True  # 没有版本要求
        
        current_version = self.config.get("aetherius.version", "1.0.0")
        return VersionChecker.check_compatibility(info.aetherius_version, current_version)
    
    async def _load_extension_instance(self, info: ExtensionInfo, context: ExtensionContext) -> IExtension:
        """加载扩展实例"""
        for loader in self._loaders:
            if loader.can_load(info.file_path or info.package_path):
                extension = await loader.load_extension(info.file_path or info.package_path, context)
                extension.state = ExtensionState.LOADED
                return extension
        
        raise ExtensionLoadError(f"No suitable loader found for {info.name}")
    
    def _setup_sandbox(self, extension: IExtension, permissions: List[str]):
        """设置扩展沙箱"""
        sandbox = ExtensionSandbox(set(permissions))
        # 这里可以实现更复杂的沙箱逻辑
        extension._sandbox = sandbox
    
    def _update_dependency_graph(self, info: ExtensionInfo):
        """更新依赖关系图"""
        name = info.name
        
        # 添加依赖关系
        for dep in info.dependencies:
            self._dependency_graph[name].add(dep)
            self._reverse_dependency_graph[dep].add(name)
    
    def _remove_from_dependency_graph(self, name: str):
        """从依赖关系图中移除"""
        # 移除依赖关系
        for dep in self._dependency_graph.get(name, set()):
            self._reverse_dependency_graph[dep].discard(name)
        
        # 移除反向依赖关系
        for dependent in self._reverse_dependency_graph.get(name, set()):
            self._dependency_graph[dependent].discard(name)
        
        # 清除自身
        self._dependency_graph.pop(name, None)
        self._reverse_dependency_graph.pop(name, None)
    
    def _calculate_load_order(self) -> List[str]:
        """计算加载顺序（拓扑排序）"""
        # 使用Kahn算法进行拓扑排序
        in_degree = defaultdict(int)
        
        # 计算入度
        for name in self._extension_infos:
            in_degree[name] = 0
        
        for name, deps in self._dependency_graph.items():
            for dep in deps:
                in_degree[name] += 1
        
        # 拓扑排序
        queue = deque([name for name in self._extension_infos if in_degree[name] == 0])
        result = []
        
        while queue:
            current = queue.popleft()
            result.append(current)
            
            # 更新依赖此扩展的其他扩展的入度
            for dependent in self._reverse_dependency_graph.get(current, set()):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        # 检查循环依赖
        if len(result) != len(self._extension_infos):
            remaining = set(self._extension_infos.keys()) - set(result)
            logger.warning(f"Circular dependency detected among: {remaining}")
            result.extend(remaining)  # 添加剩余的扩展
        
        return result
    
    def _calculate_startup_order(self) -> List[str]:
        """计算启动顺序"""
        # 只考虑已加载的扩展
        loaded_extensions = set(self._extensions.keys())
        
        # 构建已加载扩展的依赖图
        loaded_graph = defaultdict(set)
        for name, deps in self._dependency_graph.items():
            if name in loaded_extensions:
                loaded_deps = deps & loaded_extensions
                loaded_graph[name] = loaded_deps
        
        # 拓扑排序
        in_degree = defaultdict(int)
        for name in loaded_extensions:
            in_degree[name] = 0
        
        for name, deps in loaded_graph.items():
            for dep in deps:
                in_degree[name] += 1
        
        queue = deque([name for name in loaded_extensions if in_degree[name] == 0])
        result = []
        
        while queue:
            current = queue.popleft()
            result.append(current)
            
            for dependent in self._reverse_dependency_graph.get(current, set()):
                if dependent in loaded_extensions:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
        
        self._startup_order = result
        return result
    
    async def _register_extension_services(self, extension: IExtension):
        """注册扩展服务"""
        if isinstance(extension, IComponent):
            # 注册组件服务
            services = extension.get_services()
            for service_type, service_instance in services.items():
                self.services.register_instance(service_type, service_instance)
    
    async def _unregister_extension_services(self, extension: IExtension):
        """注销扩展服务"""
        # 这里需要依赖注入容器支持服务注销
        pass


# 加载器实现

class PythonModuleLoader(IExtensionLoader):
    """Python模块加载器"""
    
    def can_load(self, path: Path) -> bool:
        """检查是否可以加载"""
        return path.is_file() and path.suffix == '.py'
    
    async def load_extension(self, path: Path, context: ExtensionContext) -> IExtension:
        """加载扩展"""
        try:
            # 动态导入模块
            spec = importlib.util.spec_from_file_location(path.stem, path)
            if not spec or not spec.loader:
                raise ExtensionLoadError(f"Cannot create module spec for {path}")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找扩展类
            extension_class = None
            candidates = []
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (inspect.isclass(attr) and 
                    issubclass(attr, IExtension) and 
                    attr != IExtension and
                    attr != IPlugin and
                    attr != IComponent):
                    candidates.append((attr_name, attr))
                    extension_class = attr
                    logger.debug(f"Found extension class: {attr_name} = {attr}")
                    break
            
            if not extension_class:
                logger.error(f"No extension class found in {path}. Candidates checked: {[name for name, _ in candidates]}")
                raise ExtensionLoadError(f"No extension class found in {path}")
            
            # 检查抽象方法
            try:
                # 尝试实例化以验证所有抽象方法都已实现
                logger.debug(f"Attempting to instantiate {extension_class.__name__}")
                return extension_class(context)
            except TypeError as e:
                if "abstract" in str(e):
                    logger.error(f"Abstract method error for {extension_class.__name__}: {e}")
                    # 详细检查抽象方法
                    abstract_methods = getattr(extension_class, '__abstractmethods__', set())
                    logger.error(f"Abstract methods that need implementation: {abstract_methods}")
                    for method in abstract_methods:
                        has_method = hasattr(extension_class, method)
                        logger.error(f"  {method}: {'implemented' if has_method else 'missing'}")
                raise ExtensionLoadError(f"Failed to instantiate {extension_class.__name__}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error instantiating {extension_class.__name__}: {e}")
                raise ExtensionLoadError(f"Failed to instantiate {extension_class.__name__}: {e}")
        
        except Exception as e:
            raise ExtensionLoadError(f"Failed to load module {path}: {e}")
    
    def get_extension_info(self, path: Path) -> Optional[ExtensionInfo]:
        """获取扩展信息"""
        try:
            # 读取模块内容查找扩展信息
            content = path.read_text(encoding='utf-8')
            
            # 简单的解析（可以改进为AST解析）
            info_dict = self._extract_extension_info_from_content(content)
            if info_dict:
                info_dict['file_path'] = path
                return ExtensionInfo(**info_dict)
            
            # 如果没有找到装饰器信息，返回基本信息
            return ExtensionInfo(
                name=path.stem,
                version="1.0.0",
                file_path=path,
                extension_type=ExtensionType.PLUGIN
            )
        
        except Exception as e:
            logger.warning(f"Failed to get extension info from {path}: {e}")
            return None
    
    def _extract_extension_info_from_content(self, content: str) -> Optional[Dict[str, Any]]:
        """从内容中提取扩展信息"""
        import ast
        import re
        
        # 简单的正则表达式解析装饰器
        patterns = [
            r'@plugin\s*\(\s*name\s*=\s*["\']([^"\']+)["\'].*?version\s*=\s*["\']([^"\']+)["\']',
            r'@component\s*\(\s*name\s*=\s*["\']([^"\']+)["\'].*?version\s*=\s*["\']([^"\']+)["\']'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return {
                    'name': match.group(1),
                    'version': match.group(2),
                    'extension_type': ExtensionType.PLUGIN if '@plugin' in pattern else ExtensionType.COMPONENT
                }
        
        return None


class PythonPackageLoader(IExtensionLoader):
    """Python包加载器"""
    
    def can_load(self, path: Path) -> bool:
        """检查是否可以加载"""
        return (path.is_dir() and 
                (path / '__init__.py').exists())
    
    async def load_extension(self, path: Path, context: ExtensionContext) -> IExtension:
        """加载扩展"""
        try:
            # 添加到sys.path
            parent_dir = path.parent
            if str(parent_dir) not in sys.path:
                sys.path.insert(0, str(parent_dir))
            
            # 导入包
            module = importlib.import_module(path.name)
            
            # 查找扩展类
            extension_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (inspect.isclass(attr) and 
                    issubclass(attr, IExtension) and 
                    attr != IExtension):
                    extension_class = attr
                    break
            
            if not extension_class:
                raise ExtensionLoadError(f"No extension class found in package {path}")
            
            return extension_class(context)
        
        except Exception as e:
            raise ExtensionLoadError(f"Failed to load package {path}: {e}")
    
    def get_extension_info(self, path: Path) -> Optional[ExtensionInfo]:
        """获取扩展信息"""
        try:
            # 检查是否有extension.yaml或plugin.yaml
            for filename in ['extension.yaml', 'plugin.yaml', 'component.yaml']:
                manifest_file = path / filename
                if manifest_file.exists():
                    return self._load_yaml_manifest(manifest_file, path)
            
            # 从__init__.py中提取信息
            init_file = path / '__init__.py'
            if init_file.exists():
                content = init_file.read_text(encoding='utf-8')
                info_dict = self._extract_extension_info_from_content(content)
                if info_dict:
                    info_dict['package_path'] = path
                    return ExtensionInfo(**info_dict)
            
            # 返回基本信息
            return ExtensionInfo(
                name=path.name,
                version="1.0.0",
                package_path=path,
                extension_type=ExtensionType.PLUGIN
            )
        
        except Exception as e:
            logger.warning(f"Failed to get extension info from package {path}: {e}")
            return None
    
    def _load_yaml_manifest(self, manifest_file: Path, package_path: Path) -> ExtensionInfo:
        """从YAML清单文件加载信息"""
        with open(manifest_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        data['package_path'] = package_path
        if 'extension_type' in data:
            data['extension_type'] = ExtensionType(data['extension_type'])
        
        # 移除不被ExtensionInfo接受的字段
        filtered_data = {}
        extension_info_fields = {
            'name', 'version', 'display_name', 'description', 'author', 'website', 'license',
            'dependencies', 'soft_dependencies', 'conflicts', 'aetherius_version', 'python_version',
            'category', 'tags', 'permissions', 'sandbox', 'extension_type', 'entry_point',
            'config_schema', 'provides', 'file_path', 'package_path'
        }
        
        for key, value in data.items():
            if key in extension_info_fields:
                filtered_data[key] = value
        
        return ExtensionInfo(**filtered_data)


class YamlManifestLoader(IExtensionLoader):
    """YAML清单加载器"""
    
    def can_load(self, path: Path) -> bool:
        """检查是否可以加载"""
        return (path.is_file() and 
                path.suffix in ('.yaml', '.yml') and
                path.stem in ('extension', 'plugin', 'component'))
    
    async def load_extension(self, path: Path, context: ExtensionContext) -> IExtension:
        """加载扩展"""
        # YAML清单不能直接加载扩展，需要指向Python代码
        raise ExtensionLoadError("YAML manifest loader cannot load extensions directly")
    
    def get_extension_info(self, path: Path) -> Optional[ExtensionInfo]:
        """获取扩展信息"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            data['file_path'] = path
            if 'extension_type' in data:
                data['extension_type'] = ExtensionType(data['extension_type'])
            
            return ExtensionInfo(**data)
        
        except Exception as e:
            logger.warning(f"Failed to load YAML manifest {path}: {e}")
            return None