import json
import logging
import asyncio
import tempfile
import os
from datetime import datetime
from bson import ObjectId
from fastapi import (
    APIRouter,
    HTTPException,
    status,
    Depends,
    UploadFile,
    File,
    BackgroundTasks,
)
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging
import asyncio
import os
import tempfile
import uuid
from app.infrastructure.database.mongodb.client import mongodb_client
from app.services.agent.agent_stream_executor import AgentStreamExecutor
from app.services.agent.agent_import_service import agent_import_service
from app.services.agent.agent_service import agent_service
from app.services.agent.dag_executor import DAGExecutor, DAGPlan
from app.services.agent.dag_service import (
    RealAgentInterface,
    DAGDefinition,
    DAGExecutionRequest,
    DAGExecutionResponse,
    DAGStatusResponse,
    active_executions,
    agent_interface,
    _execute_dag_background,
)
from app.services.agent.plan_service import plan_service
from app.utils.sse_helper import TrajectoryCollector
from app.models.agent_schema import (
    CreateAgentRequest,
    UpdateAgentRequest,
    AgentListItem,
    AgentListResponse,
    AgentCategoryItem,
    AgentCategoryResponse,
    AgentInCategoryItem,
    AgentInCategoryResponse,
    AgentRunRequest,
)
from app.auth.dependencies import get_current_user_hybrid
from app.models.auth_schema import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

# Agent 流式执行器实例
agent_stream_executor = AgentStreamExecutor()


# ======= Agent 列表和查询 API接口 =======
@router.get("/list", response_model=AgentListResponse)
async def list_agents(
    category: str = None,
    limit: int = 100,
    skip: int = 0,
    current_user: CurrentUser = Depends(get_current_user_hybrid),
):
    """列出 Agents（支持分页和分类过滤）"""
    try:
        user_id = current_user.user_id

        # 获取 Agent 列表
        agents = await mongodb_client.agent_repository.list_agents(
            user_id=user_id, category=category, limit=limit, skip=skip
        )

        # 转换为响应格式
        agent_items = []
        for agent in agents:
            agent_config = agent.get("agent_config", {})

            # 处理时间格式
            created_at = agent.get("created_at", "")
            updated_at = agent.get("updated_at", "")

            if isinstance(created_at, datetime):
                created_at = created_at.isoformat()
            elif created_at:
                created_at = str(created_at)

            if isinstance(updated_at, datetime):
                updated_at = updated_at.isoformat()
            elif updated_at:
                updated_at = str(updated_at)

            agent_items.append(
                AgentListItem(
                    name=agent_config.get("name", ""),
                    category=agent_config.get("category", ""),
                    tags=agent_config.get("tags", []),
                    model=agent_config.get("model", ""),
                    created_at=created_at,
                    updated_at=updated_at,
                )
            )

        return AgentListResponse(agents=agent_items, total_count=len(agent_items))

    except Exception as e:
        logger.error(f"列出 Agents 出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"列出 Agents 出错: {str(e)}",
        )


@router.get("/categories", response_model=AgentCategoryResponse)
async def list_categories(current_user: CurrentUser = Depends(get_current_user_hybrid)):
    """列出所有 Agent 分类"""
    try:
        user_id = current_user.user_id

        # 获取分类列表
        categories = await mongodb_client.agent_repository.list_categories(user_id)

        # 转换为响应格式
        category_items = []
        for cat in categories:
            category_items.append(
                AgentCategoryItem(
                    category=cat.get("category", ""),
                    agent_count=cat.get("agent_count", 0),
                )
            )

        return AgentCategoryResponse(
            success=True,
            categories=category_items,
            total_categories=len(category_items),
        )

    except Exception as e:
        logger.error(f"列出分类出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"列出分类出错: {str(e)}",
        )


