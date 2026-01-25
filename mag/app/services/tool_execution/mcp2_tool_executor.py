"""MCP2 tool executor

New MCP implementation uses in-process fastmcp.Client instances managed by `mcp2_manager`.
This executor is used by the new ToolExecutorV2 and can be wired into agent execution.

We DO NOT modify the existing MCPToolExecutor in-place to minimize risk.
"""

import json
import logging
from typing import Any, Dict

from app.services.tool_execution.base_executor import BaseToolExecutor

logger = logging.getLogger(__name__)


class MCP2ToolExecutor(BaseToolExecutor):
    def __init__(self):
        from app.services.mcp2.mcp2_manager import mcp2_manager

        self.mcp2_manager = mcp2_manager

    def can_handle(self, tool_name: str) -> bool:
        # MCP2 tools are still "non-system" tools; routing happens by provided mapping.
        return True

    async def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        tool_call_id: str,
        **context,
    ) -> Dict[str, Any]:
        """Execute tool call via MCP2.

        Required context:
        - mcp2_server: {server_name, version}
        - user_id
        - conversation_id
        """
        server = context.get("mcp2_server")
        if not server:
            return self._format_error(tool_call_id, "missing mcp2_server in context")

        server_name = server.get("server_name")
        version = server.get("version")
        user_id = context.get("user_id") or "unknown"
        conversation_id = context.get("conversation_id") or "default"

        try:
            content = await self.mcp2_manager.call_tool(
                server_name=server_name,
                version=version,
                tool_name=tool_name,
                params=arguments,
                user_id=user_id,
                conversation_id=conversation_id,
            )

            if isinstance(content, (dict, list)):
                text = json.dumps(content, ensure_ascii=False)
            else:
                text = str(content)

            return self._format_result(tool_call_id, f"工具 {tool_name} 执行成功：{text}")
        except Exception as e:
            logger.exception("MCP2 tool execution failed")
            return self._format_error(tool_call_id, f"工具 {tool_name} 执行失败：{str(e)}")
