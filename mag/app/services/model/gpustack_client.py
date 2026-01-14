import logging
from typing import Dict, Any, Optional

import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class GPUStackClient:
    """与 GPUStack 平台交互的异步客户端

    功能：
    - 登录并获取认证 Cookie
    - 拉取 /v2/models 的模型状态列表
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 8,
    ):
        # 默认从配置读取 URL 与凭据；支持传参覆盖
        cfg_base = (
            settings.GPUSTACK_BASE_URL
            or f"http://{settings.GPUSTACK_SERVICE_HOST}:{settings.GPUSTACK_SERVICE_PORT}"
        )
        raw_base = (base_url or cfg_base).rstrip("/")
        if raw_base.endswith("/v1"):
            raw_base = raw_base[:-3]
        self.base_url = raw_base

        # 优先使用传入，其次 GPUSTACK_*，最后退回 ADMIN_*
        self.username = (
            username or settings.GPUSTACK_USERNAME or settings.ADMIN_USERNAME
        )
        self.password = (
            password or settings.GPUSTACK_PASSWORD or settings.ADMIN_PASSWORD
        )
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            # 默认启用证书校验与禁止重定向，提升安全性
            self._client = httpx.AsyncClient(
                verify=True,
                timeout=self.timeout,
                follow_redirects=False,
                headers={"accept": "application/json"},
            )
        return self._client

    async def login(self) -> bool:
        """登录以获取认证 Cookie"""
        try:
            client = await self._ensure_client()
            login_url = f"{self.base_url}/auth/login"
            headers = {
                "accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            data = {
                "username": self.username or "",
                "password": self.password or "",
            }
            resp = await client.post(login_url, headers=headers, data=data)
            if resp.status_code == 200:
                logger.debug("GPUStack 登录成功")
                return True
            # 避免记录响应正文，降低泄露风险
            logger.warning(f"GPUStack 登录失败: HTTP {resp.status_code}")
            return False
        except Exception as e:
            logger.warning(f"GPUStack 登录异常: {e}")
            return False

    @staticmethod
    def _parse_models_response(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        items = data.get("items", [])
        for item in items:
            name = item.get("name")
            if not name:
                continue
            result[name] = {
                "replicas": item.get("replicas", 0),
                "ready_replicas": item.get("ready_replicas", 0),
                "access_policy": item.get("access_policy", ""),
                "categories": item.get("categories", []),
                "backend": item.get("backend", ""),
            }
        return result

    async def get_models_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有模型状态，返回以模型名称为键的字典"""
        result: Dict[str, Dict[str, Any]] = {}
        try:
            client = await self._ensure_client()
            url = f"{self.base_url}/v2/models"
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning(f"获取模型状态失败: HTTP {resp.status_code}")
                return result
            return self._parse_models_response(resp.json())
        except Exception as e:
            logger.warning(f"拉取模型状态异常: {e}")
            return result

    async def get_models_status_with_api_key(
        self, api_key: str
    ) -> Dict[str, Dict[str, Any]]:
        """使用 API Key 获取所有模型状态，返回以模型名称为键的字典"""
        result: Dict[str, Dict[str, Any]] = {}
        try:
            client = await self._ensure_client()
            url = f"{self.base_url}/v2/models"
            headers = {
                "accept": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.warning(f"(API Key) 获取模型状态失败: HTTP {resp.status_code}")
                return result
            return self._parse_models_response(resp.json())
        except Exception as e:
            logger.warning(f"(API Key) 拉取模型状态异常: {e}")
            return result

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