@router.get("/category/{category}", response_model=AgentInCategoryResponse)
async def list_agents_in_category(
    category: str, current_user: CurrentUser = Depends(get_current_user_hybrid)
):
    """列出指定分类下的所有 Agents"""
    try:
        user_id = current_user.user_id

        # 获取分类下的 Agents
        agents = await mongodb_client.agent_repository.list_agents_in_category(
            user_id=user_id, category=category
        )

        # 转换为响应格式
        agent_items = []
        for agent in agents:
            agent_config = agent.get("agent_config", {})
            agent_items.append(
                AgentInCategoryItem(
                    name=agent_config.get("name", ""), tags=agent_config.get("tags", [])
                )
            )

        return AgentInCategoryResponse(
            success=True,
            category=category,
            agents=agent_items,
            total_count=len(agent_items),
        )

    except Exception as e:
        logger.error(f"列出分类下 Agents 出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"列出分类下 Agents 出错: {str(e)}",
        )


# ======= Agent CRUD API接口 =======
@router.post("")
async def create_agent(
    request: CreateAgentRequest,
    current_user: CurrentUser = Depends(get_current_user_hybrid),
):
    """创建 Agent"""
    try:
        # 从token获取user_id，覆盖请求体中的user_id
        user_id = current_user.user_id

        # 验证 Agent 名称唯一性
        existing_agent = await mongodb_client.agent_repository.get_agent(
            request.agent_config.name, user_id
        )

        if existing_agent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Agent 已存在: {request.agent_config.name}",
            )

        # 使用 agent_service 创建 Agent（包含记忆文档创建）
        result = await agent_service.create_agent(
            agent_config=request.agent_config.dict(), user_id=user_id
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "创建 Agent 失败"),
            )

        return {
            "status": "success",
            "message": f"Agent '{request.agent_config.name}' 创建成功",
            "agent_name": result.get("agent_name"),
            "agent_id": result.get("agent_id"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建 Agent 出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建 Agent 出错: {str(e)}",
        )


@router.get("/{agent_name}")
async def get_agent(
    agent_name: str, current_user: CurrentUser = Depends(get_current_user_hybrid)
):
    """获取 Agent 配置"""
    try:
        user_id = current_user.user_id

        agent = await mongodb_client.agent_repository.get_agent(agent_name, user_id)

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"找不到 Agent: {agent_name}",
            )

        # 验证所有权（管理员可以访问所有 Agent）
        if not current_user.is_admin() and agent.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问此 Agent"
            )

        return {"status": "success", "agent": agent}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 Agent 出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取 Agent 出错: {str(e)}",
        )


@router.put("/{agent_name}")
async def update_agent(
    agent_name: str,
    request: UpdateAgentRequest,
    current_user: CurrentUser = Depends(get_current_user_hybrid),
):
    """更新 Agent 配置"""
    try:
        user_id = current_user.user_id

        # 验证 Agent 是否存在
        existing_agent = await mongodb_client.agent_repository.get_agent(
            agent_name, user_id
        )

        if not existing_agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"找不到 Agent: {agent_name}",
            )

        # 验证所有权（管理员可以操作所有 Agent）
        if not current_user.is_admin() and existing_agent.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此 Agent"
            )

        # 验证名称一致性
        if request.agent_config.name != agent_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Agent 名称不能修改"
            )

        # 使用 agent_service 更新 Agent
        result = await agent_service.update_agent(
            agent_name=agent_name,
            agent_config=request.agent_config.dict(),
            user_id=user_id,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "更新 Agent 失败"),
            )

        return {
            "status": "success",
            "message": f"Agent '{agent_name}' 更新成功",
            "agent_name": agent_name,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新 Agent 出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新 Agent 出错: {str(e)}",
        )


@router.delete("/{agent_name}")
async def delete_agent(
    agent_name: str, current_user: CurrentUser = Depends(get_current_user_hybrid)
):
    """删除 Agent"""
    try:
        user_id = current_user.user_id

        # 验证 Agent 是否存在
        existing_agent = await mongodb_client.agent_repository.get_agent(
            agent_name, user_id
        )

        if not existing_agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"找不到 Agent: {agent_name}",
            )

        # 验证所有权（管理员可以操作所有 Agent）
        if not current_user.is_admin() and existing_agent.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此 Agent"
            )

        # 使用 agent_service 删除 Agent（会同时删除记忆文档）
        success = await agent_service.delete_agent(agent_name, user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除 Agent 失败",
            )

        return {
            "status": "success",
            "message": f"Agent '{agent_name}' 删除成功",
            "agent_name": agent_name,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除 Agent 出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除 Agent 出错: {str(e)}",
        )


