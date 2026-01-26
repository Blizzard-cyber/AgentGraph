from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import zipfile

import aiohttp
from fastmcp import Client as FastMCPClient

from app.core.config import settings

logger = logging.getLogger(__name__)


_ROOT = Path(__file__).resolve().parents[3]  # .../mag/app/services/mcp2 -> repo root
_MCP_SERVERS_DIR = _ROOT / "mcp_servers"
_MCP_STATE_DIR = _ROOT / "mcp_servers" / ".state"
_MCP_USER_SERVERS_FILE = _MCP_STATE_DIR / "user_servers.json"


def _utcnow() -> datetime:
    return datetime.utcnow()


def _safe_name(name: str) -> str:
    keep = []
    for ch in name.strip():
        if ch.isalnum() or ch in ("-", "_", "."):
            keep.append(ch)
        else:
            keep.append("_")
    out = "".join(keep).strip("_")
    return out or "server"


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _script_target_path(server_name: str, version: str) -> Path:
    # Layout: mcp_servers/{server_name}/{version}/server.py
    safe = _safe_name(server_name)
    return _MCP_SERVERS_DIR / safe / version / "server.py"


@dataclass
class RegisteredServer:
    server_name: str
    version: str
    script_path: Path
    created_at: datetime
    updated_at: datetime
    owner_user_id: Optional[str] = None


@dataclass
class ConnectionUsage:
    conversation_id: str
    last_comm_time: datetime


@dataclass
class ConnectionEntry:
    user_id: str
    usages: List[ConnectionUsage]


@dataclass
class ClientEntry:
    """In-memory client instance wrapper."""

    client: FastMCPClient
    server_name: str
    version: str
    created_at: datetime
    last_used_at: datetime
    connections: List[ConnectionEntry]
    lock: asyncio.Lock


@dataclass
class TaskEntry:
    task_type: str  # add_server | connect
    status: str  # started | downloading | registering | connecting | complete | error
    message: Optional[str]
    updated_at: datetime
    result: Optional[Dict[str, Any]]
    runner: Optional[asyncio.Task]


@dataclass
class UserServerEntry:
    server_name: str
    version: str
    added_at: datetime
    download_url: Optional[str] = None


