import platform
import os
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent.parent.parent
mag_services_env_path = project_root / "docker" / "mag_services" / ".env"

if mag_services_env_path.exists():
    load_dotenv(mag_services_env_path)
else:
    # 如果找不到，尝试从当前工作目录加载
    cwd_env_path = Path.cwd() / "docker" / "mag_services" / ".env"
    if cwd_env_path.exists():
        load_dotenv(cwd_env_path)


class Settings:
    """应用配置设置"""

    # 应用版本和名称
    APP_NAME: str = "MAG - MCP Agent Graph"
    APP_VERSION: str = "3.0.0"

    MONGODB_URL: str = os.getenv(
        "MONGODB_URL",
        f"mongodb://{os.getenv('MONGO_ROOT_USERNAME', 'admin')}:"
        f"{os.getenv('MONGO_ROOT_PASSWORD', 'securepassword123')}@"
        f"localhost:{os.getenv('MONGO_PORT', '27017')}/"
        "?authSource=admin",
    )

    MONGODB_DB: str = os.getenv("MONGO_DATABASE", "mcp-agent-graph")

    # JWT 配置
    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY", "your-secret-key-change-in-production"
    )
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    )  # 15分钟
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = int(
        os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")
    )  # 7天

    # 超级管理员配置
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")

    # MinIO 配置
    MINIO_ENDPOINT: str = os.getenv(
        "MINIO_ENDPOINT", f"localhost:{os.getenv('MINIO_API_PORT', '9010')}"
    )
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ROOT_USER", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
    MINIO_BUCKET_NAME: str = os.getenv("MINIO_BUCKET_NAME", "mag")

    # Memory Service 配置
    MEMORY_SERVICE_HOST: str = os.getenv("MEMORY_SERVICE_HOST", "127.0.0.1")
    MEMORY_SERVICE_PORT: int = int(os.getenv("MEMORY_SERVICE_PORT", "8851"))

    # FILE_SYSTEM (MCP models) service
    FILE_SYSTEM_HOST: str = (
        os.getenv("FILE_SYSTEM_HOST", "") or ""
    ).strip() or "127.0.0.1"
    FILE_SYSTEM_PORT: int = int(
        (os.getenv("FILE_SYSTEM_PORT", "8080") or "8080").strip()
    )
    FILE_SYSTEM_API_PREFIX: str = (
        os.getenv("FILE_SYSTEM_API_PREFIX", "/api/v1") or "/api/v1"
    ).strip() or "/api/v1"
    FILE_SYSTEM_BASE_URL: str = (
        os.getenv("FILE_SYSTEM_BASE_URL")
        or f"http://{FILE_SYSTEM_HOST}:{FILE_SYSTEM_PORT}{FILE_SYSTEM_API_PREFIX}"
    )

    # GPUStack 平台配置（通过 Cookie 认证拉取 /v2/models）
    # 支持从主机/端口构建 base_url，兼容 .env 中 GPUSTACK_SERVICE_HOST/PORT
    GPUSTACK_SERVICE_HOST: str = (
        os.getenv("GPUSTACK_SERVICE_HOST", "127.0.0.1") or ""
    ).strip()
    GPUSTACK_SERVICE_PORT: int = int(
        (os.getenv("GPUSTACK_SERVICE_PORT", "8899") or "8899").strip()
    )
    GPUSTACK_BASE_URL: str = (
        os.getenv("GPUSTACK_BASE_URL")
        or f"http://{GPUSTACK_SERVICE_HOST}:{GPUSTACK_SERVICE_PORT}"
    )
    GPUSTACK_API_KEY: str = (
        os.getenv("GPUSTACK_API_KEY", "gpustack-key") or "gpustack-key"
    ).strip()
    GPUSTACK_USERNAME: str = (os.getenv("GPUSTACK_USERNAME", "") or "").strip()
    GPUSTACK_PASSWORD: str = (os.getenv("GPUSTACK_PASSWORD", "") or "").strip()

    # 云端模型仓库配置
    CLOUD_GATEWAY_BASE_URL: str = os.getenv(
        "CLOUD_GATEWAY_BASE_URL", "http://192.168.1.86:8080"
    )

    # 根据操作系统确定配置目录
    @property
    def MAG_DIR(self) -> Path:
        """获取MAG配置目录"""

        # 默认行为
        system = platform.system()
        home = Path.home()

        if system == "Windows":
            return home / ".mag"
        elif system == "Darwin":  # macOS
            return home / ".mag"
        elif system == "Linux":
            return home / ".mag"
        else:
            return home / ".mag"

    @property
    def EXPORTS_DIR(self) -> Path:
        """获取导出文件存储目录"""
        return self.MAG_DIR / "exports"

    @property
    def MCP_TOOLS_DIR(self) -> Path:
        """获取AI生成的MCP工具存储目录"""
        return self.MAG_DIR / "mcp"

    def ensure_directories(self) -> None:
        """确保所有必要的目录存在"""
        self.MAG_DIR.mkdir(exist_ok=True)
        self.EXPORTS_DIR.mkdir(exist_ok=True)
        self.MCP_TOOLS_DIR.mkdir(exist_ok=True)

    def get_mcp_tool_dir(self, tool_name: str) -> Path:
        """获取指定MCP工具的目录路径"""
        return self.MCP_TOOLS_DIR / tool_name


# 创建全局设置实例
settings = Settings()
