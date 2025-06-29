"""
Aetherius玩家数据管理扩展
=======================

为Web组件提供的增强玩家数据管理功能
"""

import json
import logging
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from .player_data import PlayerDataManager, PlayerInventory, PlayerLocation, PlayerStats

logger = logging.getLogger(__name__)


@dataclass
class ExtendedPlayerInfo:
    """扩展的玩家信息"""

    # 基础信息
    name: str
    uuid: str
    display_name: str

    # 连接信息
    ip_address: str
    first_join: datetime
    last_join: datetime
    last_quit: datetime
    total_playtime: int  # 秒
    session_playtime: int  # 当前会话时间

    # 位置和状态
    location: PlayerLocation
    stats: PlayerStats
    inventory: PlayerInventory

    # 游戏数据
    achievements: list[str]
    advancements: dict[str, Any]
    statistics: dict[str, int]

    # 管理信息
    is_online: bool
    is_banned: bool
    is_whitelisted: bool
    is_op: bool
    permission_groups: list[str]

    # 社交信息
    friends: list[str]
    ignored_players: list[str]
    last_message: str
    message_count: int

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        # 转换datetime为ISO格式
        data["first_join"] = self.first_join.isoformat() if self.first_join else None
        data["last_join"] = self.last_join.isoformat() if self.last_join else None
        data["last_quit"] = self.last_quit.isoformat() if self.last_quit else None
        return data


@dataclass
class PlayerSession:
    """玩家会话信息"""

    player_uuid: str
    session_id: str
    join_time: datetime
    quit_time: Optional[datetime]
    duration: int  # 秒
    ip_address: str

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        data["join_time"] = self.join_time.isoformat()
        data["quit_time"] = self.quit_time.isoformat() if self.quit_time else None
        return data