class MCP2Manager:
    """New MCP manager.

    Core tables:
    1) server_registry (in-memory): {(server_name, version) -> RegisteredServer}
       - System-level registry of available servers and their script paths.
    2) user_servers (disk-backed via mcp_servers/.state/user_servers.json):
       - Single source of truth for which servers a user has added.
    3) client_table (in-memory): {(server_name, version) -> ClientEntry}
       - Runtime cache of FastMCPClient instances + per-user connection usages.

     Notes /补充:
     - We keep registry and client_table keyed by (server_name, version) to match your `serverName:version` requirement.
     - Concurrency: per-client lock avoids concurrent tool calls and concurrent connect/close.
     """

    def __init__(self) -> None:
        self.server_registry: Dict[Tuple[str, str], RegisteredServer] = {}
        self.client_table: Dict[Tuple[str, str], ClientEntry] = {}
        self.user_servers: Dict[str, Dict[Tuple[str, str], UserServerEntry]] = {}  # user_id -> {(server,version): entry}
        self.task_table: Dict[Tuple[str, str, str], TaskEntry] = {}  # (user_id, server_name, version)
        self.tool_index: Dict[str, Tuple[str, str]] = {}  # tool_name -> (server_name, version)
        self._task_lock = asyncio.Lock()
        self._user_servers_lock = asyncio.Lock()
        self._registry_lock = asyncio.Lock()
        self._user_servers_loaded = False

        # Idle cleanup (optional): close clients that have no active connections and haven't been used recently.
        self.idle_timeout = timedelta(minutes=30)
        self.cleanup_interval = timedelta(minutes=5)
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_stop = asyncio.Event()

        # Cleanup loop is started lazily during FastAPI startup (requires a running event loop).
        # See app.services.mcp2.mcp2_init.init_mcp2_state()

    def start_cleanup_loop(self) -> None:
        """Start the background cleanup loop.

        Must be called when an event loop is running (e.g., inside FastAPI lifespan/startup).
        """
        if self._cleanup_task and not self._cleanup_task.done():
            return
        self._cleanup_stop.clear()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_loop(self) -> None:
        """Stop the background cleanup loop (mainly for tests/shutdown)."""
        self._cleanup_stop.set()
        t = self._cleanup_task
        if t and not t.done():
            try:
                await t
            except Exception:
                pass

    async def _cleanup_loop(self) -> None:
        while not self._cleanup_stop.is_set():
            try:
                await asyncio.sleep(self.cleanup_interval.total_seconds())
                await self.cleanup_idle_clients()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("mcp2 idle cleanup loop error")

    async def cleanup_idle_clients(self) -> None:
        """Close and remove idle clients.

        Rule:
        - Only consider entries with NO active connections.
        - If now - last_used_at >= idle_timeout, close and remove.
        """
        now = _utcnow()

        # snapshot keys to avoid mutating while iterating
        async with self._registry_lock:
            items = list(self.client_table.items())

        for key, entry in items:
            # If any connection exists, do not auto-close.
            if entry.connections:
                continue

            if (now - entry.last_used_at) < self.idle_timeout:
                continue

            # Lock per-entry to avoid racing with call_tool/connect
            async with entry.lock:
                # re-check under lock
                if entry.connections:
                    continue
                if (now - entry.last_used_at) < self.idle_timeout:
                    continue
                try:
                    await entry.client.close()
                except Exception:
                    logger.exception(f"Failed to close idle client {entry.server_name}:{entry.version}")
                finally:
                    async with self._registry_lock:
                        self.client_table.pop(key, None)

    def _task_key(self, user_id: str, server_name: str, version: str) -> Tuple[str, str, str]:
        return (user_id, server_name, version)

    async def get_task_status(self, *, user_id: str, server_name: str, version: str) -> Optional[TaskEntry]:
        async with self._task_lock:
            return self.task_table.get(self._task_key(user_id, server_name, version))

    async def _set_task(self, *, user_id: str, server_name: str, version: str, task_type: str, status: str,
                        message: str | None = None, result: Dict[str, Any] | None = None,
                        runner: asyncio.Task | None = None) -> TaskEntry:
        async with self._task_lock:
            k = self._task_key(user_id, server_name, version)
            entry = self.task_table.get(k)
            if entry is None:
                entry = TaskEntry(
                    task_type=task_type,
                    status=status,
                    message=message,
                    updated_at=_utcnow(),
                    result=result,
                    runner=runner,
                )
                self.task_table[k] = entry
            else:
                entry.task_type = task_type
                entry.status = status
                entry.message = message
                entry.updated_at = _utcnow()
                entry.result = result
                if runner is not None:
                    entry.runner = runner
            return entry

    async def _ensure_state_dir(self) -> None:
        _MCP_STATE_DIR.mkdir(parents=True, exist_ok=True)

    async def _load_user_servers_from_disk(self) -> None:
        await self._ensure_state_dir()
        if not _MCP_USER_SERVERS_FILE.exists():
            async with self._user_servers_lock:
                self._user_servers_loaded = True
            return
        try:
            txt = _MCP_USER_SERVERS_FILE.read_text(encoding="utf-8").strip()
            if not txt:
                raw = {}
            else:
                raw = json.loads(txt)
        except Exception:
            # 解析失败也不要卡死：标记为已加载，使用空结构继续
            logger.exception("Failed to load user_servers.json; fallback to empty")
            async with self._user_servers_lock:
                self.user_servers = {}
                self._user_servers_loaded = True
            return

        # structure: { user_id: [ {server_name, version, added_at, download_url} ] }
        async with self._user_servers_lock:
            for user_id, items in (raw or {}).items():
                per: Dict[Tuple[str, str], UserServerEntry] = {}
                for it in items or []:
                    try:
                        s = str(it.get("server_name"))
                        v = str(it.get("version"))
                        added_at = it.get("added_at")
                        dt = datetime.fromisoformat(added_at) if added_at else _utcnow()
                        per[(s, v)] = UserServerEntry(
                            server_name=s,
                            version=v,
                            added_at=dt,
                            download_url=it.get("download_url"),
                        )
                    except Exception:
                        continue
                if per:
                    self.user_servers[user_id] = per
            self._user_servers_loaded = True

    async def _save_user_servers_to_disk(self) -> None:
        await self._ensure_state_dir()
        async with self._user_servers_lock:
            raw: Dict[str, list[dict[str, Any]]] = {}
            for user_id, per in self.user_servers.items():
                raw[user_id] = [
                    {
                        "server_name": e.server_name,
                        "version": e.version,
                        "added_at": e.added_at.isoformat(),
                        "download_url": e.download_url,
                    }
                    for e in per.values()
                ]
        try:
            _MCP_USER_SERVERS_FILE.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("Failed to save user_servers.json")

    async def _ensure_user_servers_loaded(self) -> None:
        async with self._user_servers_lock:
            loaded = self._user_servers_loaded
        if not loaded:
            await self._load_user_servers_from_disk()

    async def add_user_server(self, *, user_id: str, server_name: str, version: str, download_url: Optional[str] = None) -> None:
        await self._ensure_user_servers_loaded()
        async with self._user_servers_lock:
            per = self.user_servers.setdefault(user_id, {})
            per[(server_name, version)] = UserServerEntry(
                server_name=server_name,
                version=version,
                added_at=_utcnow(),
                download_url=download_url,
            )
        await self._save_user_servers_to_disk()

    async def remove_user_server(self, *, user_id: str, server_name: str, version: str) -> None:
        await self._ensure_user_servers_loaded()
        async with self._user_servers_lock:
            per = self.user_servers.get(user_id)
            if per and (server_name, version) in per:
                per.pop((server_name, version), None)
        await self._save_user_servers_to_disk()

    async def list_user_servers_with_status(self, user_id: str) -> List[Dict[str, Any]]:
        await self._ensure_user_servers_loaded()
        async with self._user_servers_lock:
            per = self.user_servers.get(user_id, {})
            out: List[Dict[str, Any]] = []
            for (srv, ver), entry in per.items():
                connected = False
                # client_table belongs to registry lock
                client = self.client_table.get((srv, ver))
                if client and client.connections:
                    # connected for this user if user_id exists in connections
                    connected = any(c.user_id == user_id for c in client.connections)
                out.append(
                    {
                        "server_name": srv,
                        "version": ver,
                        "added_at": entry.added_at.isoformat(),
                        "download_url": entry.download_url,
                        "connected": connected,
                        "tools_count": 0,
                    }
                )
            return sorted(out, key=lambda x: (x["server_name"], x["version"]))

    async def ensure_dirs(self) -> None:
        """Ensure required directories exist."""
        _MCP_SERVERS_DIR.mkdir(parents=True, exist_ok=True)
        await self._ensure_state_dir()

    async def _rebuild_registry_from_disk(self) -> None:
        """Rebuild server_registry from files under mcp_servers.

        This fixes the main restart issue: server_registry is in-memory and gets cleared on process restart,
        while mcp_servers/{server}/{version}/server.py persists.

        We scan and register any discovered server.py as (server_name, version).
        """
        await self.ensure_dirs()
        now = _utcnow()
        async with self._registry_lock:
            for server_dir in _MCP_SERVERS_DIR.iterdir():
                if not server_dir.is_dir() or server_dir.name.startswith('.'):
                    continue
                server_name = server_dir.name
                for version_dir in server_dir.iterdir():
                    if not version_dir.is_dir() or version_dir.name.startswith('.'):
                        continue
                    version = version_dir.name
                    script_path = version_dir / 'server.py'
                    if not script_path.exists():
                        continue
                    key = (server_name, version)
                    existing = self.server_registry.get(key)
                    if existing is None:
                        self.server_registry[key] = RegisteredServer(
                            server_name=server_name,
                            version=version,
                            script_path=script_path,
                            created_at=now,
                            updated_at=now,
                            owner_user_id=None,
                        )
                    else:
                        # keep owner_user_id as-is, but refresh path/timestamps
                        existing.script_path = script_path
                        existing.updated_at = now

    async def _ensure_server_registered(self, *, server_name: str, version: str) -> Optional[RegisteredServer]:
        """Ensure (server_name, version) exists in server_registry, rebuilding from disk if needed."""
        key = (server_name, version)
        async with self._registry_lock:
            srv = self.server_registry.get(key)
        if srv is not None:
            return srv

        # rebuild once (cheap for small folders) then re-check
        await self._rebuild_registry_from_disk()
        async with self._registry_lock:
            return self.server_registry.get(key)

    async def clear_task(self, *, user_id: str, server_name: str, version: str) -> None:
        """Clear task_table entry for a given user/server/version (best-effort)."""
        async with self._task_lock:
            self.task_table.pop((user_id, server_name, version), None)

    def _touch_connection(self, entry: ClientEntry, *, user_id: str, conversation_id: str) -> None:
        """Update entry.connections last communication time.

        This is a runtime-only table (client_table). After restart it will be empty; that's fine.
        """
        now = _utcnow()
        for ce in entry.connections:
            if ce.user_id != user_id:
                continue
            for use in ce.usages:
                if use.conversation_id == conversation_id:
                    use.last_comm_time = now
                    return
            ce.usages.append(ConnectionUsage(conversation_id=conversation_id, last_comm_time=now))
            return

        entry.connections.append(
            ConnectionEntry(
                user_id=user_id,
                usages=[ConnectionUsage(conversation_id=conversation_id, last_comm_time=now)],
            )
        )

    async def call_tool(
        self,
        *,
        server_name: str,
        version: str,
        tool_name: str,
        params: Dict[str, Any],
        user_id: str,
        conversation_id: str,
    ) -> Any:
        """Call a tool via FastMCP client (client_example-compatible)."""
        key = (server_name, version)

        server = await self._ensure_server_registered(server_name=server_name, version=version)
        if not server:
            raise KeyError(f"server not registered: {server_name}:{version}")

        async with self._registry_lock:
            entry = self.client_table.get(key)
            if entry is None:
                client = FastMCPClient(str(server.script_path))
                entry = ClientEntry(
                    client=client,
                    server_name=server_name,
                    version=version,
                    created_at=_utcnow(),
                    last_used_at=_utcnow(),
                    connections=[],
                    lock=asyncio.Lock(),
                )
                self.client_table[key] = entry

        async with entry.lock:
            async with entry.client:
                result = await entry.client.call_tool(tool_name, params)

            entry.last_used_at = _utcnow()
            self._touch_connection(entry, user_id=user_id, conversation_id=conversation_id)

        return result

    async def start_add_server_task(
        self,
        *,
        user_id: str,
        server_key: str,
    ) -> TaskEntry:
        """Unified add_server.

        Now server_key is "modelName:version".
        We resolve download URL via FILE_SYSTEM service:
        - GET /models/mcps to find id
        - GET /models/{id}/download to get real download URL
        Then download zip bytes, extract, and register as before.
         """
        if not server_key or ":" not in server_key:
            return await self._set_task(
                user_id=user_id,
                server_name=server_key or "",
                version="",
                task_type="add_server",
                status="error",
                message="server_name must be in format 'modelName:version'",
            )

        server_name, version = server_key.split(":", 1)
        key_sv = (server_name, version)

        # Resolve download_url synchronously before starting runner so errors are visible quickly
        try:
            download_url = await self._resolve_download_url_from_file_system(model_name=server_name, version=version)
        except Exception as e:
            return await self._set_task(
                user_id=user_id,
                server_name=server_name,
                version=version,
                task_type="add_server",
                status="error",
                message=str(e),
            )

        # ensure list presence immediately ("added" state)
        await self.add_user_server(user_id=user_id, server_name=server_name, version=version, download_url=download_url)

        # clear any stale task status from previous runs (e.g., previously failed connect/add)
        await self.clear_task(user_id=user_id, server_name=server_name, version=version)

        # If already registered, just mark complete.
        async with self._registry_lock:
            existing = self.server_registry.get(key_sv)
        if existing is not None:
            return await self._set_task(
                user_id=user_id,
                server_name=server_name,
                version=version,
                task_type="add_server",
                status="complete",
                message="server already exists, claimed",
                result={
                    "server_name": existing.server_name,
                    "version": existing.version,
                    "script_path": str(existing.script_path),
                },
            )

        # If a previous add_server task is still running for this same key, do not start another.
        async with self._task_lock:
            existing_task = self.task_table.get(self._task_key(user_id, server_name, version))
            if existing_task and existing_task.task_type == 'add_server' and existing_task.runner and not existing_task.runner.done():
                return existing_task

        async def _runner():
            try:
                await self._set_task(
                    user_id=user_id,
                    server_name=server_name,
                    version=version,
                    task_type="add_server",
                    status="downloading",
                    message="downloading zip package",
                )

                zip_bytes = await self._download_bytes(download_url)

                await self._set_task(
                    user_id=user_id,
                    server_name=server_name,
                    version=version,
                    task_type="add_server",
                    status="extracting",
                    message="extracting zip package",
                )

                await self.ensure_dirs()
                target_dir = _script_target_path(server_name, version).parent
                server_py = self._extract_zip_to_dir(zip_bytes=zip_bytes, target_dir=target_dir)

                await self._set_task(
                    user_id=user_id,
                    server_name=server_name,
                    version=version,
                    task_type="add_server",
                    status="registering",
                    message="registering server",
                )

                async with self._registry_lock:
                    now = _utcnow()
                    self.server_registry[key_sv] = RegisteredServer(
                        server_name=server_name,
                        version=version,
                        script_path=server_py,
                        created_at=now,
                        updated_at=now,
                        owner_user_id=user_id,
                    )

                await self._set_task(
                    user_id=user_id,
                    server_name=server_name,
                    version=version,
                    task_type="add_server",
                    status="complete",
                    message="downloaded, extracted, and registered",
                    result={
                        "server_name": server_name,
                        "version": version,
                        "script_path": str(server_py),
                    },
                )
            except Exception as e:
                await self._set_task(
                    user_id=user_id,
                    server_name=server_name,
                    version=version,
                    task_type="add_server",
                    status="error",
                    message=str(e),
                )

        runner_task = asyncio.create_task(_runner())
        return await self._set_task(
            user_id=user_id,
            server_name=server_name,
            version=version,
            task_type="add_server",
            status="started",
            message="task started",
            runner=runner_task,
        )

    async def start_connect_task(
        self,
        *,
        user_id: str,
        server_name: str,
        version: str,
        conversation_id: str,
    ) -> TaskEntry:
        """Async connect.

        Only after FastMCP client can be created + list_tools succeeds, we record the connection.
        """

        srv = await self._ensure_server_registered(server_name=server_name, version=version)
        if srv is None:
            return await self._set_task(
                user_id=user_id,
                server_name=server_name,
                version=version,
                task_type="connect",
                status="error",
                message=f"server not registered: {server_name}:{version}",
            )

        # if previous task errored, allow a new attempt by overwriting (do not keep stale error forever)
        existing_task = await self.get_task_status(user_id=user_id, server_name=server_name, version=version)
        if existing_task and existing_task.task_type == 'connect' and existing_task.status == 'error':
            await self.clear_task(user_id=user_id, server_name=server_name, version=version)

        async with self._registry_lock:
            # already running?
            k = self._task_key(user_id, server_name, version)
            t = self.task_table.get(k)
            if t and t.runner and not t.runner.done() and t.task_type == "connect":
                return t

        async def _runner():
            try:
                await self._set_task(
                    user_id=user_id,
                    server_name=server_name,
                    version=version,
                    task_type="connect",
                    status="connecting",
                    message="starting client and listing tools",
                )

                tools = await self._connect_and_list_tools(
                    server_name=server_name,
                    version=version,
                    user_id=user_id,
                    conversation_id=conversation_id,
                )

                await self._set_task(
                    user_id=user_id,
                    server_name=server_name,
                    version=version,
                    task_type="connect",
                    status="complete",
                    message="connected",
                    result={"tools": tools},
                )
            except Exception as e:
                await self._set_task(
                    user_id=user_id,
                    server_name=server_name,
                    version=version,
                    task_type="connect",
                    status="error",
                    message=str(e),
                )

        runner_task = asyncio.create_task(_runner())
        return await self._set_task(
            user_id=user_id,
            server_name=server_name,
            version=version,
            task_type="connect",
            status="started",
            message="task started",
            runner=runner_task,
        )

    async def _write_and_register_versioned(self, *, server_name: str, version: str, content: bytes, user_id: str) -> RegisteredServer:
        await self.ensure_dirs()
        target = _script_target_path(server_name, version)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(content)

        async with self._registry_lock:
            key = (server_name, version)
            now = _utcnow()
            if key not in self.server_registry:
                self.server_registry[key] = RegisteredServer(
                    server_name=server_name,
                    version=version,
                    script_path=target,
                    created_at=now,
                    updated_at=now,
                    owner_user_id=user_id,
                )
            else:
                self.server_registry[key].updated_at = now

            return self.server_registry[key]

    async def _index_tools(self, *, server_name: str, version: str, tools: List[Dict[str, Any]]) -> None:
        async with self._registry_lock:
            for t in tools:
                name = t.get("name") if isinstance(t, dict) else None
                if name:
                    self.tool_index[name] = (server_name, version)

    async def _connect_and_list_tools(self, *, server_name: str, version: str, user_id: str, conversation_id: str) -> List[Dict[str, Any]]:
        """Internal connect (sync) used by async task runner."""
        key = (server_name, version)

        # create or reuse client instance
        server = await self._ensure_server_registered(server_name=server_name, version=version)
        if not server:
            raise KeyError(f"server not registered: {server_name}:{version}")

        async with self._registry_lock:
            entry = self.client_table.get(key)
            if entry is None:
                client = FastMCPClient(str(server.script_path))
                entry = ClientEntry(
                    client=client,
                    server_name=server_name,
                    version=version,
                    created_at=_utcnow(),
                    last_used_at=_utcnow(),
                    connections=[],
                    lock=asyncio.Lock(),
                )
                self.client_table[key] = entry

        async with entry.lock:
            # strict: only mark connection after list_tools succeeded
            async with entry.client:
                tools = await entry.client.list_tools()

            entry.last_used_at = _utcnow()
            self._touch_connection(entry, user_id=user_id, conversation_id=conversation_id)

        out = []
        for t in tools:
            out.append(
                {
                    "name": getattr(t, "name", ""),
                    "description": getattr(t, "description", ""),
                    "input_schema": getattr(t, "inputSchema", None),
                }
            )

        # index tools for routing
        await self._index_tools(server_name=server_name, version=version, tools=out)

        return out

    async def debug_dump_connections(self) -> List[Dict[str, Any]]:
        """Debug helper: dump current client_table connections."""
        async with self._registry_lock:
            out: List[Dict[str, Any]] = []
            for (srv, ver), entry in self.client_table.items():
                out.append(
                    {
                        "server_name": srv,
                        "version": ver,
                        "created_at": entry.created_at.isoformat(),
                        "last_used_at": entry.last_used_at.isoformat(),
                        "connections": [
                            {
                                "user_id": c.user_id,
                                "usages": [
                                    {
                                        "conversation_id": u.conversation_id,
                                        "last_comm_time": u.last_comm_time.isoformat(),
                                    }
                                    for u in c.usages
                                ],
                            }
                            for c in entry.connections
                        ],
                    }
                )
            return out

    # --- keep existing public methods for compatibility ---

    async def download_and_register(self, *, server_name: str, download_url: str, user_id: str) -> RegisteredServer:
        """(legacy helper) preserve old behavior: compute version from content hash."""
        await self.ensure_dirs()
        content = await self._download_bytes(download_url)
        version = _sha256_bytes(content)[:12]
        return await self._write_and_register_versioned(server_name=server_name, version=version, content=content, user_id=user_id)

    async def connect(self, *, server_name: str, version: str, user_id: str, conversation_id: str) -> List[Dict[str, Any]]:
        """(legacy helper) sync connect; delegates to internal method."""
        return await self._connect_and_list_tools(server_name=server_name, version=version, user_id=user_id, conversation_id=conversation_id)

    async def disconnect(
        self,
        *,
        server_name: str,
        version: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        remove_from_user_servers: bool = False,
    ) -> None:
        """Disconnect + optional remove from user's server list.

        - Always removes connection usage from in-memory connection table.
        - If conversation_id is None: remove ALL usages for this user.
        - If remove_from_user_servers=True, also removes from disk-backed user_servers.json.
        """
        # First remove connection usage (existing logic)
        key = (server_name, version)
        entry = self.client_table.get(key)
        if entry is not None:
            async with entry.lock:
                new_connections: List[ConnectionEntry] = []
                for ce in entry.connections:
                    if ce.user_id != user_id:
                        new_connections.append(ce)
                        continue

                    # conversation_id None => remove all usages for this user
                    if conversation_id is None:
                        continue

                    new_usages = [u for u in ce.usages if u.conversation_id != conversation_id]
                    if new_usages:
                        new_connections.append(ConnectionEntry(user_id=ce.user_id, usages=new_usages))

                entry.connections = new_connections

                if not entry.connections:
                    try:
                        await entry.client.close()
                    finally:
                        async with self._registry_lock:
                            self.client_table.pop(key, None)

        if remove_from_user_servers:
            await self.remove_user_server(user_id=user_id, server_name=server_name, version=version)

    async def remove_user_server_fully(self, *, user_id: str, server_name: str, version: str) -> None:
        """Remove all information for a user about a server.

        Semantics required by you:
        - Remove from user_servers.json (so it disappears after refresh)
        - Remove any connections/usages for this user; if no connections left, close client and remove from client_table
        - Keep server_registry entry (server still exists)
        """
        # Remove connections + optionally close client
        await self.disconnect(
            server_name=server_name,
            version=version,
            user_id=user_id,
            conversation_id=None,
            remove_from_user_servers=True,
        )
        await self.clear_task(user_id=user_id, server_name=server_name, version=version)

    async def _download_bytes(self, download_url: str) -> bytes:
        """Download bytes from URL.

        The download target is expected to be a zip archive.
        """
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(download_url) as resp:
                if resp.status != 200:
                    try:
                        text = await resp.text()
                    except Exception:
                        text = ""
                    raise RuntimeError(f"download failed: HTTP {resp.status}: {text[:200]}")
                return await resp.read()

    def _extract_zip_to_dir(self, *, zip_bytes: bytes, target_dir: Path) -> Path:
        """Extract zip bytes into target_dir and delete the temporary zip.

        Expects an entrypoint file named 'server.py' to exist in target_dir after extraction.
        """
        target_dir.mkdir(parents=True, exist_ok=True)
        zip_path = target_dir / "package.zip"
        zip_path.write_bytes(zip_bytes)

        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # basic zip-slip protection
                for member in zf.namelist():
                    p = Path(member)
                    if p.is_absolute() or ".." in p.parts:
                        raise RuntimeError(f"unsafe zip entry: {member}")
                zf.extractall(target_dir)
        finally:
            try:
                zip_path.unlink(missing_ok=True)
            except Exception:
                pass

        server_py = target_dir / "server.py"
        if not server_py.exists():
            raise RuntimeError(f"server.py not found after extracting zip into {target_dir}")
        return server_py

    async def _fetch_mcp_models(self) -> List[Dict[str, Any]]:
        """Fetch MCP model list from FILE_SYSTEM service."""
        url = f"{settings.FILE_SYSTEM_BASE_URL}/models/mcps"
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"FILE_SYSTEM models/mcps failed: HTTP {resp.status}: {text[:200]}")
                data = await resp.json()
                if not isinstance(data, list):
                    raise RuntimeError("FILE_SYSTEM models/mcps returned non-list")
                return data

    async def _resolve_download_url_from_file_system(self, *, model_name: str, version: str) -> str:
        """Resolve real download url via FILE_SYSTEM.

        Steps:
        1) GET {FILE_SYSTEM_BASE_URL}/models/mcps -> find item where modelName==model_name and version==version.
        2) GET {FILE_SYSTEM_BASE_URL}/models/{id}/download -> returns direct downloadable url (string or json).
        """
        models = await self._fetch_mcp_models()
        target = None
        for it in models:
            try:
                if str(it.get("modelName")) == model_name and str(it.get("version")) == version:
                    target = it
                    break
            except Exception:
                continue
        if not target:
            raise RuntimeError(f"MCP model not found in FILE_SYSTEM: modelName={model_name}, version={version}")
        model_id = target.get("id")
        if model_id is None:
            raise RuntimeError("FILE_SYSTEM model item missing id")

        url = f"{settings.FILE_SYSTEM_BASE_URL}/models/{model_id}/download"
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"FILE_SYSTEM download failed: HTTP {resp.status}: {text[:200]}")

                # It might return plain text url or JSON
                ctype = (resp.headers.get("content-type") or "").lower()
                if "application/json" in ctype:
                    js = await resp.json()
                    # common shapes: {"url": "..."} or {"data": "..."}
                    if isinstance(js, dict):
                        if isinstance(js.get("url"), str):
                            return js["url"]
                        if isinstance(js.get("data"), str):
                            return js["data"]
                    if isinstance(js, str):
                        return js
                    raise RuntimeError(f"unexpected JSON from FILE_SYSTEM download: {js}")

                text = (await resp.text()).strip()
                if not text:
                    raise RuntimeError("FILE_SYSTEM download returned empty")
                return text

    async def get_tool_owner(self, tool_name: str) -> Optional[Tuple[str, str]]:
        """Return (server_name, version) that owns this tool, if known.

        tool_index is populated during successful connect/list_tools.
        """
        if not tool_name:
            return None
        async with self._registry_lock:
            return self.tool_index.get(tool_name)


mcp2_manager = MCP2Manager()

