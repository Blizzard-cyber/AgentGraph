import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.api.routes import router
from app.services.mcp.mcp_service import mcp_service
from app.services.model.model_service import model_service
from app.services.graph.graph_service import graph_service
from memory_client import MemoryClient
from app.infrastructure.database.mongodb import mongodb_client
from app.infrastructure.storage.file_storage import FileManager
from app.core.config import settings
from app.core.initialization import initialize_system
from app.services.model.gpustack_client import GPUStackClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mag")

# 全局记忆客户端实例
memory_client: MemoryClient = None


def create_progress_bar(progress: float, width: int = 30) -> str:
    """创建可视化进度条

    Args:
        progress: 进度百分比 (0-100)
        width: 进度条宽度（字符数）

    Returns:
        str: 格式化的进度条字符串
    """
    filled = int(width * progress / 100)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {progress:6.1f}%"


async def test_model_deployment(gpustack_client: GPUStackClient):
    """测试模型部署功能

    用于验证GPUStack客户端的模型部署、查询和监听功能
    """
    logger.info("=" * 70)
    logger.info("开始测试 GPUStack 模型部署功能")
    logger.info("=" * 70)

    try:
        # 1. 列出现有模型
        logger.info("--- 步骤1: 列出现有模型 ---")
        models = await gpustack_client.list_models()
        logger.info(f"当前已有 {len(models)} 个模型")

        # 检查测试模型是否已存在
        test_model_name = "qwen3-0.6b-test"
        existing_model = None
        for model in models:
            if model.get("name") == test_model_name:
                existing_model = model
                logger.info(
                    f"发现已存在的测试模型: ID={model.get('id')}, "
                    f"状态={model.get('state')}"
                )
                break

        # 2. 如果模型已存在，先删除
        if existing_model:
            logger.info("--- 步骤2: 删除已存在的测试模型 ---")
            model_id = existing_model.get("id")
            if await gpustack_client.delete_model(model_id):
                logger.info(f"测试模型 {model_id} 删除成功")
                import asyncio

                await asyncio.sleep(3)  # 等待删除完成
            else:
                logger.warning(f"删除测试模型 {model_id} 失败")
        else:
            logger.info("--- 步骤2: 无需删除（测试模型不存在）---")

        # 3. 创建新的测试模型（使用轻量级配置）
        logger.info("--- 步骤3: 创建测试模型 ---")
        model_payload = {
            "name": "qwen3-0.6B",
            "source": "download_url",
            "cluster_id": 1,
            "backend": "vLLM",
            "backend_version": None,
            "replicas": 1,
            "extended_kv_cache": {"enabled": False},
            "speculative_config": {"enabled": False},
            "categories": ["test"],
            "backend_parameters": ["--gpu-memory-utilization=0.9"],
            "distributed_inference_across_workers": True,
            "restart_on_error": True,
            "generic_proxy": False,
            "download_url_model_name": "qwen3-0.6b",
            "download_url": "http://192.168.1.86:9000/llm-models/qwen3-0.6B/1.0.0/69674bc0e4b01e1f6e7f1743.zip?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Date=20260114T101909Z&X-Amz-SignedHeaders=host&X-Amz-Expires=3600&X-Amz-Credential=rustfsadmin%2F20260114%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Signature=7343a10c79b5f14824dd803ff08d19a3adf35753c5fe47140bce9bf50a1b4682",
            "placement_strategy": "spread",
            "worker_selector": {"worker-name": "90.ndsl"},
            "gpu_selector": None,
        }

        model_id = await gpustack_client.create_model(model_payload)

        if not model_id:
            logger.warning("测试模型创建失败，跳过后续测试")
            return

        logger.info(f"测试模型创建成功，ID: {model_id}")

        # 4. 监听模型部署状态（使用SSE）
        logger.info("--- 步骤4: 监听模型部署状态 (SSE) ---")
        logger.info("开始监听模型实例状态变化...")

        import asyncio

        event_count = 0
        max_events = 50  # 最多处理50个事件
        timeout = 300  # 5分钟超时
        last_progress = -1  # 跟踪上次显示的进度，避免重复输出

        try:
            async for event in gpustack_client.watch_model_instances(
                model_id=model_id, timeout=timeout
            ):
                event_count += 1

                instance_id = event.get("id")
                state = event.get("state", "unknown")
                download_progress = event.get("download_progress")
                state_message = event.get("state_message", "")
                worker_name = event.get("worker_name", "N/A")

                # 构建日志输出
                # 状态图标映射
                state_icons = {
                    "initializing": "🔄",
                    "downloading": "⬇️ ",
                    "analyzing": "🔍",
                    "pending": "⏳",
                    "starting": "🚀",
                    "running": "✅",
                    "error": "❌",
                    "scheduled": "📅",
                }
                icon = state_icons.get(state, "📦")

                # 基础日志信息
                log_msg = (
                    f"{icon} 实例 {instance_id}: {state:<12} | Worker: {worker_name}"
                )

                # 如果是下载状态且有进度信息，添加进度条
                if state == "downloading" and download_progress is not None:
                    # 只在进度变化显著时才输出（避免刷屏）
                    progress_diff = abs(download_progress - last_progress)
                    if progress_diff >= 1.0 or download_progress >= 100.0:
                        progress_bar = create_progress_bar(download_progress, width=40)
                        log_msg = f"{icon} 实例 {instance_id}: {state:<12} | {progress_bar} | Worker: {worker_name}"
                        last_progress = download_progress
                        logger.info(log_msg)
                    # 进度变化不大，跳过输出
                    else:
                        continue
                else:
                    # 非下载状态，正常输出
                    if download_progress is not None and download_progress > 0:
                        log_msg += f" | 进度: {download_progress:.1f}%"
                    if state_message:
                        log_msg += f" | 消息: {state_message}"
                    logger.info(log_msg)
                    last_progress = -1  # 重置进度跟踪

                # 检查终止条件
                if state == "running":
                    logger.info(f"🎉 实例 {instance_id} 部署成功！")
                    break
                elif state == "error":
                    logger.error(f"❌ 实例 {instance_id} 部署失败: {state_message}")
                    break

                # 防止无限循环
                if event_count >= max_events:
                    logger.warning(f"已处理 {max_events} 个事件，停止监听")
                    break

        except asyncio.TimeoutError:
            logger.warning("监听模型状态超时")
        except Exception as e:
            logger.warning(f"监听模型状态异常: {e}")

        # 5. 查询最终状态
        logger.info("--- 步骤5: 查询模型最终状态 ---")
        final_model = await gpustack_client.get_model(model_id)
        if final_model:
            logger.info(f"模型状态: {final_model.get('state')}")
            logger.info(
                f"就绪副本: {final_model.get('ready_replicas')}/{final_model.get('replicas')}"
            )

        # 6. 获取模型实例列表
        logger.info("--- 步骤6: 获取模型实例列表 ---")
        instances = await gpustack_client.get_model_instances(model_id=model_id)
        logger.info(f"模型 {model_id} 共有 {len(instances)} 个实例")
        for inst in instances:
            logger.info(
                f"  实例 {inst.get('id')}: {inst.get('state')} "
                f"@ {inst.get('worker_name')}"
            )

        logger.info("=" * 70)
        logger.info("GPUStack 模型部署功能测试完成")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
        import traceback

        traceback.print_exc()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Starting MAG application...")

    try:
        # 1. 确保目录存在
        logger.info(f"配置目录: {settings.MAG_DIR}")
        settings.ensure_directories()

        # 2. 连接MongoDB
        await mongodb_client.initialize(settings.MONGODB_URL, settings.MONGODB_DB)
        logger.info("MongoDB connected successfully")

        # 3. 执行系统初始化（创建超级管理员、团队）
        await initialize_system()
        logger.info("System initialization completed")

        # 4. 初始化文件系统
        FileManager.initialize()
        logger.info("文件系统初始化成功")

        # 5. 初始化模型服务
        await model_service.initialize(mongodb_client)
        logger.info("模型服务初始化成功")

        # 6. 初始化图服务
        await graph_service.initialize()
        logger.info("图服务初始化成功")

        # 7. 初始化MCP服务 - 启动客户端进程
        await mcp_service.initialize()
        logger.info("MCP服务初始化成功")

        # 8. 初始化GPUStack客户端（登录获取Cookie，会被模型服务复用）
        try:
            await model_service.initialize_gpustack_client()
            logger.info("GPUStack客户端初始化流程完成")

            # 测试模型部署功能
            if model_service.gpustack_client:
                logger.info("检测到启用模型部署测试，开始执行测试...")
                await test_model_deployment(model_service.gpustack_client)
        except Exception as e:
            logger.warning(f"GPUStack客户端初始化失败: {e}")

        # 9. 初始化记忆客户端
        global memory_client
        memory_client = MemoryClient()

        # 10. 初始化 MCP2（加载 user_servers + 启动 idle cleanup loop）
        try:
            from app.services.mcp2.mcp2_init import init_mcp2_state
            await init_mcp2_state()
            logger.info("MCP2 初始化完成")
        except Exception as e:
                logger.warning(f"MCP2 初始化失败（不阻断启动）: {e}")


        # 测试记忆服务连接
        try:
            health_result = await memory_client.health_check()
            if health_result["success"]:
                logger.info("记忆客户端连接测试成功")
            else:
                logger.warning(f"记忆服务连接异常: {health_result['error']}")
        except Exception as e:
            logger.warning(f"记忆服务连接测试失败: {str(e)}")

        logger.info("记忆客户端初始化完成")

        logger.info("所有服务初始化完成")

        yield

    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        import traceback

        traceback.print_exc()
        raise
    finally:
        logger.info("Shutting down MAG application...")

        try:
            # 清理MCP服务
            await mcp_service.cleanup()
            logger.info("MCP服务清理完成")
        except Exception as e:
            logger.error(f"清理MCP服务时出错: {str(e)}")

        try:
            # 清理记忆客户端（如果需要）
            if memory_client:
                # memory_client 目前没有需要清理的资源，但保留接口
                logger.info("记忆客户端清理完成")
        except Exception as e:
            logger.error(f"清理记忆客户端时出错: {str(e)}")

        try:
            # 断开MongoDB连接
            await mongodb_client.disconnect()
            logger.info("MongoDB连接已断开")
        except Exception as e:
            logger.error(f"断开MongoDB连接时出错: {str(e)}")
        # Stop MCP2 cleanup loop
        try:
            from app.services.mcp2.mcp2_manager import mcp2_manager
            await mcp2_manager.stop_cleanup_loop()
            logger.info("MCP2 cleanup loop 已停止")
        except Exception as e:
            logger.error(f"停止 MCP2 cleanup loop 失败: {e}")