# ======= Agent 运行 API接口 =======
@router.post("/run")
async def agent_run(
    request: AgentRunRequest,
    current_user: CurrentUser = Depends(get_current_user_hybrid),
):
    """Agent 运行（流式响应，SSE）- 支持配置覆盖"""
    try:
        # 从token获取user_id，覆盖请求体中的user_id
        user_id = current_user.user_id

        # 基本参数验证
        if not request.user_prompt.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="用户消息不能为空"
            )

        # 验证配置：必须提供 agent_name 或 model_name
        if not request.agent_name and not request.model_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="必须提供 agent_name 或 model_name",
            )

        # 如果提供了 agent_name，验证 Agent 是否存在
        if request.agent_name:
            agent = await mongodb_client.agent_repository.get_agent(
                request.agent_name, user_id
            )

            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"找不到 Agent: {request.agent_name}",
                )

        # 生成或使用现有 conversation_id
        conversation_id = request.conversation_id or str(ObjectId())

        # 查询数据库判断是否为新对话
        existing_conversation = (
            await mongodb_client.conversation_repository.get_conversation(
                conversation_id
            )
        )
        is_new_conversation = existing_conversation is None

        if is_new_conversation:
            # 创建 conversation 记录（类型为 agent）
            await mongodb_client.conversation_repository.create_conversation(
                conversation_id=conversation_id,
                conversation_type="agent",
                user_id=user_id,
                title=f"{request.agent_name or 'Manual'} 对话",
            )

            # 创建 agent_run 记录
            await mongodb_client.agent_run_repository.create_agent_run(
                conversation_id=conversation_id
            )

        # 创建队列用于标题更新通知
        title_queue = asyncio.Queue()

        # 后台标题生成任务
        async def generate_title_background():
            from app.services.conversation.title_service import generate_title_and_tags

            try:
                title, tags = await generate_title_and_tags(
                    user_id=user_id, user_prompt=request.user_prompt
                )

                # 更新数据库中的标题和标签
                await mongodb_client.conversation_repository.update_conversation_title_and_tags(
                    conversation_id=conversation_id, title=title, tags=tags
                )

                logger.info(f"✓ 后台生成标题成功: {title}")

                # 通知前端标题更新
                await title_queue.put(
                    {
                        "type": "title_update",
                        "title": title,
                        "tags": tags,
                        "conversation_id": conversation_id,
                    }
                )

            except Exception as e:
                logger.error(f"后台生成标题出错: {str(e)}")

        # 如果是新会话，启动后台标题生成任务
        if is_new_conversation:
            asyncio.create_task(generate_title_background())

        # 生成流式响应的生成器
        async def generate_stream():
            stream_done = False
            try:
                # 创建agent执行流的异步任务
                async def agent_stream_wrapper():
                    nonlocal stream_done
                    async for chunk in agent_stream_executor.run_agent_stream(
                        agent_name=request.agent_name,
                        user_prompt=request.user_prompt,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        # 传递可选配置参数
                        model_name=request.model_name,
                        system_prompt=request.system_prompt,
                        mcp_servers=request.mcp_servers,
                        system_tools=request.system_tools,
                        max_iterations=request.max_iterations,
                    ):
                        yield chunk
                    stream_done = True

                # 同时监听agent流和标题队列
                agent_stream = agent_stream_wrapper()
                async for chunk in agent_stream:
                    yield chunk

                    # 检查队列中是否有标题更新（非阻塞）
                    try:
                        while not title_queue.empty():
                            title_event = await asyncio.wait_for(
                                title_queue.get(), timeout=0.01
                            )
                            yield f"data: {json.dumps(title_event)}\n\n"
                    except asyncio.TimeoutError:
                        pass

                # agent流结束后，等待并发送可能延迟的标题更新
                if is_new_conversation:
                    try:
                        title_event = await asyncio.wait_for(
                            title_queue.get(), timeout=3.0
                        )
                        yield f"data: {json.dumps(title_event)}\n\n"
                    except asyncio.TimeoutError:
                        pass

            except Exception as e:
                logger.error(f"Agent 流式响应生成出错: {str(e)}")
                error_chunk = {
                    "error": {"message": f"执行失败: {str(e)}", "type": "api_error"}
                }
                yield f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                # 重新抛出异常，让上层知道失败
                raise

        # 根据stream参数决定响应类型
        if request.stream:
            # 流式响应
            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            # 非流式响应：收集所有数据后返回完整结果
            collector = TrajectoryCollector(
                user_prompt=request.user_prompt,
                system_prompt=request.system_prompt or "",
            )
            complete_response = await collector.collect_stream_data(generate_stream())

            # 添加 conversation_id
            complete_response["conversation_id"] = conversation_id

            return complete_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent 运行处理出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理 Agent 运行时出错: {str(e)}",
        )


