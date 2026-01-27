import logging
import asyncio
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
from app.core.device_initialization import DeviceInitializer
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

        except Exception as e:
            logger.warning(f"GPUStack客户端初始化失败: {e}")

        # 9. 初始化记忆客户端
        global memory_client
        memory_client = MemoryClient()

        # 10. 初始化设备认证服务
        try:
            success, message, credentials = await DeviceInitializer.initialize_device()
            if success:
                logger.info(
                    f"设备初始化成功: {credentials.device_id if credentials else '待注册'}"
                )
            else:
                logger.warning(f"设备初始化结果: {message}")
        except Exception as e:
            logger.warning(f"设备初始化出错（不阻断启动）: {e}")

        # 11. 初始化 MCP2（加载 user_servers + 启动 idle cleanup loop）
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
            # 断开MongoDB连接（添加超时防护）
            try:
                await asyncio.wait_for(mongodb_client.disconnect(), timeout=5.0)
                logger.info("MongoDB连接已断开")
            except asyncio.TimeoutError:
                logger.warning("MongoDB连接断开超时，强制关闭")
                if mongodb_client.client:
                    try:
                        mongodb_client.client.close()
                        logger.info("MongoDB连接已强制关闭")
                    except Exception as e:
                        logger.warning(f"强制关闭MongoDB时出错: {str(e)}")
        except Exception as e:
            logger.error(f"断开MongoDB连接时出错: {str(e)}")
        # Stop MCP2 cleanup loop
        try:
            from app.services.mcp2.mcp2_manager import mcp2_manager

            try:
                await asyncio.wait_for(mcp2_manager.stop_cleanup_loop(), timeout=10.0)
                logger.info("MCP2 cleanup loop 已停止")
            except asyncio.TimeoutError:
                logger.warning("停止 MCP2 cleanup loop 超时，继续关闭")
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
