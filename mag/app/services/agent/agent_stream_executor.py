"""
Agent 流式执行器
实现 Agent 调用的流式执行逻辑（支持多轮对话）
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator
import requests
from app.services.model.model_service import model_service
from memory_client import MEMORY_CLIENT 
from app.services.tool_execution import ToolExecutor
from app.infrastructure.database.mongodb import mongodb_client
from app.services.system_tools import get_system_tools_by_names
from app.services.trajectory import trajectory_service

logger = logging.getLogger(__name__)


class AgentStreamExecutor:
    """Agent 流式执行器 - 处理 Agent 调用的流式执行"""

    def __init__(self):
        """初始化 Agent 流式执行器"""
        self.tool_executor = ToolExecutor()

    async def run_agent_stream(
        self,
        agent_name: Optional[str],
        user_prompt: str,
        user_id: str,
        conversation_id: str,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        mcp_servers: Optional[List[str]] = None,
        system_tools: Optional[List[str]] = None,
        max_iterations: Optional[int] = None,
        original_query: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Agent 流式运行（主入口，支持多轮对话）

        Args:
            agent_name: Agent 名称（None 表示手动配置模式）
            user_prompt: 用户输入
            user_id: 用户 ID
            conversation_id: 对话 ID
            model_name: 模型名称（可选覆盖）
            system_prompt: 系统提示词（可选覆盖）
            mcp_servers: MCP服务器列表（可选添加）
            system_tools: 系统工具列表（可选添加）
            max_iterations: 最大迭代次数（可选覆盖）
            original_query: 原始用户查询（用于记忆查询，如果不提供则使用user_prompt）

        Yields:
            SSE 格式字符串 "data: {...}\\n\\n"
        """
        try:
            from app.infrastructure.database.mongodb.client import mongodb_client
            from app.services.system_tools.registry import set_user_language_context

            # 获取用户语言并设置到上下文
            user_language = await mongodb_client.user_repository.get_user_language(
                user_id
            )
            set_user_language_context(user_language)
            logger.info(
                f"设置用户语言上下文: user_id={user_id}, language={user_language}"
            )

            # 加载有效配置
            effective_config = await self._load_effective_config(
                agent_name=agent_name,
                user_id=user_id,
                model_name=model_name,
                system_prompt=system_prompt,
                mcp_servers=mcp_servers,
                system_tools=system_tools,
                max_iterations=max_iterations,
            )

            if not effective_config:
                error_msg = {"error": "无法加载有效配置"}
                yield f"data: {json.dumps(error_msg)}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 构建包含历史消息的完整消息列表
            # 如果提供了original_query，用它进行记忆查询；否则使用user_prompt
            memory_query = original_query if original_query else user_prompt
            messages = await self._build_messages(
                conversation_id=conversation_id,
                user_prompt=user_prompt,
                agent_id=agent_name,
                user_id=user_id,
                system_prompt=effective_config["system_prompt"],
                memory_query=memory_query,
            )

            # 准备工具
            tools = await self._prepare_agent_tools(
                mcp_servers=effective_config["mcp_servers"],
                system_tools=effective_config["system_tools"],
                user_id=user_id,
                conversation_id=conversation_id,
            )

            # 执行完整流程
            final_result = None
            async for item in self.run_agent_loop(
                    agent_name=effective_config["agent_name"],
                    model_name=effective_config["model_name"],
                    messages=messages,
                    tools=tools,
                    mcp_servers=effective_config["mcp_servers"],
                    max_iterations=effective_config["max_iterations"],
                    user_id=user_id,
                    conversation_id=conversation_id,
            ):
                if isinstance(item, str):
                    # SSE 字符串，直接转发给客户端
                    yield item
                else:
                    # Dict 结果，保存但不转发到客户端
                    final_result = item

            # 保存执行结果到数据库（is_graph_node 默认为 False）
            if final_result:
                elapsed_time_ms = final_result.get("elapsed_time_ms", 0)
                try:
                    await self._save_agent_run_result(
                        conversation_id=conversation_id,
                        agent_name=effective_config["agent_name"],
                        result=final_result,
                        user_id=user_id,
                        user_prompt=user_prompt,
                        model_name=effective_config["model_name"],
                        elapsed_time_ms=elapsed_time_ms,
                        tools=tools,
                        is_graph_node=False,
                    )
                except Exception as save_error:
                    logger.error(f"保存 Agent 执行结果失败: {str(save_error)}")
                    # 抛出错误，让上层知道保存失败
                    raise
                memory_info = await self.extract_memory_info(
                    final_result.get("round_messages", [])
                )
                try:
                    memory_result = await MEMORY_CLIENT.add_memory(
                        user_id=user_id,
                        agent_id=effective_config["agent_name"],
                        session_id=conversation_id,
                        memory_info=memory_info,
                    )
                    memory_count_save_bool = await self._save_memory_count(user_id, memory_info,
                                                                           effective_config["agent_name"])
                    if memory_result.get("success") and memory_count_save_bool:
                        logger.info(
                            f"记忆保存成功: user_id={user_id}, agent_id={effective_config['agent_name']}, session_id={conversation_id}"
                        )
                    else:
                        logger.warning(
                            f"记忆保存失败: {memory_result.get('error', '未知错误')},memory_count_save_bool={memory_count_save_bool}"
                        )
                except Exception as e:
                    logger.error(f"记忆保存异常: {str(e)}")
                    # 记忆保存失败不应该影响主流程，继续执行

            # 发送完成信号
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"run_agent_stream 失败: {str(e)}")
            # 发送错误信息给前端
            error_chunk = {"error": {"message": str(e), "type": "execution_error"}}
            yield f"data: {json.dumps(error_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            raise
            error_msg = {"error": str(e)}
            yield f"data: {json.dumps(error_msg)}\n\n"
            yield "data: [DONE]\n\n"

    async def _build_messages(
        self,
        agent_id: str,
        conversation_id: str,
        user_prompt: str,
        system_prompt: str,
        user_id: str,
        memory_query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        构建包含历史消息的完整消息列表

        Args:
            conversation_id: 对话 ID
            user_prompt: 当前用户输入
            system_prompt: 系统提示词

        Returns:
            完整的消息列表
        """
        from app.infrastructure.database.mongodb.client import mongodb_client

        messages = []

        try:
            # 1. 添加系统提示词
            if system_prompt and system_prompt.strip():
                messages.append({"role": "system", "content": system_prompt.strip()})

            # 2. 获取并添加历史消息
            agent_run_doc = await mongodb_client.agent_run_repository.get_agent_run(
                conversation_id
            )

            if agent_run_doc and agent_run_doc.get("rounds"):
                logger.debug(f"加载历史消息: {len(agent_run_doc['rounds'])} 轮")

                for round_data in agent_run_doc["rounds"]:
                    round_messages = round_data.get("messages", [])
                    for msg in round_messages:
                        # 跳过历史中的 system 消消息（已在开头添加）
                        if msg.get("role") != "system":
                            messages.append(msg)
            else:
                logger.debug(f"新对话，无历史消息: {conversation_id}")

            # 3.记忆查询 - 记忆服务器挂掉，暂时注释
            # 使用memory_query（如果提供）进行查询，否则使用user_prompt
            query_for_memory = memory_query if memory_query else user_prompt
            SearchMemoryRequest = await MEMORY_CLIENT.search_memory(
                user_id=user_id,
                agent_id=agent_id,
                session_id=conversation_id,
                query=query_for_memory,
            )
            logger.info(f"记忆查询 (query={query_for_memory[:100]}...) 结果: {SearchMemoryRequest}")
            
            # 3. 添加当前用户消息
            if user_prompt and user_prompt.strip():
                messages.append(
                    {
                        "role": "user",
                        "content": user_prompt.strip(),
                        "memory": SearchMemoryRequest["data"],
                    }
                )

            logger.info(f"✓ 构建消息完成，共 {len(messages)} 条（包含历史）")
            return messages

        except Exception as e:
            logger.error(f"构建消息失败: {str(e)}")
            # 出错时至少返回当前消息
            fallback_messages = []
            if system_prompt and system_prompt.strip():
                fallback_messages.append(
                    {"role": "system", "content": system_prompt.strip()}
                )
            if user_prompt and user_prompt.strip():
                fallback_messages.append(
                    {"role": "user", "content": user_prompt.strip()}
                )
            return fallback_messages

    async def extract_memory_info(
            self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        从对话消息列表中提取可写入 memory 的条目。

        输入（messages）:
            List[Dict[str, Any]]
            - 对话消息列表（如 round_messages / messages）
            - 每个元素通常包含：
                {
                    "role": str,        # "system" | "user" | "assistant"
                    "content": Any,     # 通常为 str
                    ...                 # 可能包含 memory / token / metadata 等字段
                }

        输出（return）:
            List[Dict[str, Any]]
            - 可直接作为 add_memory 接口的 memory_info 字段
            - 每个元素结构为：
                {
                    "content": str,     # 非空文本内容
                    "role": str,        # "user" 或 "assistant"
                    "metadata": dict    # 预留扩展字段（默认空）
                }

        过滤规则:
            - 仅保留 role 为 "user" 或 "assistant" 的消息
            - content 必须是非空字符串
            - 自动丢弃 system 消息、空消息、非文本内容
            - 不会引入任何递归或执行态字段（memory / token 等）

        使用场景:
            - 在 agent 执行结束后，将对话中的关键信息写入长期记忆
            - 避免将 round_messages / final_result 原样写入 memory
        """
        memory_info = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            # 只允许 user / assistant
            if role not in ("user", "assistant"):
                continue

            # content 必须是非空字符串
            if not isinstance(content, str) or not content.strip():
                continue

            memory_info.append({"content": content, "role": role, "metadata": {}})

        return memory_info

    async def _load_effective_config(
            self,
            agent_name: Optional[str],
            user_id: str,
            model_name: Optional[str] = None,
            system_prompt: Optional[str] = None,
            mcp_servers: Optional[List[str]] = None,
            system_tools: Optional[List[str]] = None,
            max_iterations: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        加载有效配置（智能合并策略）

        策略：
        - 无 Agent：直接使用用户参数
        - 仅 Agent：使用 Agent 完整配置
        - Agent + 参数：
          - 覆盖：model_name, system_prompt, max_iterations
          - 添加（去重）：mcp_servers, system_tools

        Returns:
            {
                "agent_name": str,
                "model_name": str,
                "system_prompt": str,
                "mcp_servers": List[str],
                "system_tools": List[str],
                "max_iterations": int
            }
        """
        from app.infrastructure.database.mongodb.client import mongodb_client

        config = {
            "agent_name": "manual",
            "model_name": None,
            "system_prompt": "",
            "mcp_servers": [],
            "system_tools": [],
            "max_iterations": 50,
        }

        # === 场景1：无 Agent，纯手动配置 ===
        if not agent_name:
            config["model_name"] = model_name
            config["system_prompt"] = system_prompt or ""
            config["mcp_servers"] = mcp_servers or []
            config["system_tools"] = system_tools or []
            config["max_iterations"] = max_iterations or 50

            if not config["model_name"]:
                logger.error("手动配置模式缺少 model_name")
                return None

            logger.info(f"✓ 使用手动配置: model={config['model_name']}")
            return config

        # === 场景2/3：使用 Agent（可能带覆盖参数）===
        agent = await mongodb_client.agent_repository.get_agent(agent_name, user_id)
        if not agent:
            logger.error(f"Agent 不存在: {agent_name}")
            return None

        agent_config = agent.get("agent_config", {})

        # 加载 Agent 基础配置
        config["agent_name"] = agent_name
        config["model_name"] = agent_config.get("model")
        config["system_prompt"] = agent_config.get("instruction", "")
        
        # 处理MCP服务器配置：支持字典和字符串两种格式
        mcp_raw = agent_config.get("mcp", [])
        mcp_normalized = []
        for item in mcp_raw:
            if isinstance(item, dict):
                # 字典格式：{'name': 'xxx', 'version': 'yyy'} -> 'xxx:yyy'
                name = item.get("name", "")
                version = item.get("version", "")
                if name and version:
                    mcp_normalized.append(f"{name}:{version}")
                elif name:
                    mcp_normalized.append(name)
            elif isinstance(item, str):
                # 字符串格式：直接使用
                mcp_normalized.append(item)
        config["mcp_servers"] = mcp_normalized
        
        config["system_tools"] = agent_config.get("system_tools", []).copy()
        config["max_iterations"] = agent_config.get("max_actions", 50)

        # 应用覆盖参数
        if model_name:
            config["model_name"] = model_name
            logger.info(f"覆盖模型: {model_name}")

        if system_prompt:
            config["system_prompt"] = system_prompt
            logger.info(f"覆盖系统提示词")

        if max_iterations:
            config["max_iterations"] = max_iterations
            logger.info(f"覆盖最大迭代次数: {max_iterations}")

        # 添加工具（去重）
        if mcp_servers:
            original_count = len(config["mcp_servers"])
            # 支持字符串和字典两种格式的去重
            existing_servers = config["mcp_servers"]
            combined = existing_servers + mcp_servers
            
            # 生成唯一标识符用于去重
            seen = set()
            deduped = []
            for item in combined:
                if isinstance(item, str):
                    key = item
                elif isinstance(item, dict):
                    # 使用 name:version 或 name 作为唯一标识
                    key = f"{item.get('name', '')}:{item.get('version', '')}"
                else:
                    continue
                    
                if key not in seen:
                    seen.add(key)
                    deduped.append(item)
            
            config["mcp_servers"] = deduped
            added = len(config["mcp_servers"]) - original_count
            if added > 0:
                logger.info(f"添加 MCP 服务器: {added} 个")

        if system_tools:
            original_count = len(config["system_tools"])
            # system_tools 通常是字符串列表，可以直接用 set 去重
            config["system_tools"] = list(set(config["system_tools"] + system_tools))
            added = len(config["system_tools"]) - original_count
            if added > 0:
                logger.info(f"添加系统工具: {added} 个")

        logger.info(f"✓ 加载配置完成: agent={agent_name}, model={config['model_name']}")
        return config

    async def run_agent_loop(
            self,
            agent_name: str,
            model_name: str,
            messages: List[Dict[str, Any]],
            tools: List[Dict[str, Any]],
            mcp_servers: List[str],
            max_iterations: int,
            user_id: str,
            conversation_id: str,
            task_id: Optional[str] = None,
            is_graph_node: bool = False,
    ) -> AsyncGenerator[str | Dict[str, Any], None]:
        """
        运行 Agent 循环（含工具调用循环）

        Args:
            agent_name: Agent 名称
            model_name: 模型名称
            messages: 初始消息列表（已包含历史）
            tools: 工具列表
            mcp_servers: MCP 服务器列表
            max_iterations: 最大迭代次数
            user_id: 用户 ID
            conversation_id: 对话 ID
            task_id: 任务 ID（Sub Agent 时提供）
            is_graph_node: 是否为 Graph 节点调用（默认 False）

        Yields:
            - 中间 yield: SSE 格式字符串 "data: {...}\\n\\n"
            - 最后 yield: 完整结果字典
        """
        current_messages = messages.copy()
        iteration = 0
        round_messages = []
        round_token_usage = {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }
        round_elapsed_time_ms = 0  # 单轮模型调用总耗时

        # 标识是否为 Sub Agent
        is_sub_agent = task_id is not None

        # 记录 Graph 节点调用
        if is_graph_node:
            logger.debug(
                f"Graph 节点调用 Agent: {agent_name}, conversation_id={conversation_id}"
            )

        # 创建轨迹收集器（仅在非子Agent、非Graph节点时收集）
        trajectory_collector = None
        # 记录本次执行使用的所有工具
        tools_used = []
        
        if not is_sub_agent and not is_graph_node:
            # 获取用户查询（从messages中提取最后一条用户消息）
            user_query = ""
            for msg in reversed(current_messages):
                if msg.get("role") == "user":
                    user_query = msg.get("content", "")
                    break
            
            if user_query:
                trajectory_collector = trajectory_service.create_trajectory_collector(
                    agent_id=agent_name or "unknown_agent",
                    user_id=user_id,
                    query=user_query,
                )
                logger.info(f"已创建轨迹收集器: agent={agent_name}, user={user_id}")

        try:
            while iteration < max_iterations:
                iteration += 1
                logger.info(
                    f"Agent {agent_name} - 第 {iteration} 轮执行 (task_id={task_id})"
                )

                # 过滤 reasoning_content
                filtered_messages = model_service.filter_reasoning_content(
                    current_messages
                )

                # 调用模型进行流式生成
                accumulated_result = None
                async for item in model_service.stream_chat_with_tools(
                        model_name=model_name,
                        messages=filtered_messages,
                        tools=tools,
                        yield_chunks=True,
                        user_id=user_id,
                ):
                    if isinstance(item, str):
                        # SSE chunk
                        # 如果是 Sub Agent，添加 task_id 标识
                        if is_sub_agent:
                            # 解析 SSE 数据
                            if item.startswith("data: ") and not item.startswith(
                                    "data: [DONE]"
                            ):
                                try:
                                    data_str = item[6:].strip()
                                    data = json.loads(data_str)
                                    # 添加 task_id 标识
                                    data["task_id"] = task_id
                                    yield f"data: {json.dumps(data)}\n\n"
                                except:
                                    yield item
                            else:
                                yield item
                        else:
                            yield item
                    else:
                        # 累积结果
                        accumulated_result = item

                if not accumulated_result:
                    logger.error(
                        f"Agent {agent_name} - 第 {iteration} 轮未收到累积结果"
                    )
                    break

                # 提取累积的结果
                accumulated_content = accumulated_result["accumulated_content"]
                accumulated_reasoning = accumulated_result.get(
                    "accumulated_reasoning", ""
                )
                current_tool_calls = accumulated_result.get("tool_calls", [])
                api_usage = accumulated_result.get("api_usage")
                # 模型调用耗时
                elapsed_ms = accumulated_result.get("elapsed_time_ms")
                if elapsed_ms is not None:
                    round_elapsed_time_ms += elapsed_ms

                # 更新 token 使用量
                if api_usage:
                    round_token_usage["total_tokens"] += api_usage["total_tokens"]
                    round_token_usage["prompt_tokens"] += api_usage["prompt_tokens"]
                    round_token_usage["completion_tokens"] += api_usage[
                        "completion_tokens"
                    ]

                # 构建 assistant 消息
                assistant_message = {"role": "assistant"}

                if accumulated_reasoning:
                    assistant_message["reasoning_content"] = accumulated_reasoning

                assistant_message["content"] = accumulated_content or ""

                if current_tool_calls:
                    assistant_message["tool_calls"] = current_tool_calls

                # 添加到消息列表
                current_messages.append(assistant_message)
                if iteration == 1:
                    # 第一轮时，记录 system 和 user 消息
                    for msg in filtered_messages:
                        if msg.get("role") == "system":
                            round_messages.append(msg)
                            break  # 只添加第一条system消息
                    # 只添加当前用户消息（最后一个）
                    round_messages.append(filtered_messages[-1])
                round_messages.append(assistant_message)

                # 如果没有工具调用，结束循环
                if not current_tool_calls:
                    logger.info(
                        f"Agent {agent_name} - 第 {iteration} 轮无工具调用，执行完成"
                    )
                    
                    # 收集轨迹数据：记录没有工具调用的步骤
                    if trajectory_collector:
                        # 提取reasoning作为thought，如果没有则使用最终回答
                        thought = accumulated_reasoning if accumulated_reasoning else accumulated_content.strip()
                        if not thought:
                            thought = "生成最终回答"
                        
                        # 添加步骤，tool为空列表
                        trajectory_collector.add_step(
                            agent_name=agent_name,
                            thought=thought,
                            tool=[],
                            output=accumulated_content.strip(),
                            depend_on=[],
                        )
                    
                    break

                # 执行工具调用
                logger.info(
                    f"Agent {agent_name} - 执行 {len(current_tool_calls)} 个工具调用"
                )

                # 检查是否有流式系统工具调用
                from app.services.system_tools import is_streaming_tool

                has_streaming_tool = any(
                    is_streaming_tool(tc.get("function", {}).get("name"))
                    for tc in current_tool_calls
                )

                # 有流式工具调用，使用流式执行
                if has_streaming_tool:
                    tool_results = []
                    async for item in self.tool_executor.execute_tools_batch_stream(
                            tool_calls=current_tool_calls,
                            mcp_servers=mcp_servers,
                            user_id=user_id,
                            conversation_id=conversation_id,
                            agent_id=agent_name,
                    ):
                        if isinstance(item, str):
                            # SSE 事件，直接转发
                            if is_sub_agent:
                                # 如果当前也是 Sub Agent，添加 task_id
                                if item.startswith("data: ") and not item.startswith(
                                        "data: [DONE]"
                                ):
                                    try:
                                        data_str = item[6:].strip()
                                        data = json.loads(data_str)
                                        data["task_id"] = task_id
                                        yield f"data: {json.dumps(data)}\n\n"
                                    except:
                                        yield item
                                else:
                                    yield item
                            else:
                                yield item
                        else:
                            # 工具结果
                            tool_results.append(item)
                else:
                    # 普通工具调用，使用非流式执行
                    tool_results = await self.tool_executor.execute_tools_batch(
                        tool_calls=current_tool_calls,
                        mcp_servers=mcp_servers,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        agent_id=agent_name,
                    )

                # 添加工具结果到消息列表并实时发送
                for tool_result in tool_results:
                    tool_message = {
                        "role": "tool",
                        "tool_call_id": tool_result["tool_call_id"],
                        "content": tool_result["content"],
                    }
                    current_messages.append(tool_message)
                    round_messages.append(tool_message)

                    # 发送工具结果 SSE
                    if is_sub_agent:
                        tool_message["task_id"] = task_id
                    yield f"data: {json.dumps(tool_message)}\n\n"

                # 收集轨迹数据：记录工具调用步骤
                if trajectory_collector or not is_sub_agent:
                    # 遍历本次迭代的所有工具调用，为每个工具调用创建一个步骤
                    for tool_call, tool_result in zip(current_tool_calls, tool_results):
                        tool_name = tool_call.get("function", {}).get("name", "unknown_tool")
                        tool_args = tool_call.get("function", {}).get("arguments", "{}")
                        
                        # 记录使用的工具
                        if tool_name not in tools_used:
                            tools_used.append(tool_name)
                        
                        if trajectory_collector:
                            # 提取reasoning作为thought
                            thought = accumulated_reasoning if accumulated_reasoning else f"调用工具 {tool_name} 处理任务"
                            
                            # 解析工具输出
                            try:
                                output_content = tool_result.get("content", "")
                                # 尝试解析为JSON
                                try:
                                    output = json.loads(output_content)
                                except:
                                    output = output_content
                            except:
                                output = str(tool_result)
                            
                            # 添加步骤（depend_on暂时为空，可以根据实际依赖关系设置）
                            trajectory_collector.add_step(
                                agent_name=agent_name,
                                thought=thought,
                                tool=[tool_name],
                                output=output,
                                depend_on=[],
                            )

            if iteration >= max_iterations:
                logger.warning(
                    f"Agent {agent_name} - 达到最大迭代次数 {max_iterations}"
                )

            # 上传轨迹数据（异步执行，不阻塞响应）
            if trajectory_collector:
                asyncio.create_task(self._upload_trajectory_async(trajectory_collector))

            # 返回完整结果
            result = {
                "round_messages": round_messages,
                "round_token_usage": round_token_usage,
                "elapsed_time_ms": round_elapsed_time_ms,
                "iteration_count": iteration,
                "agent_name": agent_name,
                "tools_used": tools_used,  # 添加使用的工具列表
            }

            if is_sub_agent:
                result["task_id"] = task_id

            yield result

        except Exception as e:
            logger.error(f"run_agent_loop 失败 ({agent_name}): {str(e)}")
            raise

    async def _prepare_agent_tools(
            self,
            mcp_servers: List[str],
            system_tools: List[str],
            user_id: str,
            conversation_id: str,
    ) -> List[Dict[str, Any]]:
        """
        准备 Agent 工具

        Args:
            mcp_servers: MCP服务器列表
            system_tools: 系统工具列表
            user_id: 用户 ID
            conversation_id: 对话 ID

        Returns:
            工具 schema 列表
        """
        tools = []

        # 加载 MCP 工具（MCP2：fastmcp）
        if mcp_servers:
            try:
                from app.services.mcp2.mcp2_manager import mcp2_manager

                for server_key in mcp_servers:
                    if not isinstance(server_key, str) or ":" not in server_key:
                        logger.warning(f"MCP2 server key 格式错误（应为 server:version）: {server_key}")
                        continue

                    server_name, version = server_key.split(":", 1)

                    # Ensure connected so tool_index/tools exist. This is safe if already connected.
                    try:
                        await mcp2_manager.start_connect_task(
                            user_id=user_id,
                            server_name=server_name,
                            version=version,
                            conversation_id=conversation_id,
                        )
                    except Exception as e:
                        logger.warning(f"启动 MCP2 connect 任务失败: {server_key}, err={e}")

                    # Poll a short time to get tools (do not block too long).
                    tools_payload = None
                    try:
                        for _ in range(20):
                            t = await mcp2_manager.get_task_status(user_id=user_id, server_name=server_name, version=version)
                            if t and t.task_type == "connect":
                                if t.status == "complete" and t.result and t.result.get("tools"):
                                    tools_payload = t.result.get("tools")
                                    break
                                if t.status == "error":
                                    logger.warning(f"MCP2 connect 失败: {server_key}, msg={t.message}")
                                    break
                            await asyncio.sleep(0.2)
                    except Exception as e:
                        logger.warning(f"轮询 MCP2 connect 状态失败: {server_key}, err={e}")

                    if not tools_payload:
                        # If we couldn't fetch tools, skip adding schema for this server.
                        continue

                    # Convert MCP2 tools to OpenAI tool schema
                    for tdef in tools_payload:
                        try:
                            name = tdef.get("name")
                            desc = tdef.get("description") or ""
                            input_schema = tdef.get("input_schema") or {"type": "object", "properties": {}}

                            if not name:
                                continue

                            tools.append(
                                {
                                    "type": "function",
                                    "function": {
                                        "name": name,
                                        "description": desc,
                                        "parameters": input_schema,
                                    },
                                }
                            )
                        except Exception:
                            continue
            except Exception as e:
                logger.error(f"加载 MCP 工具失败: {str(e)}")

        # 加载系统工具
        if system_tools:
            sys_tools = get_system_tools_by_names(system_tools)
            tools.extend(sys_tools)

        return tools

    async def _save_agent_run_result(
            self,
            conversation_id: str,
            agent_name: str,
            result: Dict[str, Any],
            user_id: str,
            user_prompt: str,
            model_name: str,
            elapsed_time_ms: int,
            tools: Optional[List[Dict[str, Any]]] = None,
            is_graph_node: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        保存 Agent 运行结果到数据库

        Args:
            conversation_id: 对话 ID
            agent_name: Agent 名称
            result: 执行结果字典
            user_id: 用户 ID
            user_prompt: 用户输入
            model_name: 模型名称
            tools: 工具 schema 列表（可选）
            is_graph_node: 是否为 Graph 节点调用（默认 False）

        Returns:
            如果生成了新标题，返回 {"title": str, "tags": List[str]}，否则返回 None
        """
        # 如果是 Graph 节点调用，跳过所有数据库写入操作
        if is_graph_node:
            logger.debug(
                f"Graph 节点调用，跳过数据库写入: conversation_id={conversation_id}"
            )
            return None

        try:
            from app.infrastructure.database.mongodb.client import mongodb_client

            # 确保 conversations 元数据存在
            conversation = (
                await mongodb_client.conversation_repository.get_conversation(
                    conversation_id
                )
            )
            if not conversation:
                await mongodb_client.conversation_repository.create_conversation(
                    conversation_id=conversation_id,
                    conversation_type="agent",
                    user_id=user_id,
                    title=f"{agent_name} 对话" if agent_name != "manual" else "新对话",
                    tags=[],
                )

            # 确保 agent_run 文档存在
            agent_run = await mongodb_client.agent_run_repository.get_agent_run(
                conversation_id
            )
            if not agent_run:
                await mongodb_client.agent_run_repository.create_agent_run(
                    conversation_id
                )

            # 获取当前主线程的 round 数量
            current_round_count = (
                await mongodb_client.agent_run_repository.get_round_count(
                    conversation_id
                )
            )
            next_round_number = current_round_count + 1

            # 提取 token 使用量
            token_usage = result.get("round_token_usage", {})
            prompt_tokens = token_usage.get("prompt_tokens", 0)
            completion_tokens = token_usage.get("completion_tokens", 0)

            # 保存轮次数据到 agent_run 集合的主线程 rounds
            success = await mongodb_client.agent_run_repository.add_round_to_main(
                conversation_id=conversation_id,
                round_number=next_round_number,
                agent_name=agent_name,
                messages=result.get("round_messages", []),
                tools=tools,
                model=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                elapsed_time_ms=elapsed_time_ms,
            )

            logger.info(
                f"✓ 保存主线程 round 成功: conversation_id={conversation_id}, round={next_round_number}"
            )

            if not success:
                error_msg = f"保存主线程 round 失败: {conversation_id}"
                logger.error(error_msg)
                raise Exception(error_msg)

            # 更新 conversation 的 round_count
            await mongodb_client.conversation_repository.update_conversation_round_count(
                conversation_id=conversation_id, increment=1
            )

            # 更新 conversation 的 token 使用量
            if token_usage:
                await mongodb_client.conversation_repository.update_conversation_token_usage(
                    conversation_id=conversation_id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )

            logger.debug(
                f"Agent {agent_name} 执行结果已保存到数据库: {conversation_id}, round {next_round_number}"
            )

            return None

        except Exception as e:
            logger.error(f"保存 Agent 执行结果失败: {str(e)}")
            return None

    async def _save_memory_count(
            self,
            user_id: str,
            memory_info: List[Dict[str, Any]],
            agent_id: str
    ) -> bool:
        """
                构建记忆的count数据，具体content内容保存在我们自己的memory中，
                所以这里的content全部记为空字符串，此处只是用于前端展示计数记录

                Args:
                    user_id: 用户id
                    memory_info: 记忆信息
                    agent_id: 模型 id
                Returns:
                    成功返回TRUE，失败抛出异常
        """
        # 如果没有待保存的记忆，直接返回 True（无须写入）
        memory_count = len(memory_info)
        if memory_count == 0:
            return True

        # 固定为 episodic，我们自己的记忆保存默认为这个类型
        category = "episodic"
        additions = []

        # 为每条 memory_info 创建一条计数记录，owner 根据 role 区分 user / assistant
        for mem in memory_info:
            role = mem.get("role", "user")
            # user 保持为 "user"，assistant 对应的计数 owner 使用 "self"
            if role == "assistant":
                owner = "self"
            else:
                owner = "user"
            additions.append({
                "owner": owner,
                "category": category,
                "items": [""]
            })

        result = await mongodb_client.add_memory(user_id, additions, agent_id)
        if result.get("success"):
            return True
        else:
            return False

    async def _upload_trajectory_async(self, trajectory_collector) -> None:
        """
        异步上传轨迹数据（不阻塞主流程）
        
        Args:
            trajectory_collector: 轨迹收集器实例
        """
        try:
            success = await trajectory_collector.upload()
            if success:
                logger.info(f"轨迹数据上传成功: agent={trajectory_collector}, steps={len(trajectory_collector.steps)}")
            else:
                logger.warning(f"轨迹数据上传失败: agent={trajectory_collector}")
        except Exception as e:
            logger.error(f"轨迹数据上传异常: {str(e)}", exc_info=True)