# ======= Agent 导入 API接口 =======
class RepositoryImportRequest(BaseModel):
    """从云端仓库导入请求"""

    agent_id: int = Field(..., description="云端Agent ID")
    agent_name: Optional[str] = Field(None, description="Agent名称（用于日志记录）")


@router.post("/import/repository")
async def import_from_repository(
    request: RepositoryImportRequest,
    current_user: CurrentUser = Depends(get_current_user_hybrid),
):
    """
    从云端导入Agent配置

    通过Agent ID从云端API获取下载链接，下载ZIP包后解压导入Agent配置。

    Returns:
        FileResponse: Markdown格式的导入报告文件
    """
    try:
        user_id = current_user.user_id
        import httpx
        import zipfile
        from io import BytesIO

        agent_id = request.agent_id
        agent_name = request.agent_name or f"Agent_{agent_id}"

        logger.info(f"从云端导入Agent: ID={agent_id}, 名称={agent_name}")

        # 1. 获取下载链接
        download_api_url = f"http://192.168.1.86:8080/api/v1/models/{agent_id}/download"

        async with httpx.AsyncClient(timeout=10.0) as client:
            download_response = await client.get(download_api_url)
            download_response.raise_for_status()
            download_url = download_response.text.strip()

        if not download_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无法获取Agent ID {agent_id} 的下载链接",
            )

        logger.info(f"获取到下载链接: {download_url[:100]}...")

        # 2. 下载ZIP文件
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(download_url)
            response.raise_for_status()
            zip_content = response.content

        if not zip_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="从云端下载的文件内容为空",
            )

        # 2. 解压ZIP文件
        temp_extract_dir = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(BytesIO(zip_content)) as zip_file:
                zip_file.extractall(temp_extract_dir)

            logger.info(f"ZIP文件解压到: {temp_extract_dir}")

            # 3. 查找配置文件（优先级：agent.json > agents.json > *.json > *.jsonl）
            config_file = None
            config_extension = None

            supported_formats = [".json", ".jsonl", ".xlsx", ".xls", ".parquet"]
            priority_files = ["agent.json", "agents.json", "config.json"]

            # 先查找优先文件
            for priority_file in priority_files:
                potential_path = os.path.join(temp_extract_dir, priority_file)
                if os.path.exists(potential_path):
                    config_file = potential_path
                    config_extension = ".json"
                    break

            # 如果没找到，搜索所有支持格式的文件
            if not config_file:
                for root, dirs, files in os.walk(temp_extract_dir):
                    for file in files:
                        file_ext = os.path.splitext(file)[1].lower()
                        if file_ext in supported_formats:
                            config_file = os.path.join(root, file)
                            config_extension = file_ext
                            break
                    if config_file:
                        break

            if not config_file:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"ZIP包中未找到支持的配置文件，支持的格式: {', '.join(supported_formats)}",
                )

            logger.info(f"找到配置文件: {config_file}")

            # 4. 读取配置文件内容
            with open(config_file, "rb") as f:
                file_content = f.read()

            # 4.5. 处理JSON格式 - 如果有agent_config包装则展开
            if config_extension == ".json":
                import json

                try:
                    data = json.loads(file_content)
                    # 如果是单个对象且包含agent_config，展开它
                    if isinstance(data, dict) and "agent_config" in data:
                        data = data["agent_config"]
                        file_content = json.dumps(data, ensure_ascii=False).encode(
                            "utf-8"
                        )
                        logger.info(f"检测到agent_config包装，已自动展开")
                    # 如果是数组，检查每个元素是否有agent_config包装
                    elif isinstance(data, list):
                        unwrapped = []
                        for item in data:
                            if isinstance(item, dict) and "agent_config" in item:
                                unwrapped.append(item["agent_config"])
                            else:
                                unwrapped.append(item)
                        if unwrapped != data:
                            file_content = json.dumps(
                                unwrapped, ensure_ascii=False
                            ).encode("utf-8")
                            logger.info(f"检测到agent_config包装，已自动展开数组")
                except json.JSONDecodeError:
                    logger.warning("JSON解析失败，使用原始内容")
                except Exception as e:
                    logger.warning(f"处理JSON包装时出错: {str(e)}，使用原始内容")

            # 5. 执行导入
            import_result = await agent_import_service.import_agents(
                file_content=file_content,
                file_extension=config_extension,
                user_id=user_id,
            )

            # 6. 返回导入结果
            return {
                "success": True,
                "message": f"成功从云端导入Agent (ID: {agent_id})",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "import_result": import_result,
            }

        finally:
            # 清理解压目录
            import shutil

            try:
                shutil.rmtree(temp_extract_dir)
            except Exception as e:
                logger.warning(f"清理临时目录失败: {str(e)}")

    except httpx.HTTPError as e:
        logger.error(f"从云端下载失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"从云端下载失败: {str(e)}"
        )
    except zipfile.BadZipFile as e:
        logger.error(f"ZIP文件格式错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"ZIP文件格式错误: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从云端导入Agent出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"从云端导入Agent出错: {str(e)}",
        )


