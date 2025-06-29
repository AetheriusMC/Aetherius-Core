"""
安全管理器实现

提供完整的安全管理功能实现
"""

import asyncio
import time
import threading
from typing import Dict, List, Optional, Set, Any, Tuple, Union
from datetime import datetime, timedelta
from collections import defaultdict, deque
import logging
import json
import weakref

from . import (
    SecurityLevel, Permission, Role, User, SecurityContext,
    IAuthenticationProvider, IAuthorizationProvider, ISecurityAuditor,
    SecurityError, AuthenticationError, AuthorizationError,
    BuiltinPermissions, BuiltinRoles, PasswordUtils, TokenUtils
)

logger = logging.getLogger(__name__)


class SecurityManager:
    """安全管理器"""
    
    def __init__(self, 
                 auth_provider: IAuthenticationProvider,
                 authz_provider: IAuthorizationProvider,
                 auditor: Optional[ISecurityAuditor] = None,
                 config: Optional[Dict[str, Any]] = None):
        self.auth_provider = auth_provider
        self.authz_provider = authz_provider
        self.auditor = auditor
        self.config = config or {}
        
        # 会话管理
        self._sessions: Dict[str, SecurityContext] = {}
        self._session_lock = threading.RLock()
        
        # 权限缓存
        self._permission_cache: Dict[str, Set[Permission]] = {}
        self._cache_lock = threading.RLock()
        self._cache_ttl = self.config.get('permission_cache_ttl', 300)  # 5分钟
        self._cache_timestamps: Dict[str, float] = {}
        
        # 安全策略
        self.max_login_attempts = self.config.get('max_login_attempts', 5)
        self.lockout_duration = self.config.get('lockout_duration', 900)  # 15分钟
        self.session_timeout = self.config.get('session_timeout', 3600)  # 1小时
        self.password_policy = self.config.get('password_policy', {})
        
        # 失败登录跟踪
        self._failed_attempts: Dict[str, List[float]] = defaultdict(list)
        self._locked_accounts: Dict[str, float] = {}
        
        # 活动监控
        self._security_events: deque = deque(maxlen=1000)
        
        # 启动清理任务
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        """启动安全管理器"""
        if self._running:
            return
        
        self._running = True
        
        # 启动清理任务
        self._cleanup_task = asyncio.create_task(self._cleanup_sessions())
        
        # 初始化内置角色和权限
        await self._initialize_builtin_roles()
        
        logger.info("Security manager started")
    
    async def stop(self):
        """停止安全管理器"""
        if not self._running:
            return
        
        self._running = False
        
        # 停止清理任务
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 清理会话
        with self._session_lock:
            self._sessions.clear()
        
        logger.info("Security manager stopped")
    
    # 认证相关方法
    
    async def authenticate(self, 
                          username: str, 
                          password: str,
                          ip_address: Optional[str] = None,
                          user_agent: Optional[str] = None) -> Optional[SecurityContext]:
        """用户认证"""
        try:
            # 检查账户是否被锁定
            if await self._is_account_locked(username):
                await self._log_authentication(username, False, ip_address, "Account locked")
                raise AuthenticationError("Account is locked due to too many failed attempts")
            
            # 验证用户凭据
            user = await self.auth_provider.authenticate(username, password)
            if not user:
                await self._record_failed_attempt(username)
                await self._log_authentication(username, False, ip_address, "Invalid credentials")
                raise AuthenticationError("Invalid username or password")
            
            # 检查用户状态
            if not user.is_active:
                await self._log_authentication(username, False, ip_address, "User inactive")
                raise AuthenticationError("User account is inactive")
            
            # 创建安全上下文
            context = SecurityContext(
                user=user,
                session_id=TokenUtils.generate_session_id(),
                ip_address=ip_address,
                user_agent=user_agent,
                authentication_method="password",
                session_start=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                security_level=SecurityLevel.AUTHENTICATED
            )
            
            # 保存会话
            with self._session_lock:
                self._sessions[context.session_id] = context
            
            # 更新用户最后登录时间
            user.last_login = datetime.utcnow()
            await self.auth_provider.update_user(user)
            
            # 清理失败登录记录
            self._clear_failed_attempts(username)
            
            # 记录成功登录
            await self._log_authentication(username, True, ip_address)
            
            logger.info(f"User {username} authenticated successfully")
            return context
        
        except Exception as e:
            if not isinstance(e, AuthenticationError):
                logger.error(f"Authentication error for user {username}: {e}")
                raise AuthenticationError("Authentication failed")
            raise
    
    async def authenticate_token(self, 
                               token: str,
                               ip_address: Optional[str] = None) -> Optional[SecurityContext]:
        """令牌认证"""
        # 查找现有会话
        with self._session_lock:
            context = self._sessions.get(token)
            if context:
                # 检查会话是否过期
                if self._is_session_expired(context):
                    del self._sessions[token]
                    return None
                
                # 更新活动时间
                context.update_activity()
                context.ip_address = ip_address  # 更新IP地址
                
                return context
        
        return None
    
    async def logout(self, session_id: str):
        """用户登出"""
        with self._session_lock:
            context = self._sessions.pop(session_id, None)
            if context and context.user:
                await self._log_security_event(
                    "user.logout",
                    f"User {context.user.username} logged out",
                    context.user.username
                )
                logger.info(f"User {context.user.username} logged out")
    
    async def get_current_context(self, session_id: str) -> Optional[SecurityContext]:
        """获取当前安全上下文"""
        with self._session_lock:
            context = self._sessions.get(session_id)
            if context and not self._is_session_expired(context):
                context.update_activity()
                return context
            elif context:
                # 清理过期会话
                del self._sessions[session_id]
        
        return None
    
    # 授权相关方法
    
    async def check_permission(self, 
                              context: SecurityContext, 
                              permission: Permission,
                              resource_context: Optional[Dict[str, Any]] = None) -> bool:
        """检查权限"""
        try:
            if not context.is_authenticated:
                return False
            
            user = context.user
            
            # 超级管理员拥有所有权限
            if user.has_role("super_admin"):
                await self._log_authorization(user.username, permission, True, context)
                return True
            
            # 获取用户所有权限
            user_permissions = await self._get_user_permissions_cached(user)
            
            # 检查直接权限
            for user_perm in user_permissions:
                if user_perm.matches(permission):
                    await self._log_authorization(user.username, permission, True, context)
                    return True
            
            # 使用授权提供者进行额外检查
            result = await self.authz_provider.check_permission(user, permission, context)
            
            await self._log_authorization(user.username, permission, result, context)
            return result
        
        except Exception as e:
            logger.error(f"Permission check error: {e}")
            await self._log_authorization(
                context.user.username if context.user else "unknown", 
                permission, False, context
            )
            return False
    
    async def require_permission(self, 
                                context: SecurityContext, 
                                permission: Permission,
                                resource_context: Optional[Dict[str, Any]] = None):
        """要求权限（如果没有权限则抛出异常）"""
        if not await self.check_permission(context, permission, resource_context):
            raise AuthorizationError(f"Permission denied: {permission}")
    
    async def check_role(self, context: SecurityContext, role_name: str) -> bool:
        """检查角色"""
        if not context.is_authenticated:
            return False
        
        return context.user.has_role(role_name)
    
    async def require_role(self, context: SecurityContext, role_name: str):
        """要求角色（如果没有角色则抛出异常）"""
        if not await self.check_role(context, role_name):
            raise AuthorizationError(f"Role required: {role_name}")
    
    async def check_security_level(self, 
                                  context: SecurityContext, 
                                  required_level: SecurityLevel) -> bool:
        """检查安全级别"""
        if required_level == SecurityLevel.PUBLIC:
            return True
        
        if not context.is_authenticated:
            return False
        
        # 简单的安全级别检查
        level_hierarchy = {
            SecurityLevel.AUTHENTICATED: 1,
            SecurityLevel.AUTHORIZED: 2,
            SecurityLevel.RESTRICTED: 3,
            SecurityLevel.CONFIDENTIAL: 4,
            SecurityLevel.SECRET: 5
        }
        
        user_level = level_hierarchy.get(context.security_level, 0)
        required_level_value = level_hierarchy.get(required_level, 0)
        
        return user_level >= required_level_value
    
    # 用户管理方法
    
    async def create_user(self, 
                         username: str,
                         password: str,
                         email: Optional[str] = None,
                         display_name: Optional[str] = None,
                         roles: Optional[List[str]] = None) -> bool:
        """创建用户"""
        # 检查密码策略
        if not self._check_password_policy(password):
            raise SecurityError("Password does not meet policy requirements")
        
        # 创建用户对象
        password_hash, _ = PasswordUtils.hash_password(password)
        
        user = User(
            username=username,
            display_name=display_name,
            email=email,
            password_hash=password_hash,
            roles=set(roles) if roles else set(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        result = await self.auth_provider.create_user(user, password)
        
        if result:
            await self._log_security_event(
                "user.created",
                f"User {username} created",
                "system"
            )
        
        return result
    
    async def update_user_password(self, 
                                  username: str, 
                                  new_password: str,
                                  current_user: str) -> bool:
        """更新用户密码"""
        # 检查密码策略
        if not self._check_password_policy(new_password):
            raise SecurityError("Password does not meet policy requirements")
        
        user = await self.auth_provider.get_user(username)
        if not user:
            return False
        
        # 更新密码
        user.password_hash, _ = PasswordUtils.hash_password(new_password)
        user.updated_at = datetime.utcnow()
        
        result = await self.auth_provider.update_user(user)
        
        if result:
            await self._log_security_event(
                "user.password_changed",
                f"Password changed for user {username}",
                current_user
            )
            
            # 清理权限缓存
            self._clear_permission_cache(username)
        
        return result
    
    async def add_user_role(self, username: str, role_name: str, current_user: str) -> bool:
        """为用户添加角色"""
        user = await self.auth_provider.get_user(username)
        if not user:
            return False
        
        # 检查角色是否存在
        role = await self.authz_provider.get_role(role_name)
        if not role:
            return False
        
        user.add_role(role_name)
        result = await self.auth_provider.update_user(user)
        
        if result:
            await self._log_security_event(
                "user.role_added",
                f"Role {role_name} added to user {username}",
                current_user
            )
            
            # 清理权限缓存
            self._clear_permission_cache(username)
        
        return result
    
    async def remove_user_role(self, username: str, role_name: str, current_user: str) -> bool:
        """移除用户角色"""
        user = await self.auth_provider.get_user(username)
        if not user:
            return False
        
        user.remove_role(role_name)
        result = await self.auth_provider.update_user(user)
        
        if result:
            await self._log_security_event(
                "user.role_removed",
                f"Role {role_name} removed from user {username}",
                current_user
            )
            
            # 清理权限缓存
            self._clear_permission_cache(username)
        
        return result
    
    # 角色管理方法
    
    async def create_role(self, 
                         role_name: str,
                         display_name: str,
                         description: Optional[str] = None,
                         permissions: Optional[List[Permission]] = None) -> bool:
        """创建角色"""
        role = Role(
            name=role_name,
            display_name=display_name,
            description=description,
            permissions=set(permissions) if permissions else set(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        result = await self.authz_provider.create_role(role)
        
        if result:
            await self._log_security_event(
                "role.created",
                f"Role {role_name} created",
                "system"
            )
        
        return result
    
    async def add_role_permission(self, 
                                 role_name: str, 
                                 permission: Permission,
                                 current_user: str) -> bool:
        """为角色添加权限"""
        role = await self.authz_provider.get_role(role_name)
        if not role:
            return False
        
        role.add_permission(permission)
        result = await self.authz_provider.update_role(role)
        
        if result:
            await self._log_security_event(
                "role.permission_added",
                f"Permission {permission} added to role {role_name}",
                current_user
            )
            
            # 清理相关用户的权限缓存
            self._clear_role_permission_cache(role_name)
        
        return result
    
    # 监控和审计方法
    
    async def get_security_events(self, 
                                 limit: Optional[int] = None,
                                 event_type: Optional[str] = None,
                                 user: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取安全事件"""
        events = list(self._security_events)
        
        # 过滤
        if event_type:
            events = [e for e in events if e.get('event_type') == event_type]
        
        if user:
            events = [e for e in events if e.get('user') == user]
        
        # 限制数量
        if limit:
            events = events[-limit:]
        
        return events
    
    async def get_active_sessions(self) -> List[Dict[str, Any]]:
        """获取活动会话"""
        sessions = []
        
        with self._session_lock:
            for session_id, context in self._sessions.items():
                if not self._is_session_expired(context):
                    session_info = {
                        'session_id': session_id,
                        'username': context.user.username if context.user else None,
                        'ip_address': context.ip_address,
                        'session_start': context.session_start.isoformat() if context.session_start else None,
                        'last_activity': context.last_activity.isoformat() if context.last_activity else None,
                        'security_level': context.security_level.value
                    }
                    sessions.append(session_info)
        
        return sessions
    
    async def force_logout_user(self, username: str, current_user: str) -> int:
        """强制用户登出"""
        count = 0
        
        with self._session_lock:
            sessions_to_remove = []
            for session_id, context in self._sessions.items():
                if context.user and context.user.username == username:
                    sessions_to_remove.append(session_id)
            
            for session_id in sessions_to_remove:
                del self._sessions[session_id]
                count += 1
        
        if count > 0:
            await self._log_security_event(
                "user.force_logout",
                f"User {username} forcibly logged out from {count} sessions",
                current_user
            )
        
        return count
    
    # 私有方法
    
    async def _initialize_builtin_roles(self):
        """初始化内置角色"""
        builtin_roles = [
            BuiltinRoles.SUPER_ADMIN,
            BuiltinRoles.SERVER_ADMIN,
            BuiltinRoles.PLAYER_ADMIN,
            BuiltinRoles.PLUGIN_ADMIN,
            BuiltinRoles.READONLY_USER
        ]
        
        for role in builtin_roles:
            existing_role = await self.authz_provider.get_role(role.name)
            if not existing_role:
                await self.authz_provider.create_role(role)
                logger.info(f"Created builtin role: {role.name}")
    
    async def _get_user_permissions_cached(self, user: User) -> Set[Permission]:
        """获取用户权限（带缓存）"""
        cache_key = user.username
        current_time = time.time()
        
        with self._cache_lock:
            # 检查缓存
            if (cache_key in self._permission_cache and 
                cache_key in self._cache_timestamps and
                current_time - self._cache_timestamps[cache_key] < self._cache_ttl):
                return self._permission_cache[cache_key]
        
        # 重新加载权限
        permissions = await self.authz_provider.get_user_permissions(user)
        
        with self._cache_lock:
            self._permission_cache[cache_key] = permissions
            self._cache_timestamps[cache_key] = current_time
        
        return permissions
    
    def _clear_permission_cache(self, username: str):
        """清理权限缓存"""
        with self._cache_lock:
            self._permission_cache.pop(username, None)
            self._cache_timestamps.pop(username, None)
    
    def _clear_role_permission_cache(self, role_name: str):
        """清理角色相关的权限缓存"""
        # 简单实现：清理所有缓存
        with self._cache_lock:
            self._permission_cache.clear()
            self._cache_timestamps.clear()
    
    async def _is_account_locked(self, username: str) -> bool:
        """检查账户是否被锁定"""
        if username in self._locked_accounts:
            lock_time = self._locked_accounts[username]
            if time.time() - lock_time < self.lockout_duration:
                return True
            else:
                # 锁定时间已过，解除锁定
                del self._locked_accounts[username]
        
        return False
    
    async def _record_failed_attempt(self, username: str):
        """记录失败登录尝试"""
        current_time = time.time()
        
        # 清理过期的失败尝试记录
        cutoff_time = current_time - self.lockout_duration
        self._failed_attempts[username] = [
            attempt_time for attempt_time in self._failed_attempts[username]
            if attempt_time > cutoff_time
        ]
        
        # 添加新的失败尝试
        self._failed_attempts[username].append(current_time)
        
        # 检查是否需要锁定账户
        if len(self._failed_attempts[username]) >= self.max_login_attempts:
            self._locked_accounts[username] = current_time
            await self._log_security_event(
                "account.locked",
                f"Account {username} locked due to too many failed login attempts",
                "system",
                "warning"
            )
    
    def _clear_failed_attempts(self, username: str):
        """清理失败登录记录"""
        self._failed_attempts.pop(username, None)
        self._locked_accounts.pop(username, None)
    
    def _is_session_expired(self, context: SecurityContext) -> bool:
        """检查会话是否过期"""
        if not context.last_activity:
            return True
        
        elapsed = (datetime.utcnow() - context.last_activity).total_seconds()
        return elapsed > self.session_timeout
    
    def _check_password_policy(self, password: str) -> bool:
        """检查密码策略"""
        policy = self.password_policy
        
        # 最小长度
        min_length = policy.get('min_length', 8)
        if len(password) < min_length:
            return False
        
        # 复杂性要求
        if policy.get('require_uppercase', True):
            if not any(c.isupper() for c in password):
                return False
        
        if policy.get('require_lowercase', True):
            if not any(c.islower() for c in password):
                return False
        
        if policy.get('require_digit', True):
            if not any(c.isdigit() for c in password):
                return False
        
        if policy.get('require_special', True):
            special_chars = "!@#$%^&*(),.?\":{}|<>"
            if not any(c in special_chars for c in password):
                return False
        
        return True
    
    async def _cleanup_sessions(self):
        """定期清理过期会话"""
        while self._running:
            try:
                current_time = datetime.utcnow()
                expired_sessions = []
                
                with self._session_lock:
                    for session_id, context in self._sessions.items():
                        if self._is_session_expired(context):
                            expired_sessions.append(session_id)
                    
                    for session_id in expired_sessions:
                        context = self._sessions.pop(session_id, None)
                        if context and context.user:
                            await self._log_security_event(
                                "session.expired",
                                f"Session expired for user {context.user.username}",
                                "system"
                            )
                
                if expired_sessions:
                    logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
                
                # 等待下次清理
                await asyncio.sleep(300)  # 5分钟
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session cleanup: {e}")
                await asyncio.sleep(60)
    
    async def _log_authentication(self, 
                                 username: str, 
                                 success: bool, 
                                 ip_address: Optional[str] = None,
                                 reason: Optional[str] = None):
        """记录认证事件"""
        if self.auditor:
            await self.auditor.log_authentication(username, success, ip_address)
        
        event_type = "auth.success" if success else "auth.failure"
        description = f"Authentication {'succeeded' if success else 'failed'} for user {username}"
        if reason:
            description += f": {reason}"
        
        await self._log_security_event(event_type, description, username, 
                                      "info" if success else "warning")
    
    async def _log_authorization(self, 
                                username: str, 
                                permission: Permission, 
                                granted: bool,
                                context: Optional[SecurityContext] = None):
        """记录授权事件"""
        if self.auditor:
            await self.auditor.log_authorization(username, permission, granted, context)
        
        # 只记录被拒绝的授权事件，避免日志过多
        if not granted:
            await self._log_security_event(
                "authz.denied",
                f"Permission {permission} denied for user {username}",
                username,
                "warning"
            )
    
    async def _log_security_event(self, 
                                 event_type: str, 
                                 description: str,
                                 user: Optional[str] = None,
                                 severity: str = "info",
                                 metadata: Optional[Dict[str, Any]] = None):
        """记录安全事件"""
        if self.auditor:
            await self.auditor.log_security_event(event_type, description, user, severity, metadata)
        
        event = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'description': description,
            'user': user,
            'severity': severity,
            'metadata': metadata or {}
        }
        
        self._security_events.append(event)
        
        # 根据严重性记录日志
        if severity == "warning":
            logger.warning(f"Security event: {description}")
        elif severity == "error":
            logger.error(f"Security event: {description}")
        else:
            logger.info(f"Security event: {description}")