"""
Aetherius Core 安全框架

提供全面的安全管理功能，包括：
- 用户认证和授权
- 权限管理和访问控制
- 安全审计和监控
- 密码策略和加密
- API安全和令牌管理
- 扩展沙箱和隔离
"""

from typing import Any, Dict, List, Optional, Set, Union, Protocol, TypeVar, Tuple
from abc import ABC, abstractmethod
from enum import Enum, Flag, auto
from dataclasses import dataclass, field
import hashlib
import secrets
import time
from datetime import datetime, timedelta

__all__ = [
    'SecurityLevel', 'Permission', 'Role', 'User', 'SecurityContext',
    'IAuthenticationProvider', 'IAuthorizationProvider', 'ISecurityAuditor',
    'SecurityError', 'AuthenticationError', 'AuthorizationError',
    'permission', 'require_permission', 'require_role', 'secure'
]

T = TypeVar('T')


class SecurityLevel(Enum):
    """安全级别枚举"""
    PUBLIC = "public"           # 公开访问
    AUTHENTICATED = "authenticated"  # 需要认证
    AUTHORIZED = "authorized"   # 需要授权
    RESTRICTED = "restricted"   # 受限访问
    CONFIDENTIAL = "confidential"  # 机密级别
    SECRET = "secret"          # 秘密级别


class PermissionType(Enum):
    """权限类型枚举"""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    ADMIN = "admin"
    SYSTEM = "system"


class ResourceType(Enum):
    """资源类型枚举"""
    SERVER = "server"
    PLAYER = "player"
    FILE = "file"
    CONFIG = "config"
    PLUGIN = "plugin"
    COMPONENT = "component"
    API = "api"
    CONSOLE = "console"
    DATABASE = "database"


@dataclass(frozen=True)
class Permission:
    """权限定义"""
    name: str                           # 权限名称
    resource_type: ResourceType         # 资源类型
    permission_type: PermissionType     # 权限类型
    resource_id: Optional[str] = None   # 具体资源ID（可选）
    scope: Optional[str] = None         # 权限范围
    conditions: Tuple[Tuple[str, Any], ...] = ()  # 权限条件（使用tuple使其可哈希）
    
    def __str__(self):
        scope_str = f":{self.scope}" if self.scope else ""
        resource_str = f":{self.resource_id}" if self.resource_id else ""
        return f"{self.resource_type.value}.{self.permission_type.value}{scope_str}{resource_str}"
    
    def matches(self, required_permission: 'Permission') -> bool:
        """检查权限是否匹配"""
        # 基本匹配
        if (self.resource_type != required_permission.resource_type or
            self.permission_type != required_permission.permission_type):
            return False
        
        # 作用域匹配
        if required_permission.scope and self.scope != required_permission.scope:
            return False
        
        # 资源ID匹配
        if (required_permission.resource_id and 
            self.resource_id and 
            self.resource_id != required_permission.resource_id):
            return False
        
        # 条件匹配
        required_conditions = dict(required_permission.conditions)
        self_conditions = dict(self.conditions)
        for key, value in required_conditions.items():
            if key not in self_conditions or self_conditions[key] != value:
                return False
        
        return True


@dataclass
class Role:
    """角色定义"""
    name: str
    display_name: str
    description: Optional[str] = None
    permissions: Set[Permission] = field(default_factory=set)
    parent_roles: Set[str] = field(default_factory=set)  # 继承的父角色
    is_system_role: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def has_permission(self, required_permission: Permission) -> bool:
        """检查角色是否具有指定权限"""
        for permission in self.permissions:
            if permission.matches(required_permission):
                return True
        return False
    
    def add_permission(self, permission: Permission):
        """添加权限"""
        self.permissions.add(permission)
        self.updated_at = datetime.utcnow()
    
    def remove_permission(self, permission: Permission):
        """移除权限"""
        self.permissions.discard(permission)
        self.updated_at = datetime.utcnow()


