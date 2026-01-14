import asyncio
import logging
import traceback
from typing import Dict, Any, Optional, List
import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import app.core.config as config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("memory_client")


class MemoryClient:
    """记忆服务客户端类 - 可直接实例化使用"""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        use_https: bool = False,
    ):
        cfg_host = config.settings.MEMORY_SERVICE_HOST
        cfg_port = config.settings.MEMORY_SERVICE_PORT

        self.host = host or cfg_host
        try:
            self.port = int(port) if port is not None else int(cfg_port)
        except (TypeError, ValueError):
            logger.warning("MEMORY_SERVICE_PORT 非法，使用配置端口 %s", cfg_port)
            self.port = int(cfg_port)
        self.use_https = use_https
        self.base_url = f"{'https' if use_https else 'http'}://{self.host}:{self.port}"
        self.timeout = 10.0  # 减少超时时间

    async def health_check(self) -> Dict[str, Any]:
        """检查记忆服务健康状态"""
        try:
            async with httpx.AsyncClient(
                verify=False, timeout=httpx.Timeout(5.0, connect=3.0)
            ) as client:
                response = await client.get(f"{self.base_url}/health")

                if response.status_code == 200:
                    return {
                        "success": True,
                        "status": "healthy",
                        "data": response.json() if response.content else {},
                    }
                else:
                    return {
                        "success": False,
                        "status": "unhealthy",
                        "error": f"HTTP {response.status_code}",
                    }
        except Exception as e:
            return {"success": False, "status": "error", "error": str(e)}

    async def add_memory(
        self,
        user_id: str,
        agent_id: str,
        session_id: str,
        memory_info: List[Dict[str, Any]],
        group_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        批量添加 memory
        memory_info: 列表，每个元素包含 content, role, metadata
        """
        """添加记忆"""
        # 过滤掉 content 为空或非字符串的
        safe_memory = []
        for m in memory_info:
            content = m.get("content")
            if content is None:
                continue
            if not isinstance(content, str):
                try:
                    import json

                    content = json.dumps(content, ensure_ascii=False)
                except Exception as e:
                    logger.error(f"memory content 序列化失败: {e}")
                    continue
            safe_memory.append(
                {
                    "content": content[:2000],
                    "role": m.get("role", "assistant"),
                    "metadata": m.get("metadata", {}),
                }
            )

        if not safe_memory:
            logger.warning("没有有效 memory 条目，跳过批量添加")
            return {"success": True, "data": None}
        payload = {
            "user_info": {
                "user_id": user_id,
                "agent_id": agent_id,
                "session_id": session_id,
                "group_id": group_id or "default",
            },
            "memory_infos": safe_memory,
        }

        try:
            async with httpx.AsyncClient(
                verify=False,  # 禁用SSL证书验证
                timeout=httpx.Timeout(self.timeout, connect=5.0),  # 设置连接和总超时
                follow_redirects=True,  # 允许重定向
            ) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/add_memory",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"记忆添加成功: {user_id}/{session_id}")
                    return {"success": True, "data": result}
                else:
                    error_msg = f"添加记忆失败: HTTP {response.status_code}"
                    try:
                        error_detail = (
                            response.json() if response.content else response.text
                        )
                        logger.error(f"{error_msg}, 响应详情: {error_detail}")
                        logger.debug(f"请求负载: {payload}")
                    except:
                        logger.error(f"{error_msg}, 响应: {response.text}")
                    return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = f"添加记忆时出错: {str(e)}"
            logger.warning(error_msg)  # 改为warning级别
            return {"success": False, "error": error_msg}

    async def search_memory(
        self,
        user_id: str,
        agent_id: str,
        session_id: str,
        query: str,
        group_id: Optional[str] = None,
        limit: str = "10",
        filter_dict: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """搜索记忆"""
        payload = {
            "user_info": {
                "user_id": user_id,
                "agent_id": agent_id,
                "session_id": session_id,
                "group_id": group_id,
            },
            "query_info": {
                "query": query,
                "limit": limit,
                "filter_dict": filter_dict or {},
                "timeout": timeout,
            },
        }

        try:
            async with httpx.AsyncClient(
                verify=False,  # 禁用SSL证书验证
                timeout=httpx.Timeout(max(timeout, 10), connect=5.0),  # 动态超时设置
                follow_redirects=True,  # 允许重定向
            ) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/search_memory",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"记忆搜索成功: {user_id}/{session_id}, 查询: {query}")
                    return {"success": True, "data": result}
                else:
                    error_msg = f"搜索记忆失败: HTTP {response.status_code}"
                    logger.error(f"{error_msg}, 响应: {response.text}")
                    return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = f"搜索记忆时出错: {str(e)}"
            logger.warning(error_msg)  # 改为warning级别
            return {"success": False, "error": error_msg}


# === 以下是可选的 HTTP API 服务部分 ===

app = FastAPI(title="Memory Client", description="Memory Client for MAG")

# 全局状态
MEMORY_CLIENT: Optional[MemoryClient] = None


# 数据模型
class AddMemoryRequest(BaseModel):
    user_id: str
    agent_id: str
    session_id: str
    group_id: str
    content: str
    role: str = "user"
    metadata: Optional[Dict[str, Any]] = None


class SearchMemoryRequest(BaseModel):
    user_id: str
    agent_id: str
    session_id: str
    group_id: str
    query: str
    limit: str = "10"
    filter_dict: Optional[Dict[str, Any]] = None
    timeout: int = 30


# API端点


@app.get("/")
async def root():
    """记忆客户端状态检查"""
    return {"status": "running"}


@app.post("/add_memory")
async def add_memory(request: AddMemoryRequest):
    """添加记忆"""
    if not MEMORY_CLIENT:
        raise HTTPException(status_code=400, detail="记忆客户端未初始化")

    try:
        result = await MEMORY_CLIENT.add_memory(
            user_id=request.user_id,
            agent_id=request.agent_id,
            session_id=request.session_id,
            group_id=request.group_id,
            content=request.content,
            role=request.role,
            metadata=request.metadata,
        )

        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=400, detail=result["error"])

    except Exception as e:
        logger.error(f"添加记忆时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search_memory")
async def search_memory(request: SearchMemoryRequest):
    """搜索记忆"""
    if not MEMORY_CLIENT:
        raise HTTPException(status_code=400, detail="记忆客户端未初始化")

    try:
        result = await MEMORY_CLIENT.search_memory(
            user_id=request.user_id,
            agent_id=request.agent_id,
            session_id=request.session_id,
            group_id=request.group_id,
            query=request.query,
            limit=request.limit,
            filter_dict=request.filter_dict,
            timeout=request.timeout,
        )

        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=400, detail=result["error"])

    except Exception as e:
        logger.error(f"搜索记忆时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """启动事件"""
    global MEMORY_CLIENT
    MEMORY_CLIENT = MemoryClient()
    logger.info("记忆客户端启动...")


def run_memory_client(host="127.0.0.1", port=8766):
    """运行记忆客户端"""
    uvicorn.run(app, host=host, port=port)


MEMORY_CLIENT = MemoryClient()
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Memory Client for MAG")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8766, help="Port to bind")

    args = parser.parse_args()
    run_memory_client(host=args.host, port=args.port)