@router.post("/import")
async def import_agents(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user_hybrid),
):
    """
    从本地文件导入Agent配置，返回导入报告

    支持的文件格式：
    - JSON (.json): 单个Agent对象或Agent数组
    - JSONL (.jsonl): 每行一个Agent对象
    - Excel (.xlsx, .xls): Excel工作簿
    - Parquet (.parquet): Parquet文件

    Returns:
        FileResponse: Markdown格式的导入报告文件
    """
    try:
        user_id = current_user.user_id

        # 1. 验证文件格式
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="文件名不能为空"
            )

        file_extension = os.path.splitext(file.filename)[1].lower()
        supported_formats = [".json", ".jsonl", ".xlsx", ".xls", ".parquet"]

        if file_extension not in supported_formats:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件格式: {file_extension}，支持的格式: {', '.join(supported_formats)}",
            )

        # 2. 读取文件内容
        file_content = await file.read()

        if not file_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="文件内容为空"
            )

        # 3. 执行导入
        import_result = await agent_import_service.import_agents(
            file_content=file_content, file_extension=file_extension, user_id=user_id
        )

        # 4. 生成报告文件（固定使用Markdown格式）
        report_content = import_result.get("report_markdown", "")

        # 5. 创建临时文件
        temp_dir = tempfile.mkdtemp()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"agent_import_report_{timestamp}.md"
        report_path = os.path.join(temp_dir, report_filename)

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        # 6. 返回文件响应
        return FileResponse(
            path=report_path,
            filename=report_filename,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename={report_filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从本地文件导入Agent出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"从本地文件导入Agent出错: {str(e)}",
        )


@router.get("/import/repositories")
async def list_import_repositories(
    current_user: CurrentUser = Depends(get_current_user_hybrid),
):
    """
    列出可用的云端Agent列表

    从云端API获取可用的Agent模型列表。
    """
    try:
        import httpx

        # 云端API地址
        cloud_api_url = "http://192.168.1.86:8080/api/v1/models/agents"

        # 请求云端API
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(cloud_api_url)
            response.raise_for_status()
            agents_data = response.json()

        # 转换为前端需要的格式
        agents = []
        for agent in agents_data:
            agents.append(
                {
                    "id": agent.get("id"),
                    "name": agent.get("modelName"),
                    "version": agent.get("version"),
                    "description": agent.get("description", ""),
                    "url": agent.get("url"),
                    "size": agent.get("size"),
                    "filename": agent.get("filename"),
                    "creator": agent.get("creator"),
                    "created_at": agent.get("createdAt"),
                    "status": agent.get("status"),
                }
            )

        return {
            "success": True,
            "agents": agents,
            "total": len(agents),
            "cloud_api": cloud_api_url,
        }

    except httpx.HTTPError as e:
        logger.error(f"获取云端Agent列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"获取云端Agent列表失败: {str(e)}",
        )
    except Exception as e:
        logger.error(f"处理云端Agent列表出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理云端Agent列表出错: {str(e)}",
        )


# ======= DAG执行 API接口 =======
@router.post("/dag/execute", response_model=DAGExecutionResponse)
async def execute_dag(
    request: DAGExecutionRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user_hybrid),
):
    """
    执行DAG计划

    DAG可以定义多个Agent步骤的并行或串行执行流程，支持依赖关系管理。
    """
    try:
        import uuid

        execution_id = str(uuid.uuid4())[:12]
        user_id = current_user.user_id

        # 转换为执行器需要的格式
        dag_definition = request.dag_definition.model_dump()

        # 验证DAG定义
        if not dag_definition.get("步骤"):
            raise HTTPException(status_code=400, detail="DAG必须包含至少一个步骤")

        # 使用当前用户的user_id，如果请求中没有提供
        effective_user_id = request.user_id or user_id
        effective_conversation_id = request.conversation_id or f"dag_{execution_id}"

        # 在后台执行DAG
        background_tasks.add_task(
            _execute_dag_background,
            execution_id,
            dag_definition,
            request.max_concurrent,
            effective_user_id,
            effective_conversation_id,
        )

        return DAGExecutionResponse(
            execution_id=execution_id,
            status="started",
            message=f"DAG执行已启动: {request.execution_name or execution_id}",
            started_at=datetime.now().isoformat(),
        )

    except Exception as e:
        logger.error(f"启动DAG执行失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"启动DAG执行失败: {str(e)}")


@router.get("/dag/status/{execution_id}", response_model=DAGStatusResponse)
async def get_dag_status(
    execution_id: str, current_user: CurrentUser = Depends(get_current_user_hybrid)
):
    """
    获取DAG执行状态

    返回DAG执行的详细状态，包括各步骤的执行情况和进度。
    """
    if execution_id not in active_executions:
        raise HTTPException(status_code=404, detail="执行ID不存在")

    dag_plan = active_executions[execution_id]

    # 创建临时执行器以使用其方法
    temp_executor = DAGExecutor(agent_interface)
    status_info = temp_executor.get_execution_status(dag_plan)

    return DAGStatusResponse(**status_info)


@router.get("/dag/executions")
async def list_dag_executions(
    current_user: CurrentUser = Depends(get_current_user_hybrid),
):
    """
    列出所有DAG执行

    返回当前用户的所有DAG执行历史。
    """
    executions = []
    for execution_id, dag_plan in active_executions.items():
        executions.append(
            {
                "execution_id": execution_id,
                "goal": dag_plan.goal,
                "status": dag_plan.status,
                "start_time": (
                    dag_plan.start_time.isoformat() if dag_plan.start_time else None
                ),
                "end_time": (
                    dag_plan.end_time.isoformat() if dag_plan.end_time else None
                ),
                "total_steps": len(dag_plan.steps),
                "completed_steps": sum(
                    1 for s in dag_plan.steps if s.status.value == "completed"
                ),
            }
        )

    return {"total": len(executions), "executions": executions}


@router.delete("/dag/execution/{execution_id}")
async def cancel_dag_execution(
    execution_id: str, current_user: CurrentUser = Depends(get_current_user_hybrid)
):
    """
    取消DAG执行

    尝试取消正在执行的DAG任务。
    """
    if execution_id not in active_executions:
        raise HTTPException(status_code=404, detail="执行ID不存在")

    dag_plan = active_executions[execution_id]

    if dag_plan.status in ["completed", "failed"]:
        raise HTTPException(status_code=400, detail="执行已完成，无法取消")

    # 标记为取消状态
    dag_plan.status = "cancelled"
    dag_plan.end_time = datetime.now()

    return {"message": f"执行 {execution_id} 已取消"}


@router.get("/dag/template")
async def get_dag_template(
    current_user: CurrentUser = Depends(get_current_user_hybrid),
):
    """
    获取DAG定义模板

    返回一个标准的DAG定义模板，可以作为创建DAG的参考。
    """
    return {
        "目标": "描述要达成的目标",
        "前提假设": ["假设1：数据源可用", "假设2：相关服务正常运行"],
        "约束条件": ["时间限制：30分钟内完成", "资源限制：内存使用不超过4GB"],
        "步骤": [
            {
                "id": 1,
                "agent": "agent_name",
                "action": "执行具体动作的描述",
                "input_schema": {
                    "type": "object",
                    "required": ["param1"],
                    "properties": {
                        "param1": {"type": "string", "description": "参数说明"}
                    },
                },
                "output_schema": {
                    "type": "object",
                    "required": ["result"],
                    "properties": {
                        "result": {"type": "string", "description": "输出说明"}
                    },
                },
                "depends_on": [],
            },
            {
                "id": 2,
                "agent": "another_agent",
                "action": "依赖步骤1的动作",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "step_1_output": {
                            "type": "object",
                            "description": "步骤1的输出",
                        }
                    },
                },
                "output_schema": {
                    "type": "object",
                    "properties": {"final_result": {"type": "string"}},
                },
                "depends_on": [1],
            },
        ],
        "completion_criteria": "所有步骤成功完成",
    }