@dataclass
class User:
    """用户定义"""
    username: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    password_hash: Optional[str] = None
    roles: Set[str] = field(default_factory=set)
    permissions: Set[Permission] = field(default_factory=set)  # 直接权限
    is_active: bool = True
    is_system_user: bool = False
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_role(self, role_name: str) -> bool:
        """检查用户是否具有指定角色"""
        return role_name in self.roles
    
    def add_role(self, role_name: str):
        """添加角色"""
        self.roles.add(role_name)
        self.updated_at = datetime.utcnow()
    
    def remove_role(self, role_name: str):
        """移除角色"""
        self.roles.discard(role_name)
        self.updated_at = datetime.utcnow()
    
    def has_permission(self, required_permission: Permission) -> bool:
        """检查用户是否具有指定权限（直接权限）"""
        for permission in self.permissions:
            if permission.matches(required_permission):
                return True
        return False


@dataclass
class SecurityContext:
    """安全上下文"""
    user: Optional[User] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    authentication_method: Optional[str] = None
    session_start: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    security_level: SecurityLevel = SecurityLevel.PUBLIC
    additional_claims: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        return self.user is not None
    
    @property
    def is_anonymous(self) -> bool:
        """检查是否匿名"""
        return self.user is None
    
    def update_activity(self):
        """更新活动时间"""
        self.last_activity = datetime.utcnow()


class IAuthenticationProvider(Protocol):
    """认证提供者接口"""
    
    async def authenticate(self, 
                          username: str, 
                          password: str, 
                          **kwargs) -> Optional[User]:
        """用户认证"""
        ...
    
    async def get_user(self, username: str) -> Optional[User]:
        """获取用户信息"""
        ...
    
    async def create_user(self, user: User, password: str) -> bool:
        """创建用户"""
        ...
    
    async def update_user(self, user: User) -> bool:
        """更新用户信息"""
        ...
    
    async def delete_user(self, username: str) -> bool:
        """删除用户"""
        ...


class IAuthorizationProvider(Protocol):
    """授权提供者接口"""
    
    async def check_permission(self, 
                              user: User, 
                              permission: Permission,
                              context: Optional[SecurityContext] = None) -> bool:
        """检查用户权限"""
        ...
    
    async def get_user_permissions(self, user: User) -> Set[Permission]:
        """获取用户所有权限"""
        ...
    
    async def get_role(self, role_name: str) -> Optional[Role]:
        """获取角色信息"""
        ...
    
    async def create_role(self, role: Role) -> bool:
        """创建角色"""
        ...
    
    async def update_role(self, role: Role) -> bool:
        """更新角色"""
        ...
    
    async def delete_role(self, role_name: str) -> bool:
        """删除角色"""
        ...


class ISecurityAuditor(Protocol):
    """安全审计接口"""
    
    async def log_authentication(self, 
                                username: str, 
                                success: bool, 
                                ip_address: Optional[str] = None,
                                user_agent: Optional[str] = None):
        """记录认证事件"""
        ...
    
    async def log_authorization(self, 
                               username: str, 
                               permission: Permission, 
                               granted: bool,
                               context: Optional[SecurityContext] = None):
        """记录授权事件"""
        ...
    
    async def log_security_event(self, 
                                event_type: str, 
                                description: str, 
                                user: Optional[str] = None,
                                severity: str = "info",
                                metadata: Optional[Dict[str, Any]] = None):
        """记录安全事件"""
        ...


class SecurityError(Exception):
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


