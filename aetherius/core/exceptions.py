"""
Aetherius Core 异常定义

定义所有核心系统使用的异常类
"""

from typing import Optional, Any, Dict


class AetheriusError(Exception):
    """Aetherius 基础异常类"""
    
    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


# 配置相关异常
class ConfigError(AetheriusError):
    """配置错误基类"""
    pass


class ConfigValidationError(ConfigError):
    """配置验证错误"""
    pass


class ConfigSourceError(ConfigError):
    """配置源错误"""
    pass


# 依赖注入相关异常
class DependencyError(AetheriusError):
    """依赖注入错误基类"""
    pass


class DependencyResolutionError(DependencyError):
    """依赖解析错误"""
    pass


class CircularDependencyError(DependencyError):
    """循环依赖错误"""
    pass


class ServiceNotRegisteredError(DependencyError):
    """服务未注册错误"""
    pass


class InvalidServiceRegistrationError(DependencyError):
    """无效服务注册错误"""
    pass


# 扩展相关异常
class ExtensionError(AetheriusError):
    """扩展错误基类"""
    pass


class ExtensionLoadError(ExtensionError):
    """扩展加载错误"""
    pass


class ExtensionDependencyError(ExtensionError):
    """扩展依赖错误"""
    pass


class ExtensionVersionError(ExtensionError):
    """扩展版本兼容性错误"""
    pass


# 安全相关异常
class SecurityError(AetheriusError):
    """安全错误基类"""
    pass


class AuthenticationError(SecurityError):
    """认证错误"""
    pass


class AuthorizationError(SecurityError):
    """授权错误"""
    pass


class SecurityViolationError(SecurityError):
    """安全违规错误"""
    pass


# 事件相关异常
class EventError(AetheriusError):
    """事件错误基类"""
    pass


class EventHandlerError(EventError):
    """事件处理器错误"""
    pass


# 监控相关异常
class MonitoringError(AetheriusError):
    """监控错误基类"""
    pass


class MetricsError(MonitoringError):
    """指标错误"""
    pass


class HealthCheckError(MonitoringError):
    """健康检查错误"""
    pass