@router.get("/dag/agents")
async def list_dag_available_agents(
    current_user: CurrentUser = Depends(get_current_user_hybrid),
):
    """
    列出可用于DAG的Agent

    返回当前用户可以在DAG中使用的所有Agent列表。
    """
    try:
        user_id = current_user.user_id

        # 获取所有agent分类
        categories = await mongodb_client.agent_repository.list_agent_categories(
            user_id
        )

        agents_info = []
        for category in categories:
            agents = await mongodb_client.agent_repository.list_agents_in_category(
                user_id=user_id, category=category["category"]
            )

            for agent in agents:
                agent_config = agent.get("agent_config", {})
                agents_info.append(
                    {
                        "name": agent_config.get("name", ""),
                        "description": agent_config.get(
                            "description", f"{category['category']} Agent"
                        ),
                        "category": category["category"],
                        "actions": ["execute", "analyze", "process"],  # 通用动作
                        "tags": agent_config.get("tags", []),
                    }
                )

        return {"agents": agents_info, "total": len(agents_info)}

    except Exception as e:
        logger.warning(f"获取agent列表失败，返回默认列表: {str(e)}")
        # 如果获取真实agent失败，返回默认列表
        return {
            "agents": [
                {
                    "name": "plan_agent",
                    "description": "任务规划Agent",
                    "category": "planning",
                    "actions": ["plan", "analyze", "structure"],
                    "tags": ["planning", "task"],
                },
                {
                    "name": "RiskAnalyzeAgent",
                    "description": "风险分析Agent",
                    "category": "work-agent",
                    "actions": ["analyze_risk", "assess_compliance", "generate_report"],
                    "tags": ["risk", "compliance"],
                },
                {
                    "name": "CompanySearchAgent",
                    "description": "公司搜索Agent",
                    "category": "work-agent",
                    "actions": ["search_company", "fetch_data", "validate_info"],
                    "tags": ["search", "company"],
                },
            ],
            "total": 3,
        }