# 创建应用（使用lifespan）
app = FastAPI(
    title="MAG - MCP Agent Graph",
    description="通过MCP+Graph构建Agent系统的工具",
    version="2.0.0",
    lifespan=lifespan,
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理的异常: {str(exc)}")
    import traceback

    traceback.print_exc()
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"服务器内部错误: {str(exc)}"},
    )


# 注册路由
app.include_router(router, prefix="/api")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


# === 静态文件服务（可通过环境变量控制） ===
# MAG_INTERNAL_STATIC： 是否由 FastAPI 内部提供静态资源（默认 true）
# MAG_FRONTEND_DIST  ： 前端构建产物目录（默认 <project>/mag/dist）
import os

STATIC_SERVE_ENABLED = os.getenv("MAG_INTERNAL_STATIC", "true").lower() == "true"
FRONTEND_DIST_DIR = Path(
    os.getenv("MAG_FRONTEND_DIST", str(Path(__file__).parent.parent / "dist"))
)

# 仅当启用了内部静态服务、且目录存在时挂载
if STATIC_SERVE_ENABLED and FRONTEND_DIST_DIR.exists() and FRONTEND_DIST_DIR.is_dir():
    logger.info(f"前端静态文件目录存在: {FRONTEND_DIST_DIR}")

    # 挂载静态资源目录（CSS, JS, images等）
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIST_DIR / "assets")),
        name="assets",
    )

    # 处理所有非API路由，返回index.html（支持前端路由）
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """
        为所有非API路由提供前端应用
        支持前端单页应用的客户端路由
        """
        # 如果请求的是具体文件且存在，直接返回
        file_path = FRONTEND_DIST_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)

        # 否则返回 index.html，让前端路由处理
        index_path = FRONTEND_DIST_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)

        # 如果 index.html 不存在，返回 404
        return JSONResponse(status_code=404, content={"detail": "Frontend not found"})

else:
    if STATIC_SERVE_ENABLED:
        logger.warning(f"前端静态文件目录不存在: {FRONTEND_DIST_DIR}")
        logger.warning("如需使用集成前端，请先运行 'npm run build' 构建前端应用")
    else:
        logger.info(
            "已禁用 FastAPI 内部静态资源服务 (MAG_INTERNAL_STATIC=false)，由外部 Nginx/CDN 提供"
        )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=9999,
        reload=False,
        log_level="info",
    )