# 内置权限定义
class BuiltinPermissions:
    """内置权限定义"""
    
    # 服务器权限
    SERVER_START = Permission("server.start", ResourceType.SERVER, PermissionType.EXECUTE)
    SERVER_STOP = Permission("server.stop", ResourceType.SERVER, PermissionType.EXECUTE)
    SERVER_RESTART = Permission("server.restart", ResourceType.SERVER, PermissionType.EXECUTE)
    SERVER_CONSOLE = Permission("server.console", ResourceType.CONSOLE, PermissionType.EXECUTE)
    SERVER_STATUS = Permission("server.status", ResourceType.SERVER, PermissionType.READ)
    
    # 玩家权限
    PLAYER_LIST = Permission("player.list", ResourceType.PLAYER, PermissionType.READ)
    PLAYER_INFO = Permission("player.info", ResourceType.PLAYER, PermissionType.READ)
    PLAYER_KICK = Permission("player.kick", ResourceType.PLAYER, PermissionType.EXECUTE)
    PLAYER_BAN = Permission("player.ban", ResourceType.PLAYER, PermissionType.EXECUTE)
    PLAYER_MANAGE = Permission("player.manage", ResourceType.PLAYER, PermissionType.ADMIN)
    
    # 文件权限
    FILE_READ = Permission("file.read", ResourceType.FILE, PermissionType.READ)
    FILE_WRITE = Permission("file.write", ResourceType.FILE, PermissionType.WRITE)
    FILE_DELETE = Permission("file.delete", ResourceType.FILE, PermissionType.DELETE)
    FILE_EXECUTE = Permission("file.execute", ResourceType.FILE, PermissionType.EXECUTE)
    
    # 配置权限
    CONFIG_READ = Permission("config.read", ResourceType.CONFIG, PermissionType.READ)
    CONFIG_WRITE = Permission("config.write", ResourceType.CONFIG, PermissionType.WRITE)
    CONFIG_ADMIN = Permission("config.admin", ResourceType.CONFIG, PermissionType.ADMIN)
    
    # 插件权限
    PLUGIN_LIST = Permission("plugin.list", ResourceType.PLUGIN, PermissionType.READ)
    PLUGIN_LOAD = Permission("plugin.load", ResourceType.PLUGIN, PermissionType.EXECUTE)
    PLUGIN_UNLOAD = Permission("plugin.unload", ResourceType.PLUGIN, PermissionType.EXECUTE)
    PLUGIN_MANAGE = Permission("plugin.manage", ResourceType.PLUGIN, PermissionType.ADMIN)
    
    # 组件权限
    COMPONENT_LIST = Permission("component.list", ResourceType.COMPONENT, PermissionType.READ)
    COMPONENT_START = Permission("component.start", ResourceType.COMPONENT, PermissionType.EXECUTE)
    COMPONENT_STOP = Permission("component.stop", ResourceType.COMPONENT, PermissionType.EXECUTE)
    COMPONENT_MANAGE = Permission("component.manage", ResourceType.COMPONENT, PermissionType.ADMIN)
    
    # API权限
    API_READ = Permission("api.read", ResourceType.API, PermissionType.READ)
    API_WRITE = Permission("api.write", ResourceType.API, PermissionType.WRITE)
    API_ADMIN = Permission("api.admin", ResourceType.API, PermissionType.ADMIN)
    
    # 系统权限
    SYSTEM_ADMIN = Permission("system.admin", ResourceType.SERVER, PermissionType.SYSTEM)
    SYSTEM_USER_MANAGE = Permission("system.user.manage", ResourceType.SERVER, PermissionType.ADMIN)
    SYSTEM_ROLE_MANAGE = Permission("system.role.manage", ResourceType.SERVER, PermissionType.ADMIN)


# 内置角色定义
class BuiltinRoles:
    """内置角色定义"""
    
    # 超级管理员
    SUPER_ADMIN = Role(
        name="super_admin",
        display_name="超级管理员",
        description="拥有所有权限的超级管理员",
        permissions={
            BuiltinPermissions.SYSTEM_ADMIN,
            BuiltinPermissions.SYSTEM_USER_MANAGE,
            BuiltinPermissions.SYSTEM_ROLE_MANAGE,
        },
        is_system_role=True
    )
    
    # 服务器管理员
    SERVER_ADMIN = Role(
        name="server_admin",
        display_name="服务器管理员",
        description="服务器管理权限",
        permissions={
            BuiltinPermissions.SERVER_START,
            BuiltinPermissions.SERVER_STOP,
            BuiltinPermissions.SERVER_RESTART,
            BuiltinPermissions.SERVER_CONSOLE,
            BuiltinPermissions.SERVER_STATUS,
            BuiltinPermissions.CONFIG_READ,
            BuiltinPermissions.CONFIG_WRITE,
        },
        is_system_role=True
    )
    
    # 玩家管理员
    PLAYER_ADMIN = Role(
        name="player_admin",
        display_name="玩家管理员",
        description="玩家管理权限",
        permissions={
            BuiltinPermissions.PLAYER_LIST,
            BuiltinPermissions.PLAYER_INFO,
            BuiltinPermissions.PLAYER_KICK,
            BuiltinPermissions.PLAYER_BAN,
            BuiltinPermissions.PLAYER_MANAGE,
        },
        is_system_role=True
    )
    
    # 插件管理员
    PLUGIN_ADMIN = Role(
        name="plugin_admin",
        display_name="插件管理员",
        description="插件管理权限",
        permissions={
            BuiltinPermissions.PLUGIN_LIST,
            BuiltinPermissions.PLUGIN_LOAD,
            BuiltinPermissions.PLUGIN_UNLOAD,
            BuiltinPermissions.PLUGIN_MANAGE,
            BuiltinPermissions.COMPONENT_LIST,
            BuiltinPermissions.COMPONENT_START,
            BuiltinPermissions.COMPONENT_STOP,
            BuiltinPermissions.COMPONENT_MANAGE,
        },
        is_system_role=True
    )
    
    # 只读用户
    READONLY_USER = Role(
        name="readonly_user",
        display_name="只读用户",
        description="只读权限用户",
        permissions={
            BuiltinPermissions.SERVER_STATUS,
            BuiltinPermissions.PLAYER_LIST,
            BuiltinPermissions.PLAYER_INFO,
            BuiltinPermissions.CONFIG_READ,
            BuiltinPermissions.PLUGIN_LIST,
            BuiltinPermissions.COMPONENT_LIST,
        },
        is_system_role=True
    )


