"""
Aetherius Core 应用程序入口

整合所有核心系统的主应用程序类
"""

import asyncio
import signal
import sys
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from .di import DependencyContainer, singleton
from .config import ConfigManager, FileConfigSource, EnvironmentConfigSource, ConfigPriority, ConfigFormat
from .events.enhanced import EnhancedEventBus, MemoryEventStore
from .extensions.manager import ExtensionManager
from .security.manager import SecurityManager
from .monitoring import MonitoringContext

logger = logging.getLogger(__name__)


@singleton()
class AetheriusCore:
    """Aetherius Core 主应用程序"""
    
    def __init__(self):
        self.version = "2.0.0"
        self.instance_id = None
        self.data_dir = Path("data")
        self.config_dir = Path("config")
        
        # 核心组件
        self.container: Optional[DependencyContainer] = None
        self.config: Optional[ConfigManager] = None
        self.events: Optional[EnhancedEventBus] = None
        self.security: Optional[SecurityManager] = None
        self.extensions: Optional[ExtensionManager] = None
        self.monitoring_context: Optional[MonitoringContext] = None
        
        # 状态管理
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._startup_tasks: List[asyncio.Task] = []
        
        # 信号处理
        self._setup_signal_handlers()
    
    async def initialize(self, config_path: Optional[Path] = None):
        """初始化应用程序"""
        try:
            logger.info(f"Initializing Aetherius Core v{self.version}")
            
            # 1. 初始化依赖注入容器
            await self._initialize_container()
            
            # 2. 初始化配置系统
            await self._initialize_config(config_path)
            
            # 3. 初始化事件系统
            await self._initialize_events()
            
            # 4. 初始化安全系统
            await self._initialize_security()
            
            # 5. 初始化扩展系统
            await self._initialize_extensions()
            
            # 6. 初始化监控系统
            await self._initialize_monitoring()
            
            # 7. 注册核心服务
            await self._register_core_services()
            
            logger.info("Aetherius Core initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Aetherius Core: {e}")
            raise
    
    async def start(self):
        """启动应用程序"""
        if self._running:
            logger.warning("Aetherius Core is already running")
            return
        
        try:
            logger.info("Starting Aetherius Core...")
            
            # 启动核心组件
            await self._start_core_components()
            
            # 发现和加载扩展
            await self._discover_and_load_extensions()
            
            # 启动扩展
            await self._start_extensions()
            
            # 标记为运行状态
            self._running = True
            
            # 发送启动事件
            await self.events.publish("core.started", {
                "version": self.version,
                "instance_id": self.instance_id
            })
            
            logger.info("Aetherius Core started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start Aetherius Core: {e}")
            await self.stop()
            raise
    
    async def stop(self):
        """停止应用程序"""
        if not self._running:
            return
        
        logger.info("Stopping Aetherius Core...")
        
        try:
            # 发送停止事件
            if self.events:
                await self.events.publish("core.stopping", {
                    "instance_id": self.instance_id
                })
            
            # 停止扩展
            if self.extensions:
                await self.extensions.stop_all_extensions()
            
            # 停止核心组件
            await self._stop_core_components()
            
            # 取消启动任务
            for task in self._startup_tasks:
                if not task.done():
                    task.cancel()
            
            if self._startup_tasks:
                await asyncio.gather(*self._startup_tasks, return_exceptions=True)
                self._startup_tasks.clear()
            
            self._running = False
            self._shutdown_event.set()
            
            logger.info("Aetherius Core stopped")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    async def run(self, config_path: Optional[Path] = None):
        """运行应用程序（阻塞）"""
        await self.initialize(config_path)
        await self.start()
        
        try:
            # 等待关闭信号
            await self._shutdown_event.wait()
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            await self.stop()
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running
    
    def get_status(self) -> Dict[str, Any]:
        """获取应用程序状态"""
        status = {
            "version": self.version,
            "instance_id": self.instance_id,
            "running": self._running,
            "uptime": None,
            "components": {}
        }
        
        if self.config:
            status["components"]["config"] = "initialized"
        
        if self.events:
            status["components"]["events"] = "initialized"
            status["event_stats"] = self.events.get_stats()
        
        if self.security:
            status["components"]["security"] = "initialized"
        
        if self.extensions:
            status["components"]["extensions"] = "initialized"
            status["extension_stats"] = self.extensions.get_extension_status()
        
        return status
    
    # 私有方法
    
    async def _initialize_container(self):
        """初始化依赖注入容器"""
        logger.debug("Initializing dependency injection container")
        
        self.container = DependencyContainer()
        
        # 注册核心实例
        self.container.register_instance(AetheriusCore, self)
        self.container.register_instance(DependencyContainer, self.container)
    
    async def _initialize_config(self, config_path: Optional[Path] = None):
        """初始化配置系统"""
        logger.debug("Initializing configuration system")
        
        from .config import ConfigManager, SchemaValidator, SimpleTemplateEngine, AETHERIUS_CONFIG_SCHEMA
        
        # 创建配置管理器
        self.config = ConfigManager(
            enable_watching=True,
            template_engine=SimpleTemplateEngine()
        )
        
        # 添加配置源
        
        # 1. 文件配置源
        if config_path:
            self.config.add_source(FileConfigSource(
                config_path,
                ConfigPriority.FILE
            ))
        else:
            # 默认配置文件
            default_config = self.config_dir / "config.yaml"
            if default_config.exists():
                self.config.add_source(FileConfigSource(
                    default_config,
                    ConfigPriority.FILE
                ))
        
        # 2. 环境变量配置源
        self.config.add_source(EnvironmentConfigSource(
            prefix="AETHERIUS",
            priority=ConfigPriority.ENVIRONMENT
        ))
        
        # 添加验证器
        validator = SchemaValidator(AETHERIUS_CONFIG_SCHEMA)
        self.config.add_validator(".*", validator)
        
        # 设置实例ID
        self.instance_id = self.config.get("core.instance_id", f"aetherius-{id(self)}")
        
        # 注册到容器
        self.container.register_instance(ConfigManager, self.config)
        
        logger.debug("Configuration system initialized")
    
    async def _initialize_events(self):
        """初始化事件系统"""
        logger.debug("Initializing event system")
        
        # 创建事件存储
        event_store = None
        if self.config.get("events.enable_persistence", False):
            event_store = MemoryEventStore(
                max_events=self.config.get("events.max_stored_events", 10000)
            )
        
        # 创建事件总线
        self.events = EnhancedEventBus(
            max_queue_size=self.config.get("events.max_queue_size", 10000),
            max_workers=self.config.get("events.max_workers", 50),
            enable_persistence=self.config.get("events.enable_persistence", False),
            event_store=event_store
        )
        
        # 注册到容器
        self.container.register_instance(EnhancedEventBus, self.events)
        
        logger.debug("Event system initialized")
    
    async def _initialize_security(self):
        """初始化安全系统"""
        logger.debug("Initializing security system")
        
        from .security.providers import (
            DatabaseAuthenticationProvider, DatabaseAuthorizationProvider, FileSecurityAuditor
        )
        from .security.manager import SecurityManager
        
        # 安全配置
        security_config = {
            'max_login_attempts': self.config.get('security.max_login_attempts', 5),
            'lockout_duration': self.config.get('security.lockout_duration', 900),
            'session_timeout': self.config.get('security.session_timeout', 3600),
            'permission_cache_ttl': self.config.get('security.permission_cache_ttl', 300),
            'password_policy': self.config.get('security.password_policy', {})
        }
        
        # 创建提供者
        db_path = self.data_dir / "security" / "auth.db"
        auth_provider = DatabaseAuthenticationProvider(db_path)
        authz_provider = DatabaseAuthorizationProvider(db_path)
        
        # 创建审计器
        audit_log_path = self.data_dir / "logs" / "security_audit.log"
        auditor = FileSecurityAuditor(audit_log_path)
        
        # 创建安全管理器
        self.security = SecurityManager(
            auth_provider=auth_provider,
            authz_provider=authz_provider,
            auditor=auditor,
            config=security_config
        )
        
        # 注册到容器
        self.container.register_instance(SecurityManager, self.security)
        
        logger.debug("Security system initialized")
    
    async def _initialize_extensions(self):
        """初始化扩展系统"""
        logger.debug("Initializing extension system")
        
        self.extensions = ExtensionManager(
            config_manager=self.config,
            event_manager=self.events,
            di_container=self.container,
            data_dir=self.data_dir
        )
        
        # 注册到容器
        self.container.register_instance(ExtensionManager, self.extensions)
        
        logger.debug("Extension system initialized")
    
    async def _initialize_monitoring(self):
        """初始化监控系统"""
        logger.debug("Initializing monitoring system")
        
        from .monitoring.collectors import (
            InMemoryMetricsCollector, HealthCheckManager, SimpleAlertManager,
            SystemMetricsCollector, SystemHealthChecks
        )
        
        # 创建监控上下文
        self.monitoring_context = MonitoringContext(
            service_name="aetherius-core",
            instance_id=self.instance_id,
            version=self.version,
            environment=self.config.get("core.environment", "development")
        )
        
        # 创建指标收集器
        self.metrics_collector = InMemoryMetricsCollector(
            max_metrics=self.config.get("monitoring.max_metrics", 10000)
        )
        
        # 创建健康检查管理器
        self.health_checker = HealthCheckManager()
        
        # 创建告警管理器
        self.alert_manager = SimpleAlertManager()
        
        # 创建系统指标收集器
        self.system_metrics = SystemMetricsCollector(self.metrics_collector)
        
        # 注册系统健康检查
        self.health_checker.register_check(
            "cpu_usage", 
            SystemHealthChecks.cpu_usage_check(90.0), 
            30.0
        )
        self.health_checker.register_check(
            "memory_usage", 
            SystemHealthChecks.memory_usage_check(85.0), 
            30.0
        )
        self.health_checker.register_check(
            "disk_space", 
            SystemHealthChecks.disk_space_check("/", 90.0), 
            60.0
        )
        
        # 注册到容器
        self.container.register_instance(MonitoringContext, self.monitoring_context)
        self.container.register_instance("IMetricsCollector", self.metrics_collector)
        self.container.register_instance("IHealthChecker", self.health_checker)
        self.container.register_instance("IAlertManager", self.alert_manager)
        
        logger.debug("Monitoring system initialized")
    
    async def _register_core_services(self):
        """注册核心服务"""
        logger.debug("Registering core services")
        
        # 自动注册标记为Injectable的核心类
        from . import config, events, extensions, security, monitoring
        
        modules = [config, events, extensions, security, monitoring]
        for module in modules:
            try:
                self.container.auto_register_assembly(module)
            except Exception as e:
                logger.warning(f"Failed to auto-register module {module}: {e}")
        
        logger.debug("Core services registered")
    
    async def _start_core_components(self):
        """启动核心组件"""
        logger.debug("Starting core components")
        
        # 启动事件系统
        if self.events:
            await self.events.start()
        
        # 启动安全系统
        if self.security:
            await self.security.start()
        
        # 启动监控组件
        if hasattr(self, 'health_checker'):
            await self.health_checker.start()
        
        if hasattr(self, 'system_metrics'):
            await self.system_metrics.start()
        
        logger.debug("Core components started")
    
    async def _stop_core_components(self):
        """停止核心组件"""
        logger.debug("Stopping core components")
        
        # 停止监控组件
        if hasattr(self, 'system_metrics'):
            await self.system_metrics.stop()
        
        if hasattr(self, 'health_checker'):
            await self.health_checker.stop()
        
        # 停止扩展系统
        if self.extensions:
            # ExtensionManager 没有 stop 方法，但我们可以停止所有扩展
            pass
        
        # 停止安全系统
        if self.security:
            await self.security.stop()
        
        # 停止事件系统
        if self.events:
            await self.events.stop()
        
        logger.debug("Core components stopped")
    
    async def _discover_and_load_extensions(self):
        """发现和加载扩展"""
        logger.debug("Discovering and loading extensions")
        
        if not self.extensions:
            return
        
        # 扩展目录
        extension_directories = [
            self.data_dir / "extensions",
            Path("extensions"),
            Path("plugins"),
            Path("components")
        ]
        
        # 过滤存在的目录
        existing_dirs = [d for d in extension_directories if d.exists()]
        
        if existing_dirs:
            await self.extensions.load_all_extensions(existing_dirs)
        
        logger.debug("Extensions discovered and loaded")
    
    async def _start_extensions(self):
        """启动扩展"""
        logger.debug("Starting extensions")
        
        if not self.extensions:
            return
        
        await self.extensions.start_all_extensions()
        
        logger.debug("Extensions started")
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        if sys.platform != "win32":
            def signal_handler(signum, frame):
                logger.info(f"Received signal {signum}")
                if self._running:
                    asyncio.create_task(self.stop())
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)


# 应用程序工厂函数

async def create_app(config_path: Optional[Path] = None) -> AetheriusCore:
    """创建应用程序实例"""
    app = AetheriusCore()
    await app.initialize(config_path)
    return app


async def run_app(config_path: Optional[Path] = None):
    """运行应用程序"""
    app = AetheriusCore()
    await app.run(config_path)


# CLI 入口点

def main():
    """主入口点"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Aetherius Core Server")
    parser.add_argument("--config", type=Path, help="Configuration file path")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # 设置日志
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # 运行应用程序
    try:
        asyncio.run(run_app(args.config))
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()