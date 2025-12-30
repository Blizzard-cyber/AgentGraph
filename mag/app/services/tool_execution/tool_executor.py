"""
工具执行器协调器

统一协调各类工具执行器，提供统一的工具调用接口
"""
import asyncio
import json
import logging
from typing import Dict, List, Any, Optional

from app.services.tool_execution.mcp_tool_executor import MCPToolExecutor
from app.services.tool_execution.system_tool_executor import SystemToolExecutor
from app.services.tool_execution.handoffs_tool_executor import HandoffsToolExecutor

logger = logging.getLogger(__name__)


class ToolExecutor:
    """工具执行器协调器
    
    统一的工具调用执行器，负责协调各类专门执行器：
    - MCP 工具：通过 MCPToolExecutor 处理
    - 系统工具：通过 SystemToolExecutor 处理
    - Handoffs 工具：通过 HandoffsToolExecutor 处理
    """

    def __init__(self, mcp_service=None):
        """初始化工具执行器
        
        Args:
            mcp_service: MCP服务实例（可选）
        """
        self.mcp_executor = MCPToolExecutor(mcp_service)
        self.system_executor = SystemToolExecutor()
        self.handoffs_executor = HandoffsToolExecutor()

    @property
    def mcp_service(self):
        """获取 MCP 服务实例"""
        return self.mcp_executor.mcp_service

    async def execute_tools_batch(self, tool_calls: List[Dict[str, Any]], mcp_servers: List[str],
                                 user_id: str = None, conversation_id: str = None, agent_id: str = None) -> List[Dict[str, Any]]:
        """批量执行工具调用（非流式）
        
        Args:
            tool_calls: 工具调用列表
            mcp_servers: MCP 服务器列表
            user_id: 用户ID
            conversation_id: 会话ID
            agent_id: Agent ID
            
        Returns:
            工具执行结果列表
        """
        tool_results = []
        tasks = []

        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_id = tool_call["id"]

            try:
                arguments_str = tool_call["function"]["arguments"]
                if not arguments_str:
                    arguments = {}
                else:
                    # 处理各种JSON格式
                    try:
                        arguments = json.loads(arguments_str)
                    except json.JSONDecodeError:
                        # 处理双重转义的JSON字符串，如 "{\"key\": \"value\"}"
                        try:
                            # 去除外层引号并反转义
                            if arguments_str.startswith('"') and arguments_str.endswith('"'):
                                unescaped_str = arguments_str[1:-1].replace('\\"', '"').replace('\\\\', '\\')
                                arguments = json.loads(unescaped_str)
                            else:
                                raise ValueError("无法解析参数格式")
                        except Exception:
                            # 最后尝试：将参数作为原始字符串处理
                            logger.warning(f"工具 {tool_name} 参数解析异常，使用原始字符串: {arguments_str}")
                            arguments = {"raw_argument": arguments_str}
            except Exception as e:
                logger.error(f"工具参数JSON解析失败: {arguments_str}, 错误: {e}")
                tool_results.append({
                    "tool_call_id": tool_id,
                    "content": f"工具调用解析失败：{str(e)}"
                })
                continue

            # 构建上下文
            context = {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "agent_id": agent_id,
                "mcp_servers": mcp_servers
            }

            # 根据工具类型选择执行器
            if self.handoffs_executor.can_handle(tool_name):
                logger.info(f"使用 HandoffsToolExecutor 执行: {tool_name}")
                task = asyncio.create_task(
                    self.handoffs_executor.execute(tool_name, arguments, tool_id, **context)
                )
                tasks.append(task)
            elif self.system_executor.can_handle(tool_name):
                logger.info(f"使用 SystemToolExecutor 执行: {tool_name}")
                task = asyncio.create_task(
                    self.system_executor.execute(tool_name, arguments, tool_id, **context)
                )
                tasks.append(task)
            else:
                logger.info(f"使用 MCPToolExecutor 执行: {tool_name}")
                task = asyncio.create_task(
                    self.mcp_executor.execute(tool_name, arguments, tool_id, **context)
                )
                tasks.append(task)

        # 等待所有工具执行完成
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"工具执行异常: {result}")
                    tool_results.append({
                        "tool_call_id": "unknown",
                        "content": f"工具执行异常: {str(result)}"
                    })
                else:
                    tool_results.append(result)

        return tool_results

    async def execute_tools_batch_stream(self, tool_calls: List[Dict[str, Any]], mcp_servers: List[str],
                                        user_id: str = None, conversation_id: str = None, agent_id: str = None):
        """批量执行工具调用（流式版本）

        对于流式系统工具（如 agent_task_executor, search_memory_with_agent），会 yield SSE 事件
        对于其他工具，直接执行并返回结果
        
        Args:
            tool_calls: 工具调用列表
            mcp_servers: MCP 服务器列表
            user_id: 用户ID
            conversation_id: 会话ID
            agent_id: Agent ID
        
        Yields:
            str: SSE 事件字符串（来自 Sub Agent）
            Dict: 工具执行结果
        """
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_id = tool_call["id"]

            try:
                arguments_str = tool_call["function"]["arguments"]
                if not arguments_str:
                    arguments = {}
                else:
                    # 处理各种JSON格式
                    try:
                        arguments = json.loads(arguments_str)
                    except json.JSONDecodeError:
                        # 处理双重转义的JSON字符串，如 "{\"key\": \"value\"}"
                        try:
                            # 去除外层引号并反转义
                            if arguments_str.startswith('"') and arguments_str.endswith('"'):
                                unescaped_str = arguments_str[1:-1].replace('\\"', '"').replace('\\\\', '\\')
                                arguments = json.loads(unescaped_str)
                            else:
                                raise ValueError("无法解析参数格式")
                        except Exception:
                            # 最后尝试：将参数作为原始字符串处理
                            logger.warning(f"工具 {tool_name} 参数解析异常，使用原始字符串: {arguments_str}")
                            arguments = {"raw_argument": arguments_str}
            except Exception as e:
                logger.error(f"工具参数JSON解析失败: {arguments_str}, 错误: {e}")
                yield {
                    "tool_call_id": tool_id,
                    "content": f"工具调用解析失败：{str(e)}"
                }
                continue

            # 构建上下文
            context = {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "agent_id": agent_id,
                "mcp_servers": mcp_servers
            }

            # 根据工具类型选择执行器
            if self.handoffs_executor.can_handle(tool_name):
                logger.info(f"使用 HandoffsToolExecutor 执行: {tool_name}")
                result = await self.handoffs_executor.execute(tool_name, arguments, tool_id, **context)
                yield result
            elif self.system_executor.can_handle(tool_name):
                # 检查是否为流式系统工具
                from app.services.system_tools import is_streaming_tool
                if is_streaming_tool(tool_name):
                    # 流式系统工具
                    logger.info(f"使用 SystemToolExecutor 执行（流式）: {tool_name}")
                    async for item in self.system_executor.execute_stream(tool_name, arguments, tool_id, **context):
                        yield item
                else:
                    # 普通系统工具
                    logger.info(f"使用 SystemToolExecutor 执行: {tool_name}")
                    result = await self.system_executor.execute(tool_name, arguments, tool_id, **context)
                    yield result
            else:
                logger.info(f"使用 MCPToolExecutor 执行: {tool_name}")
                result = await self.mcp_executor.execute(tool_name, arguments, tool_id, **context)
                yield result

    async def execute_single_tool(self, server_name: str, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个 MCP 工具
        
        Args:
            server_name: MCP 服务器名称
            tool_name: 工具名称
            params: 工具参数
            
        Returns:
            工具执行结果
        """
        return await self.mcp_executor.execute_single_tool(server_name, tool_name, params)