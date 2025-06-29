"""
Aetherius组件管理器
=================

负责组件的加载、启用、禁用和卸载
支持Web组件和事件驱动架构
"""

import importlib.util
import inspect
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

from .component import Component, ComponentInfo, WebComponent

logger = logging.getLogger(__name__)


class ComponentManager:
    """增强的组件管理器"""

    def __init__(self, core_instance):
        """
        初始化组件管理器

        Args:
            core_instance: Aetherius核心实例
        """
        self.core = core_instance
        self.components: dict[str, Component] = {}
        self.component_info: dict[str, ComponentInfo] = {}
        self.component_paths: dict[str, Path] = {}
        self._load_order: list[str] = []
        self._dependency_graph: dict[str, set[str]] = {}

        # 组件目录
        self.components_dir = Path("components")
        if not self.components_dir.exists():
            self.components_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Created components directory")

        # Web组件支持
        self._web_components: dict[str, WebComponent] = {}
        self._web_routes: dict[str, dict[str, Any]] = {}
        self._api_endpoints: dict[str, dict[str, Any]] = {}

        # 状态追踪
        self._loaded_components: set[str] = set()
        self._enabled_components: set[str] = set()
        self._failed_components: dict[str, str] = {}

        logger.info("Component manager initialized")

    async def scan_components(self) -> list[str]:
        """
        扫描组件目录，发现可用组件

        Returns:
            发现的组件名称列表
        """
        discovered = []

        for component_dir in self.components_dir.iterdir():
            if not component_dir.is_dir():
                continue

            # 检查必要文件
            init_file = component_dir / "__init__.py"
            info_file = component_dir / "component.yaml"

            if not init_file.exists():
                logger.warning(f"Component {component_dir.name} missing __init__.py")
                continue

            if not info_file.exists():
                logger.warning(f"Component {component_dir.name} missing component.yaml")
                continue

            discovered.append(component_dir.name)

        logger.info(f"Discovered {len(discovered)} components: {discovered}")
        return discovered

    def _load_component_info(self, component_dir: Path) -> Optional[ComponentInfo]:
        """
        加载组件信息

        Args:
            component_dir: 组件目录

        Returns:
            组件信息对象或None
        """
        info_file = component_dir / "component.yaml"
        if not info_file.exists():
            # 尝试JSON格式
            info_file = component_dir / "component.json"
            if not info_file.exists():
                logger.error(f"No component info file found in {component_dir}")
                return None

        try:
            with open(info_file, encoding="utf-8") as f:
                if info_file.suffix == ".yaml":
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)

            # 验证必需字段
            required_fields = [
                "name",
                "display_name",
                "description",
                "version",
                "author",
            ]
            for field in required_fields:
                if field not in data:
                    logger.error(
                        f"Component {component_dir.name} missing required field: {field}"
                    )
                    return None

            # 创建ComponentInfo对象
            info = ComponentInfo(**data)
            if not info.validate():
                logger.error(f"Component {component_dir.name} info validation failed")
                return None

            return info

        except Exception as e:
            logger.error(f"Error loading component info from {component_dir}: {e}")
            return None

    def _analyze_dependencies(self, component_infos: dict[str, ComponentInfo]):
        """
        分析组件依赖关系

        Args:
            component_infos: 组件信息字典
        """
        self._dependency_graph.clear()

        for name, info in component_infos.items():
            self._dependency_graph[name] = set(info.dependencies)

        # 检查循环依赖
        for name in component_infos:
            if self._has_circular_dependency(name, set()):
                logger.error(f"Circular dependency detected for component: {name}")
                raise RuntimeError(f"Circular dependency in component: {name}")

    def _has_circular_dependency(self, component: str, visited: set[str]) -> bool:
        """检查循环依赖"""
        if component in visited:
            return True

        visited.add(component)
        for dep in self._dependency_graph.get(component, set()):
            if self._has_circular_dependency(dep, visited.copy()):
                return True

        return False

    def _topological_sort(self, component_infos: dict[str, ComponentInfo]) -> list[str]:
        """
        拓扑排序，确定加载顺序

        Args:
            component_infos: 组件信息字典

        Returns:
            排序后的组件名称列表
        """
        # 使用Kahn算法进行拓扑排序
        in_degree = {name: 0 for name in component_infos}
        graph = {name: [] for name in component_infos}

        # 构建图和入度
        for name, info in component_infos.items():
            for dep in info.dependencies:
                if dep in graph:
                    graph[dep].append(name)
                    in_degree[name] += 1
                else:
                    logger.warning(
                        f"Component {name} depends on unknown component: {dep}"
                    )

        # 拓扑排序
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # 按load_order和名称排序
            queue.sort(key=lambda x: (component_infos[x].load_order, x))
            current = queue.pop(0)
            result.append(current)

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(component_infos):
            remaining = set(component_infos.keys()) - set(result)
            logger.error(f"Topological sort failed, remaining components: {remaining}")
            raise RuntimeError("Cannot resolve component dependencies")

        return result

    async def load_component(self, component_name: str) -> bool:
        """
        加载单个组件

        Args:
            component_name: 组件名称

        Returns:
            是否成功加载
        """
        if component_name in self._loaded_components:
            logger.warning(f"Component {component_name} already loaded")
            return True

        component_dir = self.components_dir / component_name
        if not component_dir.exists():
            logger.error(f"Component directory not found: {component_dir}")
            return False

        try:
            # 加载组件信息
            info = self._load_component_info(component_dir)
            if not info:
                return False

            # 检查依赖
            missing_deps = []
            for dep in info.dependencies:
                if dep not in self._loaded_components:
                    missing_deps.append(dep)

            if missing_deps:
                logger.error(
                    f"Component {component_name} missing dependencies: {missing_deps}"
                )
                self._failed_components[
                    component_name
                ] = f"Missing dependencies: {missing_deps}"
                return False

            # 加载组件模块
            init_file = component_dir / "__init__.py"
            spec = importlib.util.spec_from_file_location(
                f"component_{component_name}", init_file
            )

            if spec is None or spec.loader is None:
                logger.error(f"Failed to create spec for component: {component_name}")
                return False

            module = importlib.util.module_from_spec(spec)
            sys.modules[f"component_{component_name}"] = module
            spec.loader.exec_module(module)

            # 查找组件类
            component_class = None

            # 1. 优先使用info中指定的主类
            if hasattr(info, "main_class") and hasattr(module, info.main_class):
                component_class = getattr(module, info.main_class)

            # 2. 查找Component子类
            if not component_class:
                for name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, Component)
                        and obj != Component
                        and obj != WebComponent
                    ):
                        component_class = obj
                        break

            if not component_class:
                logger.error(f"No Component class found in {component_name}")
                return False

            # 创建组件实例
            component_config = self._load_component_config(component_dir, info)
            component = component_class(self.core, component_config)
            component.component_info = info
            component.data_folder = component_dir / "data"

            # 调用加载生命周期
            await component.on_load()

            # 存储组件
            self.components[component_name] = component
            self.component_info[component_name] = info
            self.component_paths[component_name] = component_dir
            self._loaded_components.add(component_name)

            # 如果是Web组件，添加到Web组件集合
            if isinstance(component, WebComponent):
                self._web_components[component_name] = component

            logger.info(
                f"Successfully loaded component: {component_name} v{info.version}"
            )

            # 发送组件加载事件
            if hasattr(self.core, "event_manager") and self.core.event_manager:
                await self.core.event_manager.emit_event(
                    "component_loaded",
                    {"name": component_name, "info": info.to_dict()},
                    source="ComponentManager",
                )

            return True

        except Exception as e:
            logger.error(f"Error loading component {component_name}: {e}")
            self._failed_components[component_name] = str(e)
            return False

    def _load_component_config(
        self, component_dir: Path, info: ComponentInfo
    ) -> dict[str, Any]:
        """
        加载组件配置

        Args:
            component_dir: 组件目录
            info: 组件信息

        Returns:
            组件配置字典
        """
        config = info.default_config.copy()

        # 尝试加载用户配置
        config_file = component_dir / "config.yaml"
        if config_file.exists():
            try:
                with open(config_file, encoding="utf-8") as f:
                    user_config = yaml.safe_load(f) or {}
                config.update(user_config)
            except Exception as e:
                logger.warning(f"Failed to load config for {component_dir.name}: {e}")

        return config

    async def load_all_components(self) -> int:
        """
        加载所有组件

        Returns:
            成功加载的组件数量
        """
        logger.info("Starting component loading process")

        # 发现组件
        discovered = await self.scan_components()
        if not discovered:
            logger.info("No components found")
            return 0

        # 加载组件信息
        component_infos = {}
        for component_name in discovered:
            component_dir = self.components_dir / component_name
            info = self._load_component_info(component_dir)
            if info:
                component_infos[component_name] = info

        if not component_infos:
            logger.warning("No valid component info found")
            return 0

        # 分析依赖关系
        try:
            self._analyze_dependencies(component_infos)
            self._load_order = self._topological_sort(component_infos)
        except Exception as e:
            logger.error(f"Dependency analysis failed: {e}")
            return 0

        # 按依赖顺序加载组件
        loaded_count = 0
        for component_name in self._load_order:
            if await self.load_component(component_name):
                loaded_count += 1

        logger.info(f"Loaded {loaded_count}/{len(discovered)} components")
        return loaded_count

    async def enable_component(self, component_name: str) -> bool:
        """
        启用组件

        Args:
            component_name: 组件名称

        Returns:
            是否成功启用
        """
        if component_name not in self._loaded_components:
            logger.error(f"Component {component_name} not loaded")
            return False

        if component_name in self._enabled_components:
            logger.warning(f"Component {component_name} already enabled")
            return True

        try:
            component = self.components[component_name]
            await component.on_enable()
            self._enabled_components.add(component_name)

            logger.info(f"Enabled component: {component_name}")

            # 发送组件启用事件
            if hasattr(self.core, "event_manager") and self.core.event_manager:
                await self.core.event_manager.emit_event(
                    "component_enabled",
                    {"name": component_name},
                    source="ComponentManager",
                )

            return True

        except Exception as e:
            logger.error(f"Error enabling component {component_name}: {e}")
            return False

    async def disable_component(self, component_name: str) -> bool:
        """
        禁用组件

        Args:
            component_name: 组件名称

        Returns:
            是否成功禁用
        """
        if component_name not in self._enabled_components:
            logger.warning(f"Component {component_name} not enabled")
            return True

        try:
            component = self.components[component_name]
            await component.on_disable()
            self._enabled_components.remove(component_name)

            logger.info(f"Disabled component: {component_name}")

            # 发送组件禁用事件
            if hasattr(self.core, "event_manager") and self.core.event_manager:
                await self.core.event_manager.emit_event(
                    "component_disabled",
                    {"name": component_name},
                    source="ComponentManager",
                )

            return True

        except Exception as e:
            logger.error(f"Error disabling component {component_name}: {e}")
            return False

    async def unload_component(self, component_name: str) -> bool:
        """
        卸载组件

        Args:
            component_name: 组件名称

        Returns:
            是否成功卸载
        """
        if component_name not in self._loaded_components:
            logger.warning(f"Component {component_name} not loaded")
            return True

        try:
            # 先禁用
            if component_name in self._enabled_components:
                await self.disable_component(component_name)

            # 卸载
            component = self.components[component_name]
            await component.on_unload()

            # 清理
            del self.components[component_name]
            del self.component_info[component_name]
            del self.component_paths[component_name]
            self._loaded_components.remove(component_name)

            if component_name in self._web_components:
                del self._web_components[component_name]

            if component_name in self._failed_components:
                del self._failed_components[component_name]

            logger.info(f"Unloaded component: {component_name}")

            # 发送组件卸载事件
            if hasattr(self.core, "event_manager") and self.core.event_manager:
                await self.core.event_manager.emit_event(
                    "component_unloaded",
                    {"name": component_name},
                    source="ComponentManager",
                )

            return True

        except Exception as e:
            logger.error(f"Error unloading component {component_name}: {e}")
            return False

    async def reload_component(self, component_name: str) -> bool:
        """
        重载组件

        Args:
            component_name: 组件名称

        Returns:
            是否成功重载
        """
        was_enabled = component_name in self._enabled_components

        # 卸载
        if not await self.unload_component(component_name):
            return False

        # 重新加载
        if not await self.load_component(component_name):
            return False

        # 如果之前是启用状态，重新启用
        if was_enabled:
            return await self.enable_component(component_name)

        return True

    async def enable_all_components(self) -> int:
        """
        启用所有已加载的组件

        Returns:
            成功启用的组件数量
        """
        enabled_count = 0
        for component_name in self._load_order:
            if component_name in self._loaded_components:
                if await self.enable_component(component_name):
                    enabled_count += 1
        return enabled_count

    # 查询方法
    def is_loaded(self, component_name: str) -> bool:
        """检查组件是否已加载"""
        return component_name in self._loaded_components

    def is_enabled(self, component_name: str) -> bool:
        """检查组件是否已启用"""
        return component_name in self._enabled_components

    def get_component(self, component_name: str) -> Optional[Component]:
        """获取组件实例"""
        return self.components.get(component_name)

    def get_component_info(self, component_name: str) -> Optional[ComponentInfo]:
        """获取组件信息"""
        return self.component_info.get(component_name)

    def get_web_component(self, component_name: str) -> WebComponent | None:
        """获取Web组件实例"""
        return self._web_components.get(component_name)

    def list_loaded_components(self) -> list[str]:
        """列出已加载的组件"""
        return list(self._loaded_components)

    def list_enabled_components(self) -> list[str]:
        """列出已启用的组件"""
        return list(self._enabled_components)

    def list_web_components(self) -> list[str]:
        """列出Web组件"""
        return list(self._web_components.keys())

    def get_component_status(self) -> dict[str, Any]:
        """
        获取组件系统状态

        Returns:
            包含状态信息的字典
        """
        return {
            "total_loaded": len(self._loaded_components),
            "total_enabled": len(self._enabled_components),
            "total_web_components": len(self._web_components),
            "total_failed": len(self._failed_components),
            "loaded_components": list(self._loaded_components),
            "enabled_components": list(self._enabled_components),
            "web_components": list(self._web_components.keys()),
            "failed_components": dict(self._failed_components),
            "load_order": self._load_order,
        }

    def get_detailed_status(self) -> dict[str, Any]:
        """
        获取详细的组件状态信息

        Returns:
            详细状态信息字典
        """
        status = self.get_component_status()

        # 添加每个组件的详细信息
        component_details = {}
        for name in self._loaded_components:
            component = self.components[name]
            info = self.component_info[name]

            component_details[name] = {
                "info": info.to_dict(),
                "status": component.get_status(),
                "is_web_component": name in self._web_components,
            }

        status["component_details"] = component_details
        return status
