"""ToolExecutorV2

This is a parallel executor that routes MCP tool execution to MCP2.
Existing ToolExecutor remains unchanged.

Integration strategy:
- Higher-level agent runtimes can opt into this executor.
- Or we can adapt a top-level factory later.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List

from app.services.tool_execution.system_tool_executor import SystemToolExecutor
from app.services.tool_execution.handoffs_tool_executor import HandoffsToolExecutor
from app.services.tool_execution.mcp2_tool_executor import MCP2ToolExecutor

logger = logging.getLogger(__name__)


class ToolExecutorV2:
    def __init__(self):
        self.mcp_executor = MCP2ToolExecutor()
        self.system_executor = SystemToolExecutor()
        self.handoffs_executor = HandoffsToolExecutor()

    async def execute_tools_batch(
        self,
        tool_calls: List[Dict[str, Any]],
        *,
        mcp2_server: Dict[str, str],
        user_id: str | None = None,
        conversation_id: str | None = None,
        agent_id: str | None = None,
    ) -> List[Dict[str, Any]]:
        tasks = []
        results: List[Dict[str, Any]] = []

        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_id = tool_call["id"]
            arguments_str = tool_call["function"].get("arguments") or "{}"

            try:
                arguments = json.loads(arguments_str) if arguments_str else {}
            except Exception:
                arguments = {"raw_argument": arguments_str}

            context = {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "agent_id": agent_id,
                "mcp2_server": mcp2_server,
            }

            if self.handoffs_executor.can_handle(tool_name):
                tasks.append(asyncio.create_task(self.handoffs_executor.execute(tool_name, arguments, tool_id, **context)))
            elif self.system_executor.can_handle(tool_name):
                tasks.append(asyncio.create_task(self.system_executor.execute(tool_name, arguments, tool_id, **context)))
            else:
                tasks.append(asyncio.create_task(self.mcp_executor.execute(tool_name, arguments, tool_id, **context)))

        if tasks:
            gathered = await asyncio.gather(*tasks, return_exceptions=True)
            for r in gathered:
                if isinstance(r, Exception):
                    results.append({"tool_call_id": "unknown", "content": f"工具执行异常: {str(r)}"})
                else:
                    results.append(r)

        return results
