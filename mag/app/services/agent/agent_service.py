"""
Agent 服务
整合 Agent 管理功能，提供统一的业务逻辑层
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from app.infrastructure.database.mongodb import mongodb_client
from app.services.agent.agent_stream_executor import AgentStreamExecutor
from app.services.model.model_service import model_service
from app.services.system_tools import get_tool_names

logger = logging.getLogger(__name__)


class AgentService:
    """Agent 服务 - 负责 Agent 业务逻辑和数据库交互"""

    def __init__(self):
        """初始化 Agent 服务"""
        self.agent_stream_executor = AgentStreamExecutor()

    def _normalize_mcp_servers(
        self, mcp_config: List[Any]
    ) -> List[Dict[str, Optional[str]]]:
        """
        标准化MCP服务器配置为统一格式（向后兼容）

        支持三种输入格式：
        1. 旧格式（字符串）: ["server1", "server2"]
        2. 字符串带版本: ["server1:v1", "server2:1.0.0"]
        3. 新格式（对象）: [{"name": "server1", "version": "1.0.0"}]

        统一输出格式：[{"name": "server1", "version": "1.0.0"}]

        Args:
            mcp_config: MCP服务器配置列表

        Returns:
            标准化后的配置列表
        """
        normalized = []
        for item in mcp_config:
            if isinstance(item, str):
                raw = item.strip()
                if not raw:
                    continue

                # 支持 "name:version" 解析（MCP2 推荐用法）
                if ":" in raw:
                    name, version = raw.split(":", 1)
                    name = (name or "").strip()
                    version = (version or "").strip() or None
                    normalized.append({"name": name, "version": version})
                else:
                    # 旧格式：只有 name
                    normalized.append({"name": raw, "version": None})

            elif isinstance(item, dict):
                # 新格式：对象 -> 提取 name 和 version
                normalized.append(
                    {"name": item.get("name"), "version": item.get("version")}
                )
            else:
                logger.warning(f"无效的MCP服务器配置项: {item} (类型: {type(item)})")
        return normalized

    async def create_agent(
        self, agent_config: Dict[str, Any], user_id: str
    ) -> Dict[str, Any]:
        """
        创建 Agent

        Args:
            agent_config: Agent 配置字典
            user_id: 用户 ID

        Returns:
            创建结果
        """
        try:
            # 验证配置
            is_valid, error_msg = await self.validate_agent_config(
                agent_config, user_id
            )
            if not is_valid:
                return {"success": False, "error": f"Agent 配置验证失败: {error_msg}"}

            # 创建 Agent
            agent_id = await mongodb_client.agent_repository.create_agent(
                agent_config, user_id
            )

            if agent_id:
                # 创建对应的 memory 文档
                agent_name = agent_config.get("name")
                try:
                    await mongodb_client.memories_collection.insert_one(
                        {
                            "user_id": user_id,
                            "owner_type": "agent",
                            "owner_id": agent_name,
                            "memories": {},
                            "created_at": datetime.now(),
                            "updated_at": datetime.now(),
                        }
                    )
                    logger.info(f"为 Agent 创建 memory 文档成功: {agent_name}")
                except Exception as mem_error:
                    logger.warning(
                        f"为 Agent 创建 memory 文档失败: {agent_name}, 错误: {str(mem_error)}"
                    )

                logger.info(f"创建 Agent 成功: {agent_name} (user_id: {user_id})")
                return {"success": True, "agent_id": agent_id, "agent_name": agent_name}
            else:
                return {
                    "success": False,
                    "error": "创建 Agent 失败，可能 Agent 名称已存在",
                }

        except Exception as e:
            logger.error(f"创建 Agent 失败: {str(e)}")
            return {"success": False, "error": str(e)}

    async def get_agent(
        self, agent_name: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取 Agent

        Args:
            agent_name: Agent 名称
            user_id: 用户 ID

        Returns:
            Agent 文档，不存在返回 None
        """
        try:
            return await mongodb_client.agent_repository.get_agent(agent_name, user_id)
        except Exception as e:
            logger.error(f"获取 Agent 失败 ({agent_name}): {str(e)}")
            return None

    async def update_agent(
        self, agent_name: str, agent_config: Dict[str, Any], user_id: str
    ) -> Dict[str, Any]:
        """
        更新 Agent

        Args:
            agent_name: Agent 名称
            agent_config: 新的 Agent 配置
            user_id: 用户 ID

        Returns:
            更新结果
        """
        try:
            # 验证配置
            is_valid, error_msg = await self.validate_agent_config(
                agent_config, user_id
            )
            if not is_valid:
                return {"success": False, "error": f"Agent 配置验证失败: {error_msg}"}

            # 更新 Agent
            success = await mongodb_client.agent_repository.update_agent(
                agent_name=agent_name, user_id=user_id, agent_config=agent_config
            )

            if success:
                logger.info(f"更新 Agent 成功: {agent_name} (user_id: {user_id})")
                return {"success": True, "agent_name": agent_name}
            else:
                return {"success": False, "error": "更新 Agent 失败，Agent 可能不存在"}

        except Exception as e:
            logger.error(f"更新 Agent 失败 ({agent_name}): {str(e)}")
            return {"success": False, "error": str(e)}

    async def delete_agent(self, agent_name: str, user_id: str) -> bool:
        """
        删除 Agent

        Args:
            agent_name: Agent 名称
            user_id: 用户 ID

        Returns:
            删除成功返回 True，失败返回 False
        """
        try:
            success = await mongodb_client.agent_repository.delete_agent(
                agent_name, user_id
            )

            if success:
                # 删除对应的 memory 文档
                try:
                    delete_result = await mongodb_client.memories_collection.delete_one(
                        {
                            "user_id": user_id,
                            "owner_type": "agent",
                            "owner_id": agent_name,
                        }
                    )
                    if delete_result.deleted_count > 0:
                        logger.info(f"删除 Agent 的 memory 文档成功: {agent_name}")
                    else:
                        logger.warning(f"未找到 Agent 的 memory 文档: {agent_name}")
                except Exception as mem_error:
                    logger.warning(
                        f"删除 Agent 的 memory 文档失败: {agent_name}, 错误: {str(mem_error)}"
                    )

                logger.info(f"删除 Agent 成功: {agent_name} (user_id: {user_id})")
            else:
                logger.warning(f"删除 Agent 失败: {agent_name} (user_id: {user_id})")

            return success

        except Exception as e:
            logger.error(f"删除 Agent 失败 ({agent_name}): {str(e)}")
            return False

    async def list_agents(
        self,
        user_id: str,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        列出 Agents（支持分类过滤和分页）

        Args:
            user_id: 用户 ID
            category: 分类过滤（可选）
            skip: 跳过数量
            limit: 返回数量限制

        Returns:
            包含 agents 列表和总数的字典
        """
        try:
            agents = await mongodb_client.agent_repository.list_agents(
                user_id=user_id, category=category, skip=skip, limit=limit
            )

            total = await mongodb_client.agent_repository.count_agents(
                user_id=user_id, category=category
            )

            return {
                "success": True,
                "agents": agents,
                "total": total,
                "skip": skip,
                "limit": limit,
            }

        except Exception as e:
            logger.error(f"列出 Agents 失败: {str(e)}")
            return {"success": False, "error": str(e), "agents": [], "total": 0}

    async def list_categories(self, user_id: str) -> List[Dict[str, Any]]:
        """
        列出所有分类及其 Agent 数量

        Args:
            user_id: 用户 ID

        Returns:
            分类列表，格式：[{"category": "coding", "agent_count": 5}, ...]
        """
        try:
            return await mongodb_client.agent_repository.list_categories(user_id)
        except Exception as e:
            logger.error(f"列出分类失败: {str(e)}")
            return []

    async def list_agents_in_category(
        self, user_id: str, category: str
    ) -> List[Dict[str, Any]]:
        """
        列出指定分类下的所有 Agents（只返回 name 和 tags）

        Args:
            user_id: 用户 ID
            category: 分类名称

        Returns:
            Agent 列表，格式：[{"name": "...", "tags": [...]}, ...]
        """
        try:
            return await mongodb_client.agent_repository.list_agents_in_category(
                user_id=user_id, category=category
            )
        except Exception as e:
            logger.error(f"列出分类下 Agents 失败 ({category}): {str(e)}")
            return []

    async def get_agent_details(
        self, agent_name: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取 Agent 详细信息（包括完整的 card）

        Args:
            agent_name: Agent 名称
            user_id: 用户 ID

        Returns:
            Agent 详情，包含 name, card, category, tags, model, max_actions
        """
        try:
            return await mongodb_client.agent_repository.get_agent_details(
                agent_name=agent_name, user_id=user_id
            )
        except Exception as e:
            logger.error(f"获取 Agent 详情失败 ({agent_name}): {str(e)}")
            return None

    async def validate_agent_config(
        self, agent_config: Dict[str, Any], user_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        验证 Agent 配置的有效性

        Args:
            agent_config: Agent 配置字典
            user_id: 用户 ID

        Returns:
            (是否有效, 错误信息)
        """
        try:
            # 1. 验证必需字段
            required_fields = ["name", "model"]
            for field in required_fields:
                if field not in agent_config or not agent_config[field]:
                    return False, f"缺少必需字段: {field}"

            # 2. 验证 model 是否存在
            model_name = agent_config.get("model")
            model_id = agent_config.get("model_id")  # 可能包含云端模型ID

            # 如果没有model_id，尝试从云端API获取
            if not model_id:
                try:
                    import httpx
                    from app.core.config import settings

                    logger.info(
                        f"agent_config中没有model_id，尝试从云端API查询模型 {model_name}"
                    )

                    # 获取云端模型列表
                    models_api_url = f"{settings.CLOUD_GATEWAY_BASE_URL}/api/v1/models"
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        models_response = await client.get(models_api_url)
                        models_response.raise_for_status()
                        models_data = models_response.json()

                    # 在模型列表中查找匹配的模型
                    if isinstance(models_data, dict) and "models" in models_data:
                        models_list = models_data["models"]
                    elif isinstance(models_data, list):
                        models_list = models_data
                    else:
                        logger.warning(f"云端模型API返回格式异常: {type(models_data)}")
                        models_list = []

                    for model_item in models_list:
                        if model_item.get("name") == model_name:
                            model_id = model_item.get("id")
                            logger.info(
                                f"从云端API找到模型 {model_name}，ID: {model_id}"
                            )
                            break

                    if not model_id:
                        logger.warning(f"云端API中未找到模型 {model_name}")

                except Exception as e:
                    logger.warning(f"查询云端模型API失败: {str(e)}")

            model_config = await model_service.get_model(model_name, user_id)

            if not model_config:
                # 本地未注册，直接从云端下载并部署
                logger.info(f"本地未找到模型 {model_name}，尝试从云端下载部署")

                if model_service.gpustack_client:
                    if model_id:
                        # 有model_id，可以从云端获取下载URL
                        try:
                            import httpx
                            from app.core.config import settings

                            # 获取下载链接
                            download_api_url = f"{settings.CLOUD_GATEWAY_BASE_URL}/api/v1/models/{model_id}/download"
                            async with httpx.AsyncClient(timeout=10.0) as client:
                                download_response = await client.get(download_api_url)
                                download_response.raise_for_status()
                                download_url = download_response.text.strip()

                            if download_url:
                                logger.info(
                                    f"获取到模型下载链接: {download_url[:100]}..."
                                )

                                # 构建部署配置
                                model_payload = {
                                    "name": model_name,
                                    "source": "download_url",
                                    "cluster_id": 1,
                                    "backend": "vLLM",
                                    "backend_version": None,
                                    "replicas": 1,
                                    "extended_kv_cache": {"enabled": False},
                                    "speculative_config": {"enabled": False},
                                    "categories": ["imported"],
                                    "backend_parameters": [
                                        "--gpu-memory-utilization=0.4"
                                    ],
                                    "distributed_inference_across_workers": True,
                                    "restart_on_error": True,
                                    "generic_proxy": False,
                                    "download_url_model_name": model_name,
                                    "download_url": download_url,
                                    "placement_strategy": "spread",
                                    "worker_selector": None,
                                    "gpu_selector": None,
                                }

                                # 创建模型部署任务
                                created_model_id, is_existing = (
                                    await model_service.gpustack_client.create_model(
                                        model_payload
                                    )
                                )

                                if created_model_id:
                                    if is_existing:
                                        logger.info(
                                            f"模型 {model_name} 已存在于GPUStack，ID: {created_model_id}"
                                        )
                                    else:
                                        logger.info(
                                            f"模型 {model_name} 部署任务已创建，ID: {created_model_id}"
                                        )

                                        # 新部署的模型，监听初始状态（最多等待30秒）
                                        try:
                                            import asyncio

                                            logger.info(
                                                f"开始监听模型 {model_name} 的部署状态..."
                                            )

                                            event_count = 0
                                            max_events = 20
                                            timeout_seconds = 30

                                            async def watch_with_timeout():
                                                nonlocal event_count
                                                async for (
                                                    event
                                                ) in model_service.gpustack_client.watch_model_instances(
                                                    model_id=created_model_id,
                                                    timeout=timeout_seconds,
                                                ):
                                                    event_count += 1
                                                    state = event.get(
                                                        "state", "unknown"
                                                    )
                                                    download_progress = event.get(
                                                        "download_progress"
                                                    )

                                                    # 记录关键状态变化
                                                    if state in [
                                                        "initializing",
                                                        "downloading",
                                                        "analyzing",
                                                        "error",
                                                    ]:
                                                        if download_progress:
                                                            logger.info(
                                                                f"模型 {model_name} 状态: {state}, 进度: {download_progress:.1f}%"
                                                            )
                                                        else:
                                                            logger.info(
                                                                f"模型 {model_name} 状态: {state}"
                                                            )

                                                    # 检查错误状态
                                                    if state == "error":
                                                        error_msg = event.get(
                                                            "state_message", "未知错误"
                                                        )
                                                        logger.error(
                                                            f"模型 {model_name} 部署失败: {error_msg}"
                                                        )
                                                        return False

                                                    # 如果已经开始下载，认为部署任务启动成功
                                                    if state == "downloading":
                                                        logger.info(
                                                            f"模型 {model_name} 已开始下载，部署任务启动成功"
                                                        )
                                                        return True

                                                    # 防止监听太久
                                                    if event_count >= max_events:
                                                        logger.info(
                                                            f"模型 {model_name} 监听达到最大事件数，停止监听"
                                                        )
                                                        return True

                                                # 超时或没有事件
                                                return True

                                            # 等待监听完成或超时
                                            try:
                                                deployment_ok = await asyncio.wait_for(
                                                    watch_with_timeout(),
                                                    timeout=timeout_seconds + 5,
                                                )
                                                if not deployment_ok:
                                                    return (
                                                        False,
                                                        f"模型 {model_name} 部署过程中出现错误",
                                                    )
                                            except asyncio.TimeoutError:
                                                logger.warning(
                                                    f"模型 {model_name} 状态监听超时，但部署任务已创建"
                                                )
                                                # 超时不算失败，部署任务已在后台运行

                                        except Exception as e:
                                            logger.warning(
                                                f"监听模型部署状态时出错: {str(e)}，但部署任务已创建"
                                            )
                                            # 监听失败不影响主流程

                                    # 注册模型到用户数据库
                                    try:
                                        from app.core.config import settings

                                        model_config_data = {
                                            "name": model_name,
                                            "base_url": settings.GPUSTACK_BASE_URL,
                                            "api_key": settings.GPUSTACK_API_KEY,
                                            "model": model_name,
                                            "provider": "openai",
                                            "model_type": "llm",
                                        }

                                        success = await model_service.add_model(
                                            user_id, model_config_data
                                        )
                                        if success:
                                            logger.info(
                                                f"模型 {model_name} 已成功注册到用户数据库"
                                            )
                                        else:
                                            # 模型可能已在数据库中，记录日志但不视为错误
                                            logger.info(
                                                f"模型 {model_name} 注册失败，可能已存在"
                                            )

                                    except Exception as e:
                                        logger.error(
                                            f"注册模型到数据库时出错: {str(e)}"
                                        )
                                        # 不阻断主流程，模型部署已成功

                                    # 模型部署/已存在，验证通过
                                    return True, None
                                else:
                                    return False, f"模型 {model_name} 部署失败"
                            else:
                                return False, f"无法获取模型 {model_name} 的下载链接"

                        except Exception as e:
                            logger.error(f"从云端部署模型失败: {str(e)}")
                            return False, f"从云端部署模型 {model_name} 失败: {str(e)}"
                    else:
                        return (
                            False,
                            f"模型 {model_name} 未找到，且缺少model_id无法自动部署",
                        )
                else:
                    return (
                        False,
                        f"模型不存在: {model_name} (本地未注册，且GPUStack客户端未初始化)",
                    )

            # 3. 验证 mcp 服务器列表
            mcp_servers = agent_config.get("mcp", [])
            if mcp_servers:
                # 标准化MCP服务器配置（支持新旧两种格式）
                normalized_servers = self._normalize_mcp_servers(mcp_servers)

                # MCP2: 从 mcp2 的 user_servers 读取（同 /mcp2/servers 的数据源）
                from app.services.mcp2.mcp2_manager import mcp2_manager

                logger.info(f"当前用户 MCP2 servers: {user_id}")
                user_servers = await mcp2_manager.list_user_servers_with_status(user_id)
                # Set for fast lookup
                user_server_keys = {
                    (s.get("server_name"), s.get("version"))
                    for s in (user_servers or [])
                }

                # 验证每个服务器是否已 add-server（若未 add 且有 version 则自动 add，测试模式下为本地注册）
                for server_info in normalized_servers:
                    server_name = server_info.get("name")
                    server_version = server_info.get("version")

                    if not server_name:
                        logger.warning(f"MCP服务器配置缺少name字段: {server_info}")
                        continue

                    # MCP2 必须有 version（因为 serverKey = server_name:version）
                    if not server_version:
                        logger.warning(
                            f"MCP2 服务器 {server_name} 缺少 version，无法验证/自动注册"
                        )
                        return False, f"MCP服务器未配置且缺少版本信息: {server_name}"

                    if (server_name, server_version) not in user_server_keys:
                        logger.info(
                            f"MCP2 服务器 {server_name}:{server_version} 未添加，尝试 add-server..."
                        )
                        try:
                            # 组合成 server_key 格式: "name:version"
                            server_key = f"{server_name}:{server_version}"
                            task = await mcp2_manager.start_add_server_task(
                                user_id=user_id,
                                server_key=server_key,
                            )

                            # 等待任务完成（最多60秒）
                            import asyncio
                            max_wait = 60
                            wait_interval = 2
                            elapsed = 0
                            
                            while task.status not in ["complete", "error"] and elapsed < max_wait:
                                await asyncio.sleep(wait_interval)
                                elapsed += wait_interval
                                # 重新获取任务状态
                                task = await mcp2_manager.get_task_status(user_id=user_id, server_name=server_name, version=server_version)
                                if not task:
                                    break
                                logger.debug(f"等待MCP服务器添加任务完成: {server_name}:{server_version}, 状态={task.status}, 已等待{elapsed}秒")

                            if not task or task.status == "error":
                                error_msg = task.message if task else "任务不存在"
                                logger.warning(f"MCP服务器 {server_name}:{server_version} 注册失败: {error_msg}")
                                return False, f"MCP服务器 {server_name}:{server_version} 注册失败: {error_msg}"
                            
                            if task.status != "complete":
                                logger.warning(f"MCP服务器 {server_name}:{server_version} 注册超时（{max_wait}秒），当前状态: {task.status}")
                                return False, f"MCP服务器 {server_name}:{server_version} 注册超时，请稍后重试"

                            # 更新本地缓存集合，避免后续重复 add
                            user_server_keys.add((server_name, server_version))
                            logger.info(f"MCP服务器 {server_name}:{server_version} 注册成功")
                        except Exception as e:
                            logger.error(
                                f"注册 MCP2 服务器 {server_name}:{server_version} 失败: {str(e)}"
                            )
                            return (
                                False,
                                f"注册 MCP2 服务器失败: {server_name}:{server_version}",
                            )

            # 4. 验证 system_tools 列表
            system_tool_names = agent_config.get("system_tools", [])
            if system_tool_names:
                # 获取所有支持的系统工具名称
                available_tools = get_tool_names()

                # 验证每个工具是否存在
                for tool_name in system_tool_names:
                    if tool_name not in available_tools:
                        return False, f"系统工具不支持: {tool_name}"

            # 5. 验证 max_actions 范围
            max_actions = agent_config.get("max_actions", 50)
            if not isinstance(max_actions, int):
                return False, "max_actions 必须是整数"

            if max_actions < 1 or max_actions > 200:
                return False, "max_actions 必须在 1-200 之间"

            # 6. 验证 category（可选字段，但如果存在则验证）
            category = agent_config.get("category")
            if category is not None and not isinstance(category, str):
                return False, "category 必须是字符串"

            # 7. 验证 tags（可选字段，但如果存在则验证）
            tags = agent_config.get("tags", [])
            if not isinstance(tags, list):
                return False, "tags 必须是列表"

            # 8. 验证 instruction（可选字段，但如果存在则验证）
            instruction = agent_config.get("instruction")
            if instruction is not None and not isinstance(instruction, str):
                return False, "instruction 必须是字符串"

            # 验证通过
            return True, None

        except Exception as e:
            logger.error(f"验证 Agent 配置时出错: {str(e)}")
            return False, f"验证失败: {str(e)}"


# 创建全局 Agent 服务实例
agent_service = AgentService()
