from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MCP2ServerDownloadRequest(BaseModel):
    """Register a server by downloading its python script."""

    server_name: str = Field(..., description="Human-readable server name")
    download_url: str = Field(..., description="URL to download server script from")


class MCP2ServerInfo(BaseModel):
    server_name: str
    version: str
    script_path: str
    created_at: datetime
    updated_at: datetime
    owner_user_id: Optional[str] = None


class MCP2AddServerResponse(BaseModel):
    status: str
    server: MCP2ServerInfo
    message: Optional[str] = None


class MCP2ConnectRequest(BaseModel):
    conversation_id: Optional[str] = None


class MCP2ConnectResponse(BaseModel):
    status: str
    server_name: str
    version: str
    tools: List[Dict[str, Any]]


class MCP2DeleteRequest(BaseModel):
    conversation_id: Optional[str] = None


class MCP2ToolCallRequest(BaseModel):
    server_name: str
    version: str
    tool_name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    conversation_id: Optional[str] = None


class MCP2ToolCallResponse(BaseModel):
    status: str
    server_name: str
    version: str
    tool_name: str
    content: Any = None
    error: Optional[str] = None
    execution_time: Optional[float] = None


class MCP2TaskKey(BaseModel):
    user_id: str
    server_name: str
    version: str


class MCP2TaskStatus(BaseModel):
    key: MCP2TaskKey
    task_type: str  # add_server | connect
    status: str  # started | downloading | extracting | registering | connecting | complete | error
    message: str | None = None
    updated_at: datetime
    result: Dict[str, Any] | None = None


class MCP2AddServerRequest(BaseModel):
    """Unified add_server request.

    Client sends user_id + server_key where server_key is "serverName:version".
    Backend resolves download URL via FILE_SYSTEM service (models/mcps + models/{id}/download),
    downloads the zip, extracts, and registers.
     """

    user_id: str
    server_name: str  # server_key: "modelName:version"


class MCP2StartTaskResponse(BaseModel):
    status: str  # accepted
    task: MCP2TaskStatus


class MCP2DisconnectRequest(BaseModel):
    user_id: str
    server_name: str
    version: str
    conversation_id: Optional[str] = None