# 装饰器和工具函数

def permission(permission_obj: Permission):
    """权限装饰器"""
    def decorator(func):
        if not hasattr(func, '_required_permissions'):
            func._required_permissions = []
        func._required_permissions.append(permission_obj)
        return func
    return decorator


def require_permission(permission_obj: Permission):
    """要求权限装饰器"""
    return permission(permission_obj)


def require_role(role_name: str):
    """要求角色装饰器"""
    def decorator(func):
        if not hasattr(func, '_required_roles'):
            func._required_roles = []
        func._required_roles.append(role_name)
        return func
    return decorator


def secure(security_level: SecurityLevel = SecurityLevel.AUTHENTICATED):
    """安全级别装饰器"""
    def decorator(func):
        func._security_level = security_level
        return func
    return decorator


# 密码工具

class PasswordUtils:
    """密码工具类"""
    
    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """哈希密码"""
        if salt is None:
            salt = secrets.token_hex(32)
        
        # 使用PBKDF2算法
        key = hashlib.pbkdf2_hmac('sha256', 
                                password.encode('utf-8'), 
                                salt.encode('utf-8'), 
                                100000)  # 100,000 iterations
        
        return salt + key.hex(), salt
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """验证密码"""
        try:
            if len(hashed_password) < 64:
                return False
            
            salt = hashed_password[:64]
            stored_key = hashed_password[64:]
            
            key = hashlib.pbkdf2_hmac('sha256',
                                    password.encode('utf-8'),
                                    salt.encode('utf-8'),
                                    100000)
            
            return key.hex() == stored_key
        except Exception:
            return False
    
    @staticmethod
    def generate_password(length: int = 12) -> str:
        """生成随机密码"""
        import string
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @staticmethod
    def check_password_strength(password: str) -> Dict[str, Any]:
        """检查密码强度"""
        import re
        
        checks = {
            'length': len(password) >= 8,
            'uppercase': bool(re.search(r'[A-Z]', password)),
            'lowercase': bool(re.search(r'[a-z]', password)),
            'digit': bool(re.search(r'\d', password)),
            'special': bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password)),
        }
        
        score = sum(checks.values())
        strength = "weak"
        
        if score >= 4:
            strength = "strong"
        elif score >= 3:
            strength = "medium"
        
        return {
            'strength': strength,
            'score': score,
            'checks': checks,
            'suggestions': PasswordUtils._get_password_suggestions(checks)
        }
    
    @staticmethod
    def _get_password_suggestions(checks: Dict[str, bool]) -> List[str]:
        """获取密码改进建议"""
        suggestions = []
        
        if not checks['length']:
            suggestions.append("密码长度至少8位")
        if not checks['uppercase']:
            suggestions.append("包含大写字母")
        if not checks['lowercase']:
            suggestions.append("包含小写字母")
        if not checks['digit']:
            suggestions.append("包含数字")
        if not checks['special']:
            suggestions.append("包含特殊字符")
        
        return suggestions


# 令牌工具

class TokenUtils:
    """令牌工具类"""
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """生成随机令牌"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_api_key() -> str:
        """生成API密钥"""
        return f"ak_{secrets.token_urlsafe(32)}"
    
    @staticmethod
    def generate_session_id() -> str:
        """生成会话ID"""
        return f"sess_{secrets.token_urlsafe(24)}"