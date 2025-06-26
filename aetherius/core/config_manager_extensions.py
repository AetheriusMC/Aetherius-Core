"""
Aetherius配置管理扩展
==================

为Web组件提供的增强配置管理功能
"""

import json
import yaml
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union, Callable, Set
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from copy import deepcopy
import hashlib

from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class ConfigSection:
    """配置段信息"""
    name: str
    path: str
    description: str
    schema: Dict[str, Any]
    default_values: Dict[str, Any]
    is_readonly: bool = False
    requires_restart: bool = False
    validation_rules: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)


@dataclass
class ConfigChange:
    """配置变更记录"""
    timestamp: datetime
    section: str
    key: str
    old_value: Any
    new_value: Any
    user: str
    source: str  # web, cli, api, system
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class ConfigValidationResult:
    """配置验证结果"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)


class ConfigManagerExtensions:
    """配置管理器扩展类"""
    
    def __init__(self, base_config: Config, config_directory: str = "config"):
        """
        初始化配置管理扩展
        
        Args:
            base_config: 基础配置对象
            config_directory: 配置文件目录
        """
        self.base_config = base_config
        self.config_dir = Path(config_directory)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置段管理
        self._config_sections: Dict[str, ConfigSection] = {}
        self._config_values: Dict[str, Dict[str, Any]] = {}
        self._config_schemas: Dict[str, Dict[str, Any]] = {}
        
        # 变更追踪
        self._change_history: List[ConfigChange] = []
        self._max_history_entries = 1000
        self._change_callbacks: Dict[str, List[Callable]] = {}
        
        # 验证规则
        self._validation_rules: Dict[str, Dict[str, Callable]] = {}
        self._global_validators: List[Callable] = []
        
        # 配置备份
        self._backup_enabled = True
        self._backup_directory = self.config_dir / "backups"
        self._backup_directory.mkdir(parents=True, exist_ok=True)
        
        # 文件监控
        self._file_watchers: Dict[str, Any] = {}
        self._auto_reload_enabled = False
        
        # 配置缓存
        self._config_cache: Dict[str, Any] = {}
        self._cache_hashes: Dict[str, str] = {}
        
        # 初始化默认配置段
        self._init_default_sections()
        
        logger.info("Config manager extensions initialized")
    
    def _init_default_sections(self):
        """初始化默认配置段"""
        # 服务器配置段
        self.register_config_section(ConfigSection(
            name="server",
            path="server.yaml",
            description="Minecraft服务器基础配置",
            schema={
                "type": "object",
                "properties": {
                    "server_jar": {"type": "string", "description": "服务器JAR文件路径"},
                    "max_players": {"type": "integer", "minimum": 1, "maximum": 1000},
                    "server_port": {"type": "integer", "minimum": 1, "maximum": 65535},
                    "memory_mb": {"type": "integer", "minimum": 512},
                    "java_args": {"type": "array", "items": {"type": "string"}},
                    "world_name": {"type": "string"},
                    "difficulty": {"type": "string", "enum": ["peaceful", "easy", "normal", "hard"]},
                    "gamemode": {"type": "string", "enum": ["survival", "creative", "adventure", "spectator"]}
                }
            },
            default_values={
                "server_jar": "server/server.jar",
                "max_players": 20,
                "server_port": 25565,
                "memory_mb": 2048,
                "java_args": ["-XX:+UseG1GC", "-XX:+UseStringDeduplication"],
                "world_name": "world",
                "difficulty": "normal",
                "gamemode": "survival"
            },
            requires_restart=True
        ))
        
        # Web界面配置段
        self.register_config_section(ConfigSection(
            name="web",
            path="web.yaml",
            description="Web界面配置",
            schema={
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "host": {"type": "string"},
                    "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                    "ssl_enabled": {"type": "boolean"},
                    "ssl_cert": {"type": "string"},
                    "ssl_key": {"type": "string"},
                    "session_timeout": {"type": "integer", "minimum": 300},
                    "max_concurrent_users": {"type": "integer", "minimum": 1},
                    "allowed_origins": {"type": "array", "items": {"type": "string"}},
                    "rate_limit_requests": {"type": "integer", "minimum": 1},
                    "rate_limit_window": {"type": "integer", "minimum": 1}
                }
            },
            default_values={
                "enabled": True,
                "host": "0.0.0.0",
                "port": 8080,
                "ssl_enabled": False,
                "ssl_cert": "",
                "ssl_key": "",
                "session_timeout": 3600,
                "max_concurrent_users": 50,
                "allowed_origins": ["*"],
                "rate_limit_requests": 100,
                "rate_limit_window": 60
            }
        ))
        
        # 监控配置段
        self.register_config_section(ConfigSection(
            name="monitoring",
            path="monitoring.yaml",
            description="性能监控和日志配置",
            schema={
                "type": "object",
                "properties": {
                    "performance_monitoring": {"type": "boolean"},
                    "monitoring_interval": {"type": "integer", "minimum": 5},
                    "metrics_retention_days": {"type": "integer", "minimum": 1},
                    "log_level": {"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR"]},
                    "log_file_max_size": {"type": "integer", "minimum": 1},
                    "log_backup_count": {"type": "integer", "minimum": 1},
                    "enable_crash_reports": {"type": "boolean"},
                    "enable_performance_alerts": {"type": "boolean"}
                }
            },
            default_values={
                "performance_monitoring": True,
                "monitoring_interval": 30,
                "metrics_retention_days": 30,
                "log_level": "INFO",
                "log_file_max_size": 10,
                "log_backup_count": 5,
                "enable_crash_reports": True,
                "enable_performance_alerts": True
            }
        ))
    
    def register_config_section(self, section: ConfigSection):
        """
        注册配置段
        
        Args:
            section: 配置段对象
        """
        self._config_sections[section.name] = section
        
        # 加载默认值
        if section.name not in self._config_values:
            self._config_values[section.name] = section.default_values.copy()
        
        # 尝试从文件加载
        config_file = self.config_dir / section.path
        if config_file.exists():
            try:
                loaded_config = self._load_config_file(config_file)
                if loaded_config:
                    self._config_values[section.name].update(loaded_config)
            except Exception as e:
                logger.error(f"Error loading config section {section.name}: {e}")
        
        logger.info(f"Registered config section: {section.name}")
    
    def _load_config_file(self, config_file: Path) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                if config_file.suffix.lower() in ['.yaml', '.yml']:
                    return yaml.safe_load(f) or {}
                elif config_file.suffix.lower() == '.json':
                    return json.load(f)
                else:
                    logger.warning(f"Unsupported config file format: {config_file}")
                    return {}
        except Exception as e:
            logger.error(f"Error loading config file {config_file}: {e}")
            return {}
    
    def _save_config_file(self, section_name: str) -> bool:
        """保存配置文件"""
        try:
            section = self._config_sections.get(section_name)
            if not section:
                logger.error(f"Config section {section_name} not found")
                return False
            
            config_file = self.config_dir / section.path
            config_data = self._config_values.get(section_name, {})
            
            # 创建备份
            if self._backup_enabled and config_file.exists():
                backup_name = f"{config_file.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{config_file.suffix}"
                backup_path = self._backup_directory / backup_name
                config_file.rename(backup_path)
            
            # 保存配置
            with open(config_file, 'w', encoding='utf-8') as f:
                if config_file.suffix.lower() in ['.yaml', '.yml']:
                    yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
                elif config_file.suffix.lower() == '.json':
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            # 更新缓存哈希
            self._update_cache_hash(section_name)
            
            logger.info(f"Saved config section: {section_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving config section {section_name}: {e}")
            return False
    
    def _update_cache_hash(self, section_name: str):
        """更新配置缓存哈希"""
        config_data = self._config_values.get(section_name, {})
        config_str = json.dumps(config_data, sort_keys=True)
        self._cache_hashes[section_name] = hashlib.md5(config_str.encode()).hexdigest()
    
    def get_config_value(self, section: str, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            section: 配置段名称
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        section_config = self._config_values.get(section, {})
        return section_config.get(key, default)
    
    def get_config_section(self, section: str) -> Dict[str, Any]:
        """
        获取整个配置段
        
        Args:
            section: 配置段名称
            
        Returns:
            配置段字典
        """
        return deepcopy(self._config_values.get(section, {}))
    
    async def set_config_value(self, section: str, key: str, value: Any, 
                              user: str = "system", source: str = "api") -> bool:
        """
        设置配置值
        
        Args:
            section: 配置段名称
            key: 配置键
            value: 配置值
            user: 操作用户
            source: 操作来源
            
        Returns:
            是否成功
        """
        try:
            # 验证配置段存在
            if section not in self._config_sections:
                logger.error(f"Config section {section} not found")
                return False
            
            # 检查只读权限
            section_info = self._config_sections[section]
            if section_info.is_readonly:
                logger.error(f"Config section {section} is readonly")
                return False
            
            # 获取旧值
            old_value = self.get_config_value(section, key)
            
            # 验证新值
            validation_result = await self._validate_config_value(section, key, value)
            if not validation_result.is_valid:
                logger.error(f"Config validation failed: {validation_result.errors}")
                return False
            
            # 设置新值
            if section not in self._config_values:
                self._config_values[section] = {}
            
            self._config_values[section][key] = value
            
            # 记录变更
            change = ConfigChange(
                timestamp=datetime.now(),
                section=section,
                key=key,
                old_value=old_value,
                new_value=value,
                user=user,
                source=source
            )
            
            self._change_history.append(change)
            if len(self._change_history) > self._max_history_entries:
                self._change_history.pop(0)
            
            # 保存到文件
            if not self._save_config_file(section):
                # 回滚
                if old_value is not None:
                    self._config_values[section][key] = old_value
                else:
                    self._config_values[section].pop(key, None)
                return False
            
            # 触发回调
            await self._trigger_change_callbacks(section, key, old_value, value)
            
            logger.info(f"Config updated: {section}.{key} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting config value {section}.{key}: {e}")
            return False
    
    async def _validate_config_value(self, section: str, key: str, value: Any) -> ConfigValidationResult:
        """验证配置值"""
        errors = []
        warnings = []
        suggestions = []
        
        try:
            section_info = self._config_sections.get(section)
            if not section_info:
                errors.append(f"Unknown config section: {section}")
                return ConfigValidationResult(False, errors, warnings, suggestions)
            
            # JSON Schema验证
            if section_info.schema:
                property_schema = section_info.schema.get("properties", {}).get(key)
                if property_schema:
                    validation_errors = self._validate_against_schema(value, property_schema)
                    errors.extend(validation_errors)
            
            # 自定义验证规则
            section_validators = self._validation_rules.get(section, {})
            if key in section_validators:
                try:
                    validator_result = await section_validators[key](value)
                    if isinstance(validator_result, dict):
                        errors.extend(validator_result.get('errors', []))
                        warnings.extend(validator_result.get('warnings', []))
                        suggestions.extend(validator_result.get('suggestions', []))
                    elif not validator_result:
                        errors.append(f"Custom validation failed for {section}.{key}")
                except Exception as e:
                    errors.append(f"Validation error: {e}")
            
            # 全局验证器
            for validator in self._global_validators:
                try:
                    result = await validator(section, key, value)
                    if not result:
                        warnings.append(f"Global validator warning for {section}.{key}")
                except Exception as e:
                    warnings.append(f"Global validator error: {e}")
            
            return ConfigValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                suggestions=suggestions
            )
            
        except Exception as e:
            errors.append(f"Validation exception: {e}")
            return ConfigValidationResult(False, errors, warnings, suggestions)
    
    def _validate_against_schema(self, value: Any, schema: Dict[str, Any]) -> List[str]:
        """根据JSON Schema验证值"""
        errors = []
        
        try:
            # 类型验证
            expected_type = schema.get("type")
            if expected_type:
                if expected_type == "string" and not isinstance(value, str):
                    errors.append(f"Expected string, got {type(value).__name__}")
                elif expected_type == "integer" and not isinstance(value, int):
                    errors.append(f"Expected integer, got {type(value).__name__}")
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    errors.append(f"Expected number, got {type(value).__name__}")
                elif expected_type == "boolean" and not isinstance(value, bool):
                    errors.append(f"Expected boolean, got {type(value).__name__}")
                elif expected_type == "array" and not isinstance(value, list):
                    errors.append(f"Expected array, got {type(value).__name__}")
                elif expected_type == "object" and not isinstance(value, dict):
                    errors.append(f"Expected object, got {type(value).__name__}")
            
            # 范围验证
            if isinstance(value, (int, float)):
                minimum = schema.get("minimum")
                maximum = schema.get("maximum")
                if minimum is not None and value < minimum:
                    errors.append(f"Value {value} is below minimum {minimum}")
                if maximum is not None and value > maximum:
                    errors.append(f"Value {value} is above maximum {maximum}")
            
            # 枚举验证
            enum_values = schema.get("enum")
            if enum_values and value not in enum_values:
                errors.append(f"Value {value} not in allowed values: {enum_values}")
            
            # 字符串长度验证
            if isinstance(value, str):
                min_length = schema.get("minLength")
                max_length = schema.get("maxLength")
                if min_length is not None and len(value) < min_length:
                    errors.append(f"String length {len(value)} is below minimum {min_length}")
                if max_length is not None and len(value) > max_length:
                    errors.append(f"String length {len(value)} is above maximum {max_length}")
            
        except Exception as e:
            errors.append(f"Schema validation error: {e}")
        
        return errors
    
    async def _trigger_change_callbacks(self, section: str, key: str, old_value: Any, new_value: Any):
        """触发配置变更回调"""
        callback_key = f"{section}.{key}"
        section_callbacks = self._change_callbacks.get(section, [])
        key_callbacks = self._change_callbacks.get(callback_key, [])
        
        all_callbacks = section_callbacks + key_callbacks
        
        for callback in all_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(section, key, old_value, new_value)
                else:
                    callback(section, key, old_value, new_value)
            except Exception as e:
                logger.error(f"Error in config change callback: {e}")
    
    def add_change_callback(self, pattern: str, callback: Callable):
        """
        添加配置变更回调
        
        Args:
            pattern: 匹配模式（section 或 section.key）
            callback: 回调函数
        """
        if pattern not in self._change_callbacks:
            self._change_callbacks[pattern] = []
        
        self._change_callbacks[pattern].append(callback)
        logger.debug(f"Added config change callback for pattern: {pattern}")
    
    def remove_change_callback(self, pattern: str, callback: Callable):
        """移除配置变更回调"""
        if pattern in self._change_callbacks and callback in self._change_callbacks[pattern]:
            self._change_callbacks[pattern].remove(callback)
    
    def add_validation_rule(self, section: str, key: str, validator: Callable):
        """
        添加配置验证规则
        
        Args:
            section: 配置段名称
            key: 配置键
            validator: 验证函数
        """
        if section not in self._validation_rules:
            self._validation_rules[section] = {}
        
        self._validation_rules[section][key] = validator
        logger.debug(f"Added validation rule for {section}.{key}")
    
    def add_global_validator(self, validator: Callable):
        """添加全局验证器"""
        self._global_validators.append(validator)
    
    def get_change_history(self, section: str = None, 
                          limit: int = 100,
                          days: int = 30) -> List[ConfigChange]:
        """
        获取配置变更历史
        
        Args:
            section: 配置段过滤器
            limit: 返回的最大记录数
            days: 查询天数
            
        Returns:
            配置变更列表
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        history = []
        for change in reversed(self._change_history):
            if change.timestamp < cutoff_date:
                break
            
            if section is None or change.section == section:
                history.append(change)
                
                if len(history) >= limit:
                    break
        
        return history
    
    def export_config(self, sections: List[str] = None) -> Dict[str, Any]:
        """
        导出配置
        
        Args:
            sections: 要导出的配置段列表，None表示全部
            
        Returns:
            配置数据字典
        """
        export_data = {
            'timestamp': datetime.now().isoformat(),
            'sections': {}
        }
        
        target_sections = sections or list(self._config_sections.keys())
        
        for section_name in target_sections:
            if section_name in self._config_values:
                export_data['sections'][section_name] = deepcopy(self._config_values[section_name])
        
        return export_data
    
    async def import_config(self, config_data: Dict[str, Any], 
                           user: str = "system", 
                           source: str = "import",
                           validate: bool = True) -> Dict[str, Any]:
        """
        导入配置
        
        Args:
            config_data: 配置数据字典
            user: 操作用户
            source: 操作来源
            validate: 是否验证配置
            
        Returns:
            导入结果
        """
        results = {
            'success': True,
            'imported_sections': [],
            'failed_sections': [],
            'errors': []
        }
        
        sections_data = config_data.get('sections', {})
        
        for section_name, section_config in sections_data.items():
            try:
                # 验证配置段存在
                if section_name not in self._config_sections:
                    results['errors'].append(f"Unknown config section: {section_name}")
                    results['failed_sections'].append(section_name)
                    continue
                
                # 逐个设置配置值
                section_success = True
                for key, value in section_config.items():
                    if validate:
                        validation_result = await self._validate_config_value(section_name, key, value)
                        if not validation_result.is_valid:
                            results['errors'].extend([f"{section_name}.{key}: {error}" for error in validation_result.errors])
                            section_success = False
                            continue
                    
                    success = await self.set_config_value(section_name, key, value, user, source)
                    if not success:
                        section_success = False
                
                if section_success:
                    results['imported_sections'].append(section_name)
                else:
                    results['failed_sections'].append(section_name)
                    
            except Exception as e:
                results['errors'].append(f"Error importing section {section_name}: {e}")
                results['failed_sections'].append(section_name)
        
        if results['failed_sections']:
            results['success'] = False
        
        return results
    
    def get_config_schema(self, section: str = None) -> Dict[str, Any]:
        """
        获取配置架构
        
        Args:
            section: 配置段名称，None表示全部
            
        Returns:
            配置架构字典
        """
        if section:
            section_info = self._config_sections.get(section)
            if section_info:
                return section_info.schema
            return {}
        
        schemas = {}
        for section_name, section_info in self._config_sections.items():
            schemas[section_name] = section_info.schema
        
        return schemas
    
    def get_config_sections_info(self) -> List[Dict[str, Any]]:
        """获取所有配置段信息"""
        sections_info = []
        for section_info in self._config_sections.values():
            info = section_info.to_dict()
            info['current_values'] = deepcopy(self._config_values.get(section_info.name, {}))
            info['has_changes'] = self._has_unsaved_changes(section_info.name)
            sections_info.append(info)
        
        return sections_info
    
    def _has_unsaved_changes(self, section: str) -> bool:
        """检查是否有未保存的更改"""
        current_hash = self._cache_hashes.get(section)
        if not current_hash:
            return True
        
        config_data = self._config_values.get(section, {})
        config_str = json.dumps(config_data, sort_keys=True)
        new_hash = hashlib.md5(config_str.encode()).hexdigest()
        
        return current_hash != new_hash
    
    async def reset_section_to_defaults(self, section: str, 
                                       user: str = "system",
                                       source: str = "reset") -> bool:
        """
        重置配置段到默认值
        
        Args:
            section: 配置段名称
            user: 操作用户
            source: 操作来源
            
        Returns:
            是否成功
        """
        try:
            section_info = self._config_sections.get(section)
            if not section_info:
                logger.error(f"Config section {section} not found")
                return False
            
            if section_info.is_readonly:
                logger.error(f"Config section {section} is readonly")
                return False
            
            # 记录当前值
            old_values = deepcopy(self._config_values.get(section, {}))
            
            # 重置到默认值
            self._config_values[section] = deepcopy(section_info.default_values)
            
            # 保存到文件
            if not self._save_config_file(section):
                # 回滚
                self._config_values[section] = old_values
                return False
            
            # 记录变更
            for key, new_value in section_info.default_values.items():
                old_value = old_values.get(key)
                
                change = ConfigChange(
                    timestamp=datetime.now(),
                    section=section,
                    key=key,
                    old_value=old_value,
                    new_value=new_value,
                    user=user,
                    source=source
                )
                
                self._change_history.append(change)
                
                # 触发回调
                await self._trigger_change_callbacks(section, key, old_value, new_value)
            
            logger.info(f"Reset config section to defaults: {section}")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting config section {section}: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取配置管理统计信息"""
        return {
            'total_sections': len(self._config_sections),
            'total_change_records': len(self._change_history),
            'total_callbacks': sum(len(callbacks) for callbacks in self._change_callbacks.values()),
            'total_validators': sum(len(validators) for validators in self._validation_rules.values()),
            'global_validators': len(self._global_validators),
            'backup_enabled': self._backup_enabled,
            'auto_reload_enabled': self._auto_reload_enabled,
            'sections_with_changes': sum(1 for section in self._config_sections if self._has_unsaved_changes(section))
        }