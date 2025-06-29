"""
配置验证和模板系统

提供强大的配置验证和模板渲染功能
"""

import re
import json
import ipaddress
from typing import Any, Dict, List, Optional, Union, Callable, Type
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import logging

from .interfaces import IConfigValidator, IConfigTemplate, ConfigValidationError

logger = logging.getLogger(__name__)


class ValidationType(Enum):
    """验证类型枚举"""
    TYPE = "type"
    RANGE = "range" 
    REGEX = "regex"
    ENUM = "enum"
    LENGTH = "length"
    CUSTOM = "custom"
    IP_ADDRESS = "ip_address"
    URL = "url"
    FILE_PATH = "file_path"
    EMAIL = "email"


@dataclass
class ValidationRule:
    """验证规则"""
    type: ValidationType
    parameters: Dict[str, Any]
    message: Optional[str] = None
    optional: bool = False


class SchemaValidator(IConfigValidator):
    """基于 Schema 的配置验证器"""
    
    def __init__(self, schema: Dict[str, Any]):
        self.schema = schema
        self._type_converters = {
            'int': int,
            'float': float,
            'str': str,
            'bool': self._convert_bool,
            'list': list,
            'dict': dict,
        }
    
    def validate(self, key: str, value: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """验证配置值"""
        key_schema = self._get_key_schema(key)
        if not key_schema:
            return value  # 无schema则不验证
        
        # 类型验证和转换
        if 'type' in key_schema:
            expected_type = key_schema['type']
            value = self._convert_type(value, expected_type)
        
        # 应用验证规则
        if 'rules' in key_schema:
            for rule_def in key_schema['rules']:
                rule = ValidationRule(**rule_def)
                value = self._apply_rule(key, value, rule, context)
        
        return value
    
    def get_schema(self) -> Dict[str, Any]:
        """获取配置模式"""
        return self.schema
    
    def _get_key_schema(self, key: str) -> Optional[Dict[str, Any]]:
        """获取键对应的schema"""
        # 支持嵌套键和通配符
        parts = key.split('.')
        current = self.schema
        
        for part in parts:
            if isinstance(current, dict):
                if part in current:
                    current = current[part]
                elif '*' in current:
                    current = current['*']
                else:
                    return None
            else:
                return None
        
        return current if isinstance(current, dict) else None
    
    def _convert_type(self, value: Any, expected_type: str) -> Any:
        """类型转换"""
        if value is None:
            return None
        
        converter = self._type_converters.get(expected_type)
        if not converter:
            raise ConfigValidationError(f"Unknown type: {expected_type}")
        
        try:
            return converter(value)
        except (ValueError, TypeError) as e:
            raise ConfigValidationError(f"Cannot convert to {expected_type}: {e}")
    
    def _convert_bool(self, value: Any) -> bool:
        """布尔值转换"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on', 'enabled')
        if isinstance(value, (int, float)):
            return bool(value)
        raise ValueError(f"Cannot convert {value} to bool")
    
    def _apply_rule(self, key: str, value: Any, rule: ValidationRule, context: Optional[Dict[str, Any]]) -> Any:
        """应用验证规则"""
        if value is None and rule.optional:
            return value
        
        try:
            if rule.type == ValidationType.RANGE:
                return self._validate_range(value, rule.parameters)
            elif rule.type == ValidationType.REGEX:
                return self._validate_regex(value, rule.parameters)
            elif rule.type == ValidationType.ENUM:
                return self._validate_enum(value, rule.parameters)
            elif rule.type == ValidationType.LENGTH:
                return self._validate_length(value, rule.parameters)
            elif rule.type == ValidationType.IP_ADDRESS:
                return self._validate_ip_address(value, rule.parameters)
            elif rule.type == ValidationType.URL:
                return self._validate_url(value, rule.parameters)
            elif rule.type == ValidationType.FILE_PATH:
                return self._validate_file_path(value, rule.parameters)
            elif rule.type == ValidationType.EMAIL:
                return self._validate_email(value, rule.parameters)
            elif rule.type == ValidationType.CUSTOM:
                return self._validate_custom(value, rule.parameters, context)
            else:
                return value
        
        except Exception as e:
            message = rule.message or str(e)
            raise ConfigValidationError(f"Validation failed for {key}: {message}")
    
    def _validate_range(self, value: Any, params: Dict[str, Any]) -> Any:
        """范围验证"""
        min_val = params.get('min')
        max_val = params.get('max')
        
        if min_val is not None and value < min_val:
            raise ValueError(f"Value {value} is less than minimum {min_val}")
        
        if max_val is not None and value > max_val:
            raise ValueError(f"Value {value} is greater than maximum {max_val}")
        
        return value
    
    def _validate_regex(self, value: Any, params: Dict[str, Any]) -> Any:
        """正则验证"""
        pattern = params.get('pattern')
        if not pattern:
            raise ValueError("Regex pattern is required")
        
        if not isinstance(value, str):
            value = str(value)
        
        if not re.match(pattern, value):
            raise ValueError(f"Value '{value}' does not match pattern '{pattern}'")
        
        return value
    
    def _validate_enum(self, value: Any, params: Dict[str, Any]) -> Any:
        """枚举验证"""
        allowed_values = params.get('values', [])
        if value not in allowed_values:
            raise ValueError(f"Value '{value}' not in allowed values: {allowed_values}")
        
        return value
    
    def _validate_length(self, value: Any, params: Dict[str, Any]) -> Any:
        """长度验证"""
        min_len = params.get('min')
        max_len = params.get('max')
        
        if hasattr(value, '__len__'):
            length = len(value)
            
            if min_len is not None and length < min_len:
                raise ValueError(f"Length {length} is less than minimum {min_len}")
            
            if max_len is not None and length > max_len:
                raise ValueError(f"Length {length} is greater than maximum {max_len}")
        
        return value
    
    def _validate_ip_address(self, value: Any, params: Dict[str, Any]) -> Any:
        """IP地址验证"""
        if not isinstance(value, str):
            value = str(value)
        
        version = params.get('version')  # 4, 6, or None for both
        
        try:
            if version == 4:
                ipaddress.IPv4Address(value)
            elif version == 6:
                ipaddress.IPv6Address(value)
            else:
                ipaddress.ip_address(value)
        except ValueError as e:
            raise ValueError(f"Invalid IP address: {e}")
        
        return value
    
    def _validate_url(self, value: Any, params: Dict[str, Any]) -> Any:
        """URL验证"""
        if not isinstance(value, str):
            value = str(value)
        
        schemes = params.get('schemes', ['http', 'https'])
        
        # 简单的URL验证
        import urllib.parse
        parsed = urllib.parse.urlparse(value)
        
        if not parsed.scheme:
            raise ValueError("URL must have a scheme")
        
        if schemes and parsed.scheme not in schemes:
            raise ValueError(f"URL scheme '{parsed.scheme}' not in allowed schemes: {schemes}")
        
        if not parsed.netloc:
            raise ValueError("URL must have a netloc")
        
        return value
    
    def _validate_file_path(self, value: Any, params: Dict[str, Any]) -> Any:
        """文件路径验证"""
        if not isinstance(value, (str, Path)):
            raise ValueError("File path must be string or Path")
        
        path = Path(value)
        
        must_exist = params.get('must_exist', False)
        must_be_file = params.get('must_be_file', False)
        must_be_dir = params.get('must_be_dir', False)
        
        if must_exist and not path.exists():
            raise ValueError(f"Path does not exist: {path}")
        
        if must_be_file and path.exists() and not path.is_file():
            raise ValueError(f"Path is not a file: {path}")
        
        if must_be_dir and path.exists() and not path.is_dir():
            raise ValueError(f"Path is not a directory: {path}")
        
        return str(path)
    
    def _validate_email(self, value: Any, params: Dict[str, Any]) -> Any:
        """邮箱验证"""
        if not isinstance(value, str):
            value = str(value)
        
        # 简单的邮箱验证
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, value):
            raise ValueError(f"Invalid email address: {value}")
        
        return value
    
    def _validate_custom(self, value: Any, params: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Any:
        """自定义验证"""
        validator_func = params.get('function')
        if not validator_func:
            raise ValueError("Custom validator function is required")
        
        if isinstance(validator_func, str):
            # 如果是字符串，尝试导入函数
            module_name, func_name = validator_func.rsplit('.', 1)
            module = __import__(module_name, fromlist=[func_name])
            validator_func = getattr(module, func_name)
        
        if not callable(validator_func):
            raise ValueError("Custom validator must be callable")
        
        return validator_func(value, context)


class JinjaTemplateEngine(IConfigTemplate):
    """基于 Jinja2 的模板引擎"""
    
    def __init__(self):
        try:
            from jinja2 import Template, Environment
            self.Template = Template
            self.Environment = Environment
            self._env = Environment()
        except ImportError:
            logger.warning("Jinja2 not available, template features disabled")
            self.Template = None
            self.Environment = None
            self._env = None
    
    def render(self, template: str, context: Dict[str, Any]) -> str:
        """渲染模板"""
        if not self.Template:
            return template  # Jinja2不可用时直接返回
        
        try:
            tmpl = self.Template(template)
            return tmpl.render(**context)
        except Exception as e:
            logger.warning(f"Template rendering failed: {e}")
            return template
    
    def extract_variables(self, template: str) -> List[str]:
        """提取模板变量"""
        if not self._env:
            return []
        
        try:
            ast = self._env.parse(template)
            return list(self._env.get_variables(ast))
        except Exception as e:
            logger.warning(f"Failed to extract template variables: {e}")
            return []


class SimpleTemplateEngine(IConfigTemplate):
    """简单模板引擎（不依赖外部库）"""
    
    def __init__(self):
        self._var_pattern = re.compile(r'\$\{([^}]+)\}')
    
    def render(self, template: str, context: Dict[str, Any]) -> str:
        """渲染模板"""
        def replace_var(match):
            var_name = match.group(1)
            return str(self._get_nested_value(context, var_name))
        
        try:
            return self._var_pattern.sub(replace_var, template)
        except Exception as e:
            logger.warning(f"Template rendering failed: {e}")
            return template
    
    def extract_variables(self, template: str) -> List[str]:
        """提取模板变量"""
        matches = self._var_pattern.findall(template)
        return list(set(matches))
    
    def _get_nested_value(self, context: Dict[str, Any], key: str) -> Any:
        """获取嵌套值"""
        keys = key.split('.')
        current = context
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return f"${{{key}}}"  # 变量不存在时保持原样
        
        return current


# 预定义的配置Schema示例
AETHERIUS_CONFIG_SCHEMA = {
    "server": {
        "type": "dict",
        "properties": {
            "host": {
                "type": "str",
                "rules": [
                    {
                        "type": "ip_address",
                        "parameters": {},
                        "message": "Invalid IP address"
                    }
                ]
            },
            "port": {
                "type": "int", 
                "rules": [
                    {
                        "type": "range",
                        "parameters": {"min": 1, "max": 65535},
                        "message": "Port must be between 1 and 65535"
                    }
                ]
            },
            "max_players": {
                "type": "int",
                "rules": [
                    {
                        "type": "range", 
                        "parameters": {"min": 1, "max": 1000},
                        "message": "Max players must be between 1 and 1000"
                    }
                ]
            }
        }
    },
    "database": {
        "type": "dict",
        "properties": {
            "url": {
                "type": "str",
                "rules": [
                    {
                        "type": "url",
                        "parameters": {"schemes": ["sqlite", "postgresql", "mysql"]},
                        "message": "Invalid database URL"
                    }
                ]
            }
        }
    },
    "logging": {
        "type": "dict", 
        "properties": {
            "level": {
                "type": "str",
                "rules": [
                    {
                        "type": "enum",
                        "parameters": {"values": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]},
                        "message": "Invalid log level"
                    }
                ]
            },
            "file": {
                "type": "str",
                "rules": [
                    {
                        "type": "file_path",
                        "parameters": {"must_be_file": False},
                        "message": "Invalid log file path"
                    }
                ]
            }
        }
    },
    # 通配符支持
    "plugins": {
        "*": {
            "type": "dict",
            "properties": {
                "enabled": {
                    "type": "bool"
                },
                "config": {
                    "type": "dict"
                }
            }
        }
    }
}