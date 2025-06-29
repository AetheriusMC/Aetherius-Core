"""
安全系统提供者实现

提供基于数据库的认证和授权实现
"""

import asyncio
import sqlite3
import json
from typing import Optional, Set, Dict, Any, List
from datetime import datetime
from pathlib import Path
import logging

from . import (
    IAuthenticationProvider, IAuthorizationProvider, ISecurityAuditor,
    User, Role, Permission, SecurityContext, PasswordUtils,
    ResourceType, PermissionType
)

logger = logging.getLogger(__name__)


class DatabaseAuthenticationProvider(IAuthenticationProvider):
    """基于数据库的认证提供者"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    display_name TEXT,
                    email TEXT,
                    password_hash TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    is_system_user BOOLEAN DEFAULT 0,
                    last_login TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_roles (
                    username TEXT,
                    role_name TEXT,
                    PRIMARY KEY (username, role_name),
                    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_permissions (
                    username TEXT,
                    permission_name TEXT,
                    resource_type TEXT,
                    permission_type TEXT,
                    resource_id TEXT,
                    scope TEXT,
                    conditions TEXT DEFAULT '{}',
                    PRIMARY KEY (username, permission_name),
                    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
                )
            """)
            
            # 角色表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS roles (
                    name TEXT PRIMARY KEY,
                    display_name TEXT,
                    description TEXT,
                    is_system_role BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            # 角色权限表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS role_permissions (
                    role_name TEXT,
                    permission_name TEXT,
                    resource_type TEXT,
                    permission_type TEXT,
                    resource_id TEXT,
                    scope TEXT,
                    conditions TEXT DEFAULT '{}',
                    PRIMARY KEY (role_name, permission_name),
                    FOREIGN KEY (role_name) REFERENCES roles(name) ON DELETE CASCADE
                )
            """)
            
            # 角色层次表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS role_hierarchy (
                    role_name TEXT,
                    parent_role TEXT,
                    PRIMARY KEY (role_name, parent_role),
                    FOREIGN KEY (role_name) REFERENCES roles(name) ON DELETE CASCADE,
                    FOREIGN KEY (parent_role) REFERENCES roles(name) ON DELETE CASCADE
                )
            """)
    
    async def authenticate(self, username: str, password: str, **kwargs) -> Optional[User]:
        """用户认证"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM users WHERE username = ? AND is_active = 1",
                    (username,)
                )
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                # 验证密码
                if not PasswordUtils.verify_password(password, row['password_hash']):
                    return None
                
                # 获取角色
                cursor = conn.execute(
                    "SELECT role_name FROM user_roles WHERE username = ?",
                    (username,)
                )
                roles = {row[0] for row in cursor.fetchall()}
                
                # 获取直接权限
                cursor = conn.execute(
                    "SELECT * FROM user_permissions WHERE username = ?",
                    (username,)
                )
                permissions = set()
                for perm_row in cursor.fetchall():
                    # 正确处理条件字段：从JSON字典转换为元组的元组
                    conditions_dict = json.loads(perm_row['conditions'] or '{}')
                    conditions_tuple = tuple(conditions_dict.items()) if conditions_dict else ()
                    
                    permission = Permission(
                        name=perm_row['permission_name'],
                        resource_type=ResourceType(perm_row['resource_type']),
                        permission_type=PermissionType(perm_row['permission_type']),
                        resource_id=perm_row['resource_id'],
                        scope=perm_row['scope'],
                        conditions=conditions_tuple
                    )
                    permissions.add(permission)
                
                # 创建用户对象
                user = User(
                    username=row['username'],
                    display_name=row['display_name'],
                    email=row['email'],
                    password_hash=row['password_hash'],
                    roles=roles,
                    permissions=permissions,
                    is_active=bool(row['is_active']),
                    is_system_user=bool(row['is_system_user']),
                    last_login=datetime.fromisoformat(row['last_login']) if row['last_login'] else None,
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
                    metadata=json.loads(row['metadata'] or '{}')
                )
                
                return user
        
        except Exception as e:
            logger.error(f"Authentication error for user {username}: {e}")
            return None
    
    async def get_user(self, username: str) -> Optional[User]:
        """获取用户信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                # 获取角色
                cursor = conn.execute(
                    "SELECT role_name FROM user_roles WHERE username = ?",
                    (username,)
                )
                roles = {row[0] for row in cursor.fetchall()}
                
                # 获取权限
                cursor = conn.execute(
                    "SELECT * FROM user_permissions WHERE username = ?",
                    (username,)
                )
                permissions = set()
                for perm_row in cursor.fetchall():
                    # 正确处理条件字段：从JSON字典转换为元组的元组
                    conditions_dict = json.loads(perm_row['conditions'] or '{}')
                    conditions_tuple = tuple(conditions_dict.items()) if conditions_dict else ()
                    
                    permission = Permission(
                        name=perm_row['permission_name'],
                        resource_type=ResourceType(perm_row['resource_type']),
                        permission_type=PermissionType(perm_row['permission_type']),
                        resource_id=perm_row['resource_id'],
                        scope=perm_row['scope'],
                        conditions=conditions_tuple
                    )
                    permissions.add(permission)
                
                user = User(
                    username=row['username'],
                    display_name=row['display_name'],
                    email=row['email'],
                    password_hash=row['password_hash'],
                    roles=roles,
                    permissions=permissions,
                    is_active=bool(row['is_active']),
                    is_system_user=bool(row['is_system_user']),
                    last_login=datetime.fromisoformat(row['last_login']) if row['last_login'] else None,
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
                    metadata=json.loads(row['metadata'] or '{}')
                )
                
                return user
        
        except Exception as e:
            logger.error(f"Error getting user {username}: {e}")
            return None
    
    async def create_user(self, user: User, password: str) -> bool:
        """创建用户"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 插入用户
                conn.execute("""
                    INSERT INTO users (
                        username, display_name, email, password_hash,
                        is_active, is_system_user, created_at, updated_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user.username,
                    user.display_name,
                    user.email,
                    user.password_hash,
                    user.is_active,
                    user.is_system_user,
                    user.created_at.isoformat() if user.created_at else datetime.utcnow().isoformat(),
                    user.updated_at.isoformat() if user.updated_at else datetime.utcnow().isoformat(),
                    json.dumps(user.metadata)
                ))
                
                # 插入角色
                for role_name in user.roles:
                    conn.execute(
                        "INSERT INTO user_roles (username, role_name) VALUES (?, ?)",
                        (user.username, role_name)
                    )
                
                # 插入权限
                for permission in user.permissions:
                    conn.execute("""
                        INSERT INTO user_permissions (
                            username, permission_name, resource_type, permission_type,
                            resource_id, scope, conditions
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        user.username,
                        permission.name,
                        permission.resource_type.value,
                        permission.permission_type.value,
                        permission.resource_id,
                        permission.scope,
                        json.dumps(permission.conditions)
                    ))
                
                return True
        
        except Exception as e:
            logger.error(f"Error creating user {user.username}: {e}")
            return False
    
    async def update_user(self, user: User) -> bool:
        """更新用户信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 更新用户基本信息
                conn.execute("""
                    UPDATE users SET
                        display_name = ?, email = ?, password_hash = ?,
                        is_active = ?, last_login = ?, updated_at = ?, metadata = ?
                    WHERE username = ?
                """, (
                    user.display_name,
                    user.email,
                    user.password_hash,
                    user.is_active,
                    user.last_login.isoformat() if user.last_login else None,
                    datetime.utcnow().isoformat(),
                    json.dumps(user.metadata),
                    user.username
                ))
                
                # 更新角色（先删除再插入）
                conn.execute("DELETE FROM user_roles WHERE username = ?", (user.username,))
                for role_name in user.roles:
                    conn.execute(
                        "INSERT INTO user_roles (username, role_name) VALUES (?, ?)",
                        (user.username, role_name)
                    )
                
                # 更新权限（先删除再插入）
                conn.execute("DELETE FROM user_permissions WHERE username = ?", (user.username,))
                for permission in user.permissions:
                    conn.execute("""
                        INSERT INTO user_permissions (
                            username, permission_name, resource_type, permission_type,
                            resource_id, scope, conditions
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        user.username,
                        permission.name,
                        permission.resource_type.value,
                        permission.permission_type.value,
                        permission.resource_id,
                        permission.scope,
                        json.dumps(permission.conditions)
                    ))
                
                return True
        
        except Exception as e:
            logger.error(f"Error updating user {user.username}: {e}")
            return False
    
    async def delete_user(self, username: str) -> bool:
        """删除用户"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM users WHERE username = ?", (username,))
                return True
        
        except Exception as e:
            logger.error(f"Error deleting user {username}: {e}")
            return False


class DatabaseAuthorizationProvider(IAuthorizationProvider):
    """基于数据库的授权提供者"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS roles (
                    name TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    description TEXT,
                    is_system_role BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS role_permissions (
                    role_name TEXT,
                    permission_name TEXT,
                    resource_type TEXT,
                    permission_type TEXT,
                    resource_id TEXT,
                    scope TEXT,
                    conditions TEXT DEFAULT '{}',
                    PRIMARY KEY (role_name, permission_name),
                    FOREIGN KEY (role_name) REFERENCES roles(name) ON DELETE CASCADE
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS role_hierarchy (
                    role_name TEXT,
                    parent_role TEXT,
                    PRIMARY KEY (role_name, parent_role),
                    FOREIGN KEY (role_name) REFERENCES roles(name) ON DELETE CASCADE,
                    FOREIGN KEY (parent_role) REFERENCES roles(name) ON DELETE CASCADE
                )
            """)
    
    async def check_permission(self, 
                              user: User, 
                              permission: Permission,
                              context: Optional[SecurityContext] = None) -> bool:
        """检查用户权限"""
        # 首先检查用户直接权限
        if user.has_permission(permission):
            return True
        
        # 然后检查角色权限
        try:
            with sqlite3.connect(self.db_path) as conn:
                for role_name in user.roles:
                    # 获取角色的所有权限（包括继承的）
                    role_permissions = await self._get_role_permissions_recursive(role_name, conn)
                    
                    for role_permission in role_permissions:
                        if role_permission.matches(permission):
                            return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error checking permission for user {user.username}: {e}")
            return False
    
    async def get_user_permissions(self, user: User) -> Set[Permission]:
        """获取用户所有权限"""
        permissions = set(user.permissions)  # 直接权限
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                for role_name in user.roles:
                    role_permissions = await self._get_role_permissions_recursive(role_name, conn)
                    permissions.update(role_permissions)
            
            return permissions
        
        except Exception as e:
            logger.error(f"Error getting permissions for user {user.username}: {e}")
            return permissions
    
    async def get_role(self, role_name: str) -> Optional[Role]:
        """获取角色信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM roles WHERE name = ?", (role_name,))
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                # 获取权限
                cursor = conn.execute(
                    "SELECT * FROM role_permissions WHERE role_name = ?",
                    (role_name,)
                )
                permissions = set()
                for perm_row in cursor.fetchall():
                    # 正确处理条件字段：从JSON字典转换为元组的元组
                    conditions_dict = json.loads(perm_row['conditions'] or '{}')
                    conditions_tuple = tuple(conditions_dict.items()) if conditions_dict else ()
                    
                    permission = Permission(
                        name=perm_row['permission_name'],
                        resource_type=ResourceType(perm_row['resource_type']),
                        permission_type=PermissionType(perm_row['permission_type']),
                        resource_id=perm_row['resource_id'],
                        scope=perm_row['scope'],
                        conditions=conditions_tuple
                    )
                    permissions.add(permission)
                
                # 获取父角色
                cursor = conn.execute(
                    "SELECT parent_role FROM role_hierarchy WHERE role_name = ?",
                    (role_name,)
                )
                parent_roles = {row[0] for row in cursor.fetchall()}
                
                role = Role(
                    name=row['name'],
                    display_name=row['display_name'],
                    description=row['description'],
                    permissions=permissions,
                    parent_roles=parent_roles,
                    is_system_role=bool(row['is_system_role']),
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                )
                
                return role
        
        except Exception as e:
            logger.error(f"Error getting role {role_name}: {e}")
            return None
    
    async def create_role(self, role: Role) -> bool:
        """创建角色"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 插入角色
                conn.execute("""
                    INSERT INTO roles (
                        name, display_name, description, is_system_role,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    role.name,
                    role.display_name,
                    role.description,
                    role.is_system_role,
                    role.created_at.isoformat() if role.created_at else datetime.utcnow().isoformat(),
                    role.updated_at.isoformat() if role.updated_at else datetime.utcnow().isoformat()
                ))
                
                # 插入权限
                for permission in role.permissions:
                    conn.execute("""
                        INSERT INTO role_permissions (
                            role_name, permission_name, resource_type, permission_type,
                            resource_id, scope, conditions
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        role.name,
                        permission.name,
                        permission.resource_type.value,
                        permission.permission_type.value,
                        permission.resource_id,
                        permission.scope,
                        json.dumps(permission.conditions)
                    ))
                
                # 插入父角色关系
                for parent_role in role.parent_roles:
                    conn.execute(
                        "INSERT INTO role_hierarchy (role_name, parent_role) VALUES (?, ?)",
                        (role.name, parent_role)
                    )
                
                return True
        
        except Exception as e:
            logger.error(f"Error creating role {role.name}: {e}")
            return False
    
    async def update_role(self, role: Role) -> bool:
        """更新角色"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 更新角色基本信息
                conn.execute("""
                    UPDATE roles SET
                        display_name = ?, description = ?, updated_at = ?
                    WHERE name = ?
                """, (
                    role.display_name,
                    role.description,
                    datetime.utcnow().isoformat(),
                    role.name
                ))
                
                # 更新权限（先删除再插入）
                conn.execute("DELETE FROM role_permissions WHERE role_name = ?", (role.name,))
                for permission in role.permissions:
                    conn.execute("""
                        INSERT INTO role_permissions (
                            role_name, permission_name, resource_type, permission_type,
                            resource_id, scope, conditions
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        role.name,
                        permission.name,
                        permission.resource_type.value,
                        permission.permission_type.value,
                        permission.resource_id,
                        permission.scope,
                        json.dumps(permission.conditions)
                    ))
                
                # 更新父角色关系
                conn.execute("DELETE FROM role_hierarchy WHERE role_name = ?", (role.name,))
                for parent_role in role.parent_roles:
                    conn.execute(
                        "INSERT INTO role_hierarchy (role_name, parent_role) VALUES (?, ?)",
                        (role.name, parent_role)
                    )
                
                return True
        
        except Exception as e:
            logger.error(f"Error updating role {role.name}: {e}")
            return False
    
    async def delete_role(self, role_name: str) -> bool:
        """删除角色"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM roles WHERE name = ?", (role_name,))
                return True
        
        except Exception as e:
            logger.error(f"Error deleting role {role_name}: {e}")
            return False
    
    async def _get_role_permissions_recursive(self, role_name: str, conn) -> Set[Permission]:
        """递归获取角色权限（包括继承的）"""
        permissions = set()
        visited = set()
        
        def _collect_permissions(current_role: str):
            if current_role in visited:
                return  # 避免循环
            
            visited.add(current_role)
            
            # 获取当前角色的直接权限
            cursor = conn.execute(
                "SELECT * FROM role_permissions WHERE role_name = ?",
                (current_role,)
            )
            for perm_row in cursor.fetchall():
                permission = Permission(
                    name=perm_row['permission_name'],
                    resource_type=perm_row['resource_type'],
                    permission_type=perm_row['permission_type'],
                    resource_id=perm_row['resource_id'],
                    scope=perm_row['scope'],
                    conditions=json.loads(perm_row['conditions'] or '{}')
                )
                permissions.add(permission)
            
            # 递归获取父角色权限
            cursor = conn.execute(
                "SELECT parent_role FROM role_hierarchy WHERE role_name = ?",
                (current_role,)
            )
            for parent_row in cursor.fetchall():
                _collect_permissions(parent_row[0])
        
        _collect_permissions(role_name)
        return permissions


class FileSecurityAuditor(ISecurityAuditor):
    """基于文件的安全审计器"""
    
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 设置文件日志
        self.logger = logging.getLogger("security_audit")
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    async def log_authentication(self, 
                                username: str, 
                                success: bool, 
                                ip_address: Optional[str] = None,
                                user_agent: Optional[str] = None):
        """记录认证事件"""
        message = f"Authentication {'SUCCESS' if success else 'FAILURE'} for user '{username}'"
        if ip_address:
            message += f" from IP {ip_address}"
        if user_agent:
            message += f" with user agent '{user_agent}'"
        
        if success:
            self.logger.info(message)
        else:
            self.logger.warning(message)
    
    async def log_authorization(self, 
                               username: str, 
                               permission: Permission, 
                               granted: bool,
                               context: Optional[SecurityContext] = None):
        """记录授权事件"""
        message = f"Authorization {'GRANTED' if granted else 'DENIED'} for user '{username}' permission '{permission}'"
        if context and context.ip_address:
            message += f" from IP {context.ip_address}"
        
        if granted:
            self.logger.info(message)
        else:
            self.logger.warning(message)
    
    async def log_security_event(self, 
                                event_type: str, 
                                description: str, 
                                user: Optional[str] = None,
                                severity: str = "info",
                                metadata: Optional[Dict[str, Any]] = None):
        """记录安全事件"""
        message = f"Security event [{event_type}]: {description}"
        if user:
            message += f" (user: {user})"
        if metadata:
            message += f" metadata: {json.dumps(metadata)}"
        
        if severity == "info":
            self.logger.info(message)
        elif severity == "warning":
            self.logger.warning(message)
        elif severity == "error":
            self.logger.error(message)
        else:
            self.logger.critical(message)