# ======= 任务规划模式 API接口 =======
class PlanningModeRequest(BaseModel):
    """任务规划模式请求"""

    user_query: str = Field(..., description="用户查询")
    conversation_id: Optional[str] = Field(None, description="对话ID")
    max_concurrent: int = Field(default=5, ge=1, le=20, description="最大并发数")
    include_agents: Optional[List[str]] = Field(None, description="指定可用的agent列表")
    plan_agent_name: str = Field(default="plan_agent", description="规划Agent的名称")


@router.post("/planning-mode")
async def execute_planning_mode(
    request: PlanningModeRequest,
    current_user: CurrentUser = Depends(get_current_user_hybrid),
):
    """
    任务规划模式

    该模式会：
    1. 使用plan_agent根据用户查询生成DAG计划
    2. 根据DAG中定义的依赖关系，并行或串行执行各个agent
    3. 流式返回执行过程和结果

    整个过程是异步的，支持复杂的多步骤任务编排。
    """
    try:
        user_id = current_user.user_id

        # 验证用户查询
        if not request.user_query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="用户查询不能为空"
            )

        # 生成或使用现有conversation_id
        conversation_id = request.conversation_id or str(ObjectId())

        # 获取可用的agent列表
        available_agents = []

        if request.include_agents:
            # 使用指定的agent列表
            for agent_name in request.include_agents:
                agent = await mongodb_client.agent_repository.get_agent(
                    agent_name, user_id
                )
                if agent:
                    agent_config = agent.get("agent_config", {})
                    available_agents.append(
                        {
                            "name": agent_config.get("name", agent_name),
                            "description": agent_config.get("description", ""),
                            "category": agent_config.get("category", "unknown"),
                            "actions": ["execute", "analyze", "process"],
                            "tags": agent_config.get("tags", []),
                        }
                    )
        else:
            # 获取所有可用的agent
            try:
                categories = await mongodb_client.agent_repository.list_categories(
                    user_id
                )

                for category_item in categories:
                    category_name = category_item.get("category", "")
                    agents = (
                        await mongodb_client.agent_repository.list_agents_in_category(
                            user_id=user_id, category=category_name
                        )
                    )

                    for agent in agents:
                        agent_name = agent.get("name", "")
                        if agent_name:  # 只添加有名称的 agent
                            # 使用 get_agent_details 获取完整的 agent 详情
                            agent_details = (
                                await mongodb_client.agent_repository.get_agent_details(
                                    agent_name=agent_name, user_id=user_id
                                )
                            )

                            if agent_details:
                                agent_config = agent.get("agent_config", {})
                                available_agents.append(
                                    {
                                        "name": agent_config.get("name", agent_name),
                                        "description": agent_config.get(
                                            "card", agent_details.get("description", "")
                                        ),
                                        "category": agent_config.get(
                                            "category", category_name
                                        ),
                                        "tags": agent_config.get("tags", []),
                                        "model": agent_config.get("model"),
                                        "max_actions": agent_config.get(
                                            "max_actions", 50
                                        ),
                                    }
                                )
                logger.info(f"可用agent列表: {available_agents}")
            except Exception as e:
                logger.warning(f"获取agent列表失败: {str(e)}")

        # 执行规划模式
        async def generate_stream():
            try:
                async for event in plan_service.execute_planning_mode(
                    user_query=request.user_query,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    available_agents=available_agents,
                    max_concurrent=request.max_concurrent,
                    plan_agent_name=request.plan_agent_name,
                ):
                    yield event

            except Exception as e:
                logger.error(f"规划模式执行出错: {str(e)}")
                error_event = {"type": "error", "message": f"执行出错: {str(e)}"}
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"规划模式处理出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理规划模式请求时出错: {str(e)}",
        )
