from app.services.mcp2.mcp2_manager import mcp2_manager
"""
MCP 工具执行器

处理 MCP（Model Context Protocol）工具的执行
"""
import json
import logging
from typing import Dict, Any, Optional, List
from app.services.tool_execution.base_executor import BaseToolExecutor

logger = logging.getLogger(__name__)

from app.services.mcp2.mcp2_manager import mcp2_manager



class MCPToolExecutor(BaseToolExecutor):
    """MCP 工具执行器

    专门处理通过 MCP 服务调用的外部工具。

    注意：当前已切换到 MCP2（fastmcp stdio client）。
    """

    def __init__(self, mcp_service=None):
        # 兼容旧构造参数，但不再依赖 MCP1 mcp_service
        self._mcp_service = mcp_service

    @property
    def mcp_service(self):
        """Deprecated: MCP1 service is no longer used in MCP2 mode."""
        return None

    def can_handle(self, tool_name: str) -> bool:
        """判断是否为 MCP 工具
        
        MCP 工具通过排除法判断：不是系统工具也不是 Handoffs 工具
        
        Args:
            tool_name: 工具名称
            
        Returns:
            True 如果可能是 MCP 工具
        """
        # MCP 工具需要通过查找服务器来确认，这里返回 True 表示可能处理
        return True

    async def execute(self, tool_name: str, arguments: Dict[str, Any],
                     tool_call_id: str, **context) -> Dict[str, Any]:
        """执行 MCP 工具调用
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            tool_call_id: 工具调用ID
            **context: 上下文参数（mcp_servers 必需）
            
        Returns:
            工具执行结果
        """
        mcp_servers = context.get("mcp_servers", [])

        try:
            # 查找工具所属服务器
            server_name = await self._find_tool_server(tool_name, mcp_servers)
            if not server_name:
                return self._format_error(tool_call_id, f"找不到工具 '{tool_name}' 所属的服务器")

            # 执行工具
            result = await self._execute_single_tool(server_name, tool_name, arguments, **context)

            # 格式化结果
            if result.get("error"):
                content = f"工具 {tool_name} 执行失败：{result['error']}"
            else:
                result_content = result.get("content", "")
                if isinstance(result_content, (dict, list)):
                    content = f"工具 {tool_name} 执行成功：{json.dumps(result_content, ensure_ascii=False)}"
                else:
                    content = f"工具 {tool_name} 执行成功：{str(result_content)}"

            return self._format_result(tool_call_id, content)

        except Exception as e:
            logger.error(f"MCP 工具 {tool_name} 执行失败: {str(e)}")
            return self._format_error(
                tool_call_id,
                f"工具 {tool_name} 执行失败：{str(e)}"
            )

    async def execute_single_tool(self, server_name: str, tool_name: str,
                                  params: Dict[str, Any], **context) -> Dict[str, Any]:
        """执行单个 MCP 工具（不带 tool_call_id）
        
        Args:
            server_name: MCP 服务器名称
            tool_name: 工具名称
            params: 工具参数
            
        Returns:
            工具执行结果
        """
        return await self._execute_single_tool(server_name, tool_name, params, **context)

    async def _execute_single_tool(self, server_name: str, tool_name: str,
                                   params: Dict[str, Any], **context) -> Dict[str, Any]:
        """执行单个 MCP 工具的内部实现（MCP2）。

        server_name 使用约定格式："{server}:{version}"。

        user_id / conversation_id 优先从 context 读取；为兼容旧调用方，也支持从 params 中读取
        __user_id / __conversation_id。
        """
        try:
            if ":" not in server_name:
                return {"error": f"invalid mcp2 server key (expected server:version): {server_name}"}

            srv, ver = server_name.split(":", 1)

            user_id = context.get("user_id") or params.pop("__user_id", None) or "unknown"
            conversation_id = context.get("conversation_id") or params.pop("__conversation_id", None) or "default"

            content = await mcp2_manager.call_tool(
                server_name=srv,
                version=ver,
                tool_name=tool_name,
                params=params,
                user_id=str(user_id),
                conversation_id=str(conversation_id),
            )

            return {"tool_name": tool_name, "server_name": server_name, "content": content}
        except Exception as e:
            error_msg = f"调用工具时出错: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "tool_name": tool_name,
                "server_name": server_name,
                "error": error_msg
            }

    async def _find_tool_server(self, tool_name: str, mcp_servers: List[str]) -> Optional[str]:
        """查找工具所属的 MCP 服务器（MCP2）。

        返回的 server_name 约定为 "server:version"。
        """
        try:
            if not tool_name:
                return None

            # 优先走 MCP2 tool index（connect 时建立）
            owner = await mcp2_manager.get_tool_owner(tool_name)
            if owner:
                srv, ver = owner
                return f"{srv}:{ver}"

            # 如果上层明确传了 mcp_servers，且含 server:version，则直接兜底返回第一个
            for s in mcp_servers or []:
                if isinstance(s, str) and ":" in s:
                    return s

            logger.warning(f"MCP2 tool owner not found for tool '{tool_name}'. Connect the server first.")
            return None
        except Exception as e:
            logger.error(f"查找工具 '{tool_name}' 服务器时出错: {str(e)}", exc_info=True)
            return None
