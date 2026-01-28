import time
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user_hybrid
from app.models.auth_schema import CurrentUser
from app.models.mcp2_schema import (
    MCP2ServerDownloadRequest,
    MCP2AddServerResponse,
    MCP2ConnectResponse,
    MCP2ToolCallRequest,
    MCP2ToolCallResponse,
    MCP2AddServerRequest,
    MCP2TaskStatus,
    MCP2TaskKey,
    MCP2StartTaskResponse,
    MCP2DisconnectRequest,
)
from app.services.mcp2.mcp2_manager import mcp2_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp2", tags=["mcp2"])


@router.get("/servers", response_model=List[Dict[str, Any]])
async def list_servers(current_user: CurrentUser = Depends(get_current_user_hybrid)):
    """List servers owned/added by current user.

    This is backed by a local json file (mcp_servers/.state/user_servers.json) so it survives refresh/restart.
    """
    return await mcp2_manager.list_user_servers_with_status(current_user.user_id)


@router.post("/add-server", response_model=MCP2StartTaskResponse)
async def add_server(req: MCP2AddServerRequest,
                     current_user: CurrentUser = Depends(get_current_user_hybrid),
                     ):
    """Unified add_server (async).

    Frontend provides user_id + server_name where server_name is serverKey "modelName:version".
    Backend resolves download URL via FILE_SYSTEM and creates/updates a task keyed by (user_id, modelName, version).

    Status values: started/downloading/complete/error.

    """
    req.user_id = current_user.user_id
    task = await mcp2_manager.start_add_server_task(user_id=req.user_id, server_key=req.server_name)

    # normalize task key for response
    server_name = req.server_name
    version = ""
    if isinstance(req.server_name, str) and ":" in req.server_name:
        server_name, version = req.server_name.split(":", 1)
    return {
        "status": "accepted",
        "task": {
            "key": {"user_id": req.user_id, "server_name": server_name, "version": version},
            "task_type": task.task_type,
            "status": task.status,
            "message": task.message,
            "updated_at": task.updated_at,
            "result": task.result,
        },
    }


@router.post("/connect", response_model=MCP2StartTaskResponse, )
async def connect(req: MCP2TaskKey, conversation_id: str | None = None,
                  current_user: CurrentUser = Depends(get_current_user_hybrid)):
    """Async connect task. When complete, task.result contains tools."""
    req.user_id = current_user.user_id
    task = await mcp2_manager.start_connect_task(
        user_id=req.user_id,
        server_name=req.server_name,
        version=req.version,
        conversation_id=conversation_id or "default",
    )
    return {
        "status": "accepted",
        "task": {
            "key": {"user_id": req.user_id, "server_name": req.server_name, "version": req.version},
            "task_type": task.task_type,
            "status": task.status,
            "message": task.message,
            "updated_at": task.updated_at,
            "result": task.result,
        },
    }


@router.get("/tasks/status", response_model=MCP2TaskStatus)
async def get_task_status(user_id: str, server_name: str, version: str):
    task = await mcp2_manager.get_task_status(user_id=user_id, server_name=server_name, version=version)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return {
        "key": {"user_id": user_id, "server_name": server_name, "version": version},
        "task_type": task.task_type,
        "status": task.status,
        "message": task.message,
        "updated_at": task.updated_at,
        "result": task.result,
    }


@router.post("/tool-call", response_model=MCP2ToolCallResponse)
async def tool_call(
        req: MCP2ToolCallRequest,
        current_user: CurrentUser = Depends(get_current_user_hybrid),
):
    start = time.time()
    try:
        content = await mcp2_manager.call_tool(
            server_name=req.server_name,
            version=req.version,
            tool_name=req.tool_name,
            params=req.params,
            user_id=current_user.user_id,
            conversation_id=req.conversation_id or "default",
        )
        return {
            "status": "success",
            "server_name": req.server_name,
            "version": req.version,
            "tool_name": req.tool_name,
            "content": content,
            "execution_time": time.time() - start,
        }
    except Exception as e:
        return {
            "status": "error",
            "server_name": req.server_name,
            "version": req.version,
            "tool_name": req.tool_name,
            "error": str(e),
            "execution_time": time.time() - start,
        }


@router.post("/disconnect")
async def disconnect(req: MCP2DisconnectRequest,
                     current_user: CurrentUser = Depends(get_current_user_hybrid)
                     ):
    """Disconnect: close client usage for this user.

    This only affects runtime connections (client_table). It does NOT delete the server from the user's list.
    """
    try:
        req.user_id = current_user.user_id
        await mcp2_manager.disconnect(
            server_name=req.server_name,
            version=req.version,
            user_id=req.user_id,
            conversation_id=req.conversation_id,
            remove_from_user_servers=False,
        )
        return {"status": "disconnected"}
    except Exception as e:
        logger.error(f"mcp2 disconnect failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug/connections")
async def debug_connections(current_user: CurrentUser = Depends(get_current_user_hybrid)):
    """Debug only: dump current MCP2 connection table."""
    data = await mcp2_manager.debug_dump_connections()
    logger.info(f"mcp2 debug connections for user {current_user.user_id}: {data}")
    return data


@router.post("/servers/update")
async def update_server(payload: Dict[str, Any],
                        current_user: CurrentUser = Depends(get_current_user_hybrid)
                        ):
    """Update a server entry for a user.

    Payload:
    - user_id
    - old_server_name, old_version
    - new_server_name, new_version

    Note: This updates the user's server list (disk-backed). It does not download anything.
    """
    try:
        user_id = current_user.user_id
        old_server_name = str(payload.get("old_server_name"))
        old_version = str(payload.get("old_version"))
        new_server_name = str(payload.get("new_server_name"))
        new_version = str(payload.get("new_version"))
        if not all([user_id, old_server_name, old_version, new_server_name, new_version]):
            raise HTTPException(status_code=400, detail="missing required fields")

        await mcp2_manager.remove_user_server(user_id=user_id, server_name=old_server_name, version=old_version)
        await mcp2_manager.add_user_server(user_id=user_id, server_name=new_server_name, version=new_version,
                                           download_url=None)

        return {"status": "updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"mcp2 update server failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/servers/remove")
async def remove_server(payload: Dict[str, Any],
                        current_user: CurrentUser = Depends(get_current_user_hybrid)
                        ):
    """Remove: delete all records for this user about server_name:version.

    - Removes from user's server list (user_servers.json)
    - Clears user's task record for this server
    - Drops user's connections/usages. If no connections left, closes and removes the client from client_table.
    - Keeps server_registry entry.
    """
    try:
        user_id = current_user.user_id
        server_name = str(payload.get("server_name"))
        version = str(payload.get("version"))
        if not all([user_id, server_name, version]):
            raise HTTPException(status_code=400, detail="missing required fields")

        await mcp2_manager.remove_user_server_fully(user_id=user_id, server_name=server_name, version=version)

        # also clear task entry for cleanliness
        async with mcp2_manager._task_lock:  # type: ignore[attr-defined]
            mcp2_manager.task_table.pop((user_id, server_name, version), None)

        return {"status": "removed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"mcp2 remove server failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