@dataclass
class PlayerAction:
    """玩家行为记录"""

    player_uuid: str
    action_type: str  # join, quit, chat, command, death, etc.
    timestamp: datetime
    details: dict[str, Any]
    location: Optional[PlayerLocation]

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class PlayerManagerExtensions:
    """玩家管理器扩展类"""

    def __init__(
        self, player_data_manager: PlayerDataManager, database_path: str = None
    ):
        """
        初始化玩家管理器扩展

        Args:
            player_data_manager: 基础玩家数据管理器
            database_path: 数据库路径
        """
        self.player_manager = player_data_manager
        self.db_path = database_path or "data/players.db"

        # 确保数据库目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # 在线玩家追踪
        self._online_players: dict[str, ExtendedPlayerInfo] = {}
        self._player_sessions: dict[str, PlayerSession] = {}

        # 缓存
        self._player_cache: dict[str, ExtendedPlayerInfo] = {}
        self._cache_ttl = 300  # 5分钟
        self._cache_timestamps: dict[str, datetime] = {}

        # 统计追踪
        self._player_statistics: dict[str, dict[str, int]] = {}
        self._action_history: list[PlayerAction] = []
        self._max_action_history = 10000

        # 初始化数据库
        self._init_database()

        logger.info("Player manager extensions initialized")

    def _init_database(self):
        """初始化数据库表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 玩家基础信息表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS players (
                        uuid TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        display_name TEXT,
                        ip_address TEXT,
                        first_join TIMESTAMP,
                        last_join TIMESTAMP,
                        last_quit TIMESTAMP,
                        total_playtime INTEGER DEFAULT 0,
                        is_banned BOOLEAN DEFAULT 0,
                        is_whitelisted BOOLEAN DEFAULT 0,
                        is_op BOOLEAN DEFAULT 0,
                        permission_groups TEXT,
                        friends TEXT,
                        ignored_players TEXT,
                        last_message TEXT,
                        message_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # 玩家会话表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS player_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        player_uuid TEXT,
                        session_id TEXT UNIQUE,
                        join_time TIMESTAMP,
                        quit_time TIMESTAMP,
                        duration INTEGER,
                        ip_address TEXT,
                        FOREIGN KEY (player_uuid) REFERENCES players (uuid)
                    )
                """
                )

                # 玩家行为记录表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS player_actions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        player_uuid TEXT,
                        action_type TEXT,
                        timestamp TIMESTAMP,
                        details TEXT,
                        location_x REAL,
                        location_y REAL,
                        location_z REAL,
                        location_dimension TEXT,
                        FOREIGN KEY (player_uuid) REFERENCES players (uuid)
                    )
                """
                )

                # 玩家统计表
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS player_stats (
                        player_uuid TEXT,
                        stat_name TEXT,
                        stat_value INTEGER,
                        PRIMARY KEY (player_uuid, stat_name),
                        FOREIGN KEY (player_uuid) REFERENCES players (uuid)
                    )
                """
                )

                # 创建索引
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_players_name ON players (name)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_player ON player_sessions (player_uuid)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_actions_player ON player_actions (player_uuid)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_actions_type ON player_actions (action_type)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_actions_timestamp ON player_actions (timestamp)"
                )

                conn.commit()
                logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing database: {e}")

    async def get_player_info(
        self, player_identifier: str, use_cache: bool = True
    ) -> Optional[ExtendedPlayerInfo]:
        """
        获取扩展的玩家信息

        Args:
            player_identifier: 玩家名称或UUID
            use_cache: 是否使用缓存

        Returns:
            扩展玩家信息或None
        """
        # 检查缓存
        if use_cache and player_identifier in self._player_cache:
            cache_time = self._cache_timestamps.get(player_identifier)
            if (
                cache_time
                and (datetime.now() - cache_time).total_seconds() < self._cache_ttl
            ):
                return self._player_cache[player_identifier]

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 查询玩家基础信息
                if len(player_identifier) == 36 and "-" in player_identifier:
                    # UUID格式
                    cursor.execute(
                        "SELECT * FROM players WHERE uuid = ?", (player_identifier,)
                    )
                else:
                    # 玩家名格式
                    cursor.execute(
                        "SELECT * FROM players WHERE name = ?", (player_identifier,)
                    )

                row = cursor.fetchone()
                if not row:
                    return None

                # 获取列名
                columns = [description[0] for description in cursor.description]
                player_data = dict(zip(columns, row, strict=False))

                # 获取基础玩家数据
                basic_data = await self.player_manager.get_player_data(
                    player_data["uuid"]
                )

                # 构建扩展玩家信息
                player_info = ExtendedPlayerInfo(
                    name=player_data["name"],
                    uuid=player_data["uuid"],
                    display_name=player_data["display_name"] or player_data["name"],
                    ip_address=player_data["ip_address"] or "",
                    first_join=datetime.fromisoformat(player_data["first_join"])
                    if player_data["first_join"]
                    else datetime.now(),
                    last_join=datetime.fromisoformat(player_data["last_join"])
                    if player_data["last_join"]
                    else datetime.now(),
                    last_quit=datetime.fromisoformat(player_data["last_quit"])
                    if player_data["last_quit"]
                    else datetime.now(),
                    total_playtime=player_data["total_playtime"] or 0,
                    session_playtime=self._calculate_session_playtime(
                        player_data["uuid"]
                    ),
                    location=basic_data.location
                    if basic_data
                    else PlayerLocation(0, 0, 0, "overworld"),
                    stats=basic_data.stats if basic_data else PlayerStats(),
                    inventory=basic_data.inventory if basic_data else PlayerInventory(),
                    achievements=basic_data.achievements if basic_data else [],
                    advancements=basic_data.advancements if basic_data else {},
                    statistics=self._get_player_statistics(player_data["uuid"]),
                    is_online=player_data["uuid"] in self._online_players,
                    is_banned=bool(player_data["is_banned"]),
                    is_whitelisted=bool(player_data["is_whitelisted"]),
                    is_op=bool(player_data["is_op"]),
                    permission_groups=json.loads(
                        player_data["permission_groups"] or "[]"
                    ),
                    friends=json.loads(player_data["friends"] or "[]"),
                    ignored_players=json.loads(player_data["ignored_players"] or "[]"),
                    last_message=player_data["last_message"] or "",
                    message_count=player_data["message_count"] or 0,
                )

                # 更新缓存
                self._player_cache[player_identifier] = player_info
                self._player_cache[player_info.uuid] = player_info
                self._player_cache[player_info.name] = player_info
                self._cache_timestamps[player_identifier] = datetime.now()

                return player_info

        except Exception as e:
            logger.error(f"Error getting player info for {player_identifier}: {e}")
            return None

    def _calculate_session_playtime(self, player_uuid: str) -> int:
        """计算当前会话游戏时间"""
        session = self._player_sessions.get(player_uuid)
        if session and not session.quit_time:
            return int((datetime.now() - session.join_time).total_seconds())
        return 0

    def _get_player_statistics(self, player_uuid: str) -> dict[str, int]:
        """获取玩家统计数据"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT stat_name, stat_value FROM player_stats WHERE player_uuid = ?",
                    (player_uuid,),
                )

                stats = {}
                for row in cursor.fetchall():
                    stats[row[0]] = row[1]

                return stats

        except Exception as e:
            logger.error(f"Error getting player statistics: {e}")
            return {}

    async def record_player_join(
        self, player_name: str, player_uuid: str, ip_address: str
    ) -> bool:
        """
        记录玩家加入

        Args:
            player_name: 玩家名称
            player_uuid: 玩家UUID
            ip_address: IP地址

        Returns:
            是否成功
        """
        try:
            join_time = datetime.now()
            session_id = f"{player_uuid}_{int(time.time())}"

            # 创建会话记录
            session = PlayerSession(
                player_uuid=player_uuid,
                session_id=session_id,
                join_time=join_time,
                quit_time=None,
                duration=0,
                ip_address=ip_address,
            )

            self._player_sessions[player_uuid] = session

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 更新或插入玩家基础信息
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO players
                    (uuid, name, ip_address, first_join, last_join, updated_at)
                    VALUES (?, ?, ?,
                        COALESCE((SELECT first_join FROM players WHERE uuid = ?), ?),
                        ?, ?)
                """,
                    (
                        player_uuid,
                        player_name,
                        ip_address,
                        player_uuid,
                        join_time,
                        join_time,
                        join_time,
                    ),
                )

                # 插入会话记录
                cursor.execute(
                    """
                    INSERT INTO player_sessions
                    (player_uuid, session_id, join_time, ip_address)
                    VALUES (?, ?, ?, ?)
                """,
                    (player_uuid, session_id, join_time, ip_address),
                )

                conn.commit()

            # 记录行为
            await self._record_action(
                player_uuid,
                "join",
                {"ip_address": ip_address, "session_id": session_id},
            )

            # 清除缓存
            self._clear_player_cache(player_uuid, player_name)

            logger.info(f"Player join recorded: {player_name} ({player_uuid})")
            return True

        except Exception as e:
            logger.error(f"Error recording player join: {e}")
            return False

    async def record_player_quit(self, player_name: str, player_uuid: str) -> bool:
        """
        记录玩家退出

        Args:
            player_name: 玩家名称
            player_uuid: 玩家UUID

        Returns:
            是否成功
        """
        try:
            quit_time = datetime.now()
            session = self._player_sessions.get(player_uuid)

            if session:
                session.quit_time = quit_time
                session.duration = int((quit_time - session.join_time).total_seconds())

                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()

                    # 更新会话记录
                    cursor.execute(
                        """
                        UPDATE player_sessions
                        SET quit_time = ?, duration = ?
                        WHERE session_id = ?
                    """,
                        (quit_time, session.duration, session.session_id),
                    )

                    # 更新玩家总游戏时间
                    cursor.execute(
                        """
                        UPDATE players
                        SET last_quit = ?,
                            total_playtime = total_playtime + ?,
                            updated_at = ?
                        WHERE uuid = ?
                    """,
                        (quit_time, session.duration, quit_time, player_uuid),
                    )

                    conn.commit()

                # 移除会话
                del self._player_sessions[player_uuid]

            # 记录行为
            await self._record_action(player_uuid, "quit", {})

            # 清除缓存
            self._clear_player_cache(player_uuid, player_name)

            logger.info(f"Player quit recorded: {player_name} ({player_uuid})")
            return True

        except Exception as e:
            logger.error(f"Error recording player quit: {e}")
            return False

    async def _record_action(
        self,
        player_uuid: str,
        action_type: str,
        details: dict[str, Any],
        location: PlayerLocation = None,
    ):
        """记录玩家行为"""
        try:
            action = PlayerAction(
                player_uuid=player_uuid,
                action_type=action_type,
                timestamp=datetime.now(),
                details=details,
                location=location,
            )

            self._action_history.append(action)

            # 限制历史记录大小
            if len(self._action_history) > self._max_action_history:
                self._action_history.pop(0)

            # 保存到数据库
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO player_actions
                    (player_uuid, action_type, timestamp, details,
                     location_x, location_y, location_z, location_dimension)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        player_uuid,
                        action_type,
                        action.timestamp,
                        json.dumps(details),
                        location.x if location else None,
                        location.y if location else None,
                        location.z if location else None,
                        location.dimension if location else None,
                    ),
                )
                conn.commit()

        except Exception as e:
            logger.error(f"Error recording action: {e}")

    def _clear_player_cache(self, player_uuid: str, player_name: str):
        """清除玩家缓存"""
        for key in [player_uuid, player_name]:
            self._player_cache.pop(key, None)
            self._cache_timestamps.pop(key, None)

    async def get_online_players(self) -> list[ExtendedPlayerInfo]:
        """获取在线玩家列表"""
        online_players = []
        for player_uuid in self._player_sessions:
            player_info = await self.get_player_info(player_uuid)
            if player_info:
                online_players.append(player_info)
        return online_players

    async def get_player_history(
        self,
        player_uuid: str,
        action_types: list[str] | None = None,
        limit: int = 100,
        days: int = 30,
    ) -> list[PlayerAction]:
        """
        获取玩家历史行为

        Args:
            player_uuid: 玩家UUID
            action_types: 行为类型过滤器
            limit: 返回的最大记录数
            days: 查询天数

        Returns:
            玩家行为列表
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                query = """
                    SELECT player_uuid, action_type, timestamp, details,
                           location_x, location_y, location_z, location_dimension
                    FROM player_actions
                    WHERE player_uuid = ? AND timestamp >= ?
                """
                params = [player_uuid, cutoff_date]

                if action_types:
                    placeholders = ",".join(["?" for _ in action_types])
                    query += f" AND action_type IN ({placeholders})"
                    params.extend(action_types)

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)

                actions = []
                for row in cursor.fetchall():
                    location = None
                    if row[4] is not None:  # location_x
                        location = PlayerLocation(
                            x=row[4], y=row[5], z=row[6], dimension=row[7]
                        )

                    action = PlayerAction(
                        player_uuid=row[0],
                        action_type=row[1],
                        timestamp=datetime.fromisoformat(row[2]),
                        details=json.loads(row[3]) if row[3] else {},
                        location=location,
                    )
                    actions.append(action)

                return actions

        except Exception as e:
            logger.error(f"Error getting player history: {e}")
            return []

    async def get_server_statistics(self) -> dict[str, Any]:
        """获取服务器统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 总玩家数
                cursor.execute("SELECT COUNT(*) FROM players")
                total_players = cursor.fetchone()[0]

                # 今日加入的玩家数
                today = datetime.now().date()
                cursor.execute(
                    "SELECT COUNT(*) FROM players WHERE DATE(first_join) = ?", (today,)
                )
                new_players_today = cursor.fetchone()[0]

                # 本周活跃玩家数
                week_ago = datetime.now() - timedelta(days=7)
                cursor.execute(
                    "SELECT COUNT(*) FROM players WHERE last_join >= ?", (week_ago,)
                )
                active_players_week = cursor.fetchone()[0]

                # 平均游戏时间
                cursor.execute(
                    "SELECT AVG(total_playtime) FROM players WHERE total_playtime > 0"
                )
                avg_playtime = cursor.fetchone()[0] or 0

                # 当前在线玩家数
                online_count = len(self._player_sessions)

                # 最受欢迎的游戏模式
                cursor.execute(
                    """
                    SELECT details, COUNT(*) as count
                    FROM player_actions
                    WHERE action_type = 'gamemode_change'
                    GROUP BY details
                    ORDER BY count DESC
                    LIMIT 1
                """
                )
                popular_gamemode_row = cursor.fetchone()
                popular_gamemode = "survival"  # 默认值
                if popular_gamemode_row:
                    try:
                        details = json.loads(popular_gamemode_row[0])
                        popular_gamemode = details.get("gamemode", "survival")
                    except Exception:
                        pass

                return {
                    "total_players": total_players,
                    "new_players_today": new_players_today,
                    "active_players_week": active_players_week,
                    "online_players": online_count,
                    "avg_playtime_hours": avg_playtime / 3600 if avg_playtime else 0,
                    "popular_gamemode": popular_gamemode,
                    "total_sessions": len(self._action_history),
                    "last_updated": datetime.now().isoformat(),
                }

        except Exception as e:
            logger.error(f"Error getting server statistics: {e}")
            return {}

    async def search_players(
        self, query: str, online_only: bool = False, limit: int = 50
    ) -> list[ExtendedPlayerInfo]:
        """
        搜索玩家

        Args:
            query: 搜索查询
            online_only: 仅搜索在线玩家
            limit: 返回的最大结果数

        Returns:
            匹配的玩家列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                sql_query = """
                    SELECT uuid FROM players
                    WHERE name LIKE ? OR display_name LIKE ?
                """
                params = [f"%{query}%", f"%{query}%"]

                if online_only:
                    online_uuids = list(self._player_sessions.keys())
                    if not online_uuids:
                        return []

                    placeholders = ",".join(["?" for _ in online_uuids])
                    sql_query += f" AND uuid IN ({placeholders})"
                    params.extend(online_uuids)

                sql_query += " ORDER BY last_join DESC LIMIT ?"
                params.append(limit)

                cursor.execute(sql_query, params)

                players = []
                for row in cursor.fetchall():
                    player_info = await self.get_player_info(row[0])
                    if player_info:
                        players.append(player_info)

                return players

        except Exception as e:
            logger.error(f"Error searching players: {e}")
            return []

    async def update_player_statistics(self, player_uuid: str, stats: dict[str, int]):
        """
        更新玩家统计数据

        Args:
            player_uuid: 玩家UUID
            stats: 统计数据字典
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                for stat_name, stat_value in stats.items():
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO player_stats
                        (player_uuid, stat_name, stat_value)
                        VALUES (?, ?, ?)
                    """,
                        (player_uuid, stat_name, stat_value),
                    )

                conn.commit()

            # 清除缓存
            self._clear_player_cache(player_uuid, "")

        except Exception as e:
            logger.error(f"Error updating player statistics: {e}")

    async def ban_player(
        self, player_uuid: str, reason: str = "", admin_uuid: str = ""
    ):
        """封禁玩家"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE players
                    SET is_banned = 1, updated_at = ?
                    WHERE uuid = ?
                """,
                    (datetime.now(), player_uuid),
                )
                conn.commit()

            await self._record_action(
                player_uuid, "ban", {"reason": reason, "admin_uuid": admin_uuid}
            )

            self._clear_player_cache(player_uuid, "")

        except Exception as e:
            logger.error(f"Error banning player: {e}")

    async def unban_player(self, player_uuid: str, admin_uuid: str = ""):
        """解封玩家"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE players
                    SET is_banned = 0, updated_at = ?
                    WHERE uuid = ?
                """,
                    (datetime.now(), player_uuid),
                )
                conn.commit()

            await self._record_action(player_uuid, "unban", {"admin_uuid": admin_uuid})

            self._clear_player_cache(player_uuid, "")

        except Exception as e:
            logger.error(f"Error unbanning player: {e}")

    def get_cache_statistics(self) -> dict[str, Any]:
        """获取缓存统计信息"""
        return {
            "cached_players": len(self._player_cache),
            "online_sessions": len(self._player_sessions),
            "action_history_size": len(self._action_history),
            "cache_ttl_seconds": self._cache_ttl,
            "max_action_history": self._max_action_history,
        }
