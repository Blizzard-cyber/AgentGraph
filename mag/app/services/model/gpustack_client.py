import logging
from typing import Dict, Any, Optional, List, AsyncGenerator
import json

import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class GPUStackClient:
    """与 GPUStack 平台交互的异步客户端

    功能：
    - 登录并获取认证 Cookie
    - 拉取 /v2/models 的模型状态列表
    - 创建、删除、查询模型
    - 获取模型实例信息
    - 监听模型部署状态 (SSE)
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
                # 检查并记录获取到的 Cookie
                cookies_dict = dict(client.cookies)
                if cookies_dict:
                    cookie_names = list(cookies_dict.keys())
                    logger.info(
                        f"GPUStack 登录成功，已获取并保存 Cookie: {cookie_names}"
                    )
                else:
                    logger.warning("GPUStack 登录成功但未获取到 Cookie")
                return True
            # 避免记录响应正文，降低泄露风险
            logger.warning(f"GPUStack 登录失败: HTTP {resp.status_code}")
            return False
        except Exception as e:
            logger.warning(f"GPUStack 登录异常: {e}")
            return False

    def has_valid_cookies(self) -> bool:
        """检查是否有有效的认证 Cookie

        Returns:
            bool: 如果client存在且有cookies则返回True
        """
        if self._client is None:
            return False
        cookies_dict = dict(self._client.cookies)
        return len(cookies_dict) > 0

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

            # 记录使用cookie进行鉴权
            if self.has_valid_cookies():
                logger.debug(f"使用已保存的 Cookie 请求: {url}")
            else:
                logger.warning(f"请求 {url} 时未检测到 Cookie，可能需要先登录")

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

    # ========== 模型管理方法 ==========

    async def list_models(self) -> List[Dict[str, Any]]:
        """列出所有模型

        Returns:
            List[Dict]: 模型列表
        """
        try:
            client = await self._ensure_client()
            url = f"{self.base_url}/v2/models"

            if self.has_valid_cookies():
                logger.debug(f"使用已保存的 Cookie 请求模型列表: {url}")
            else:
                logger.warning(f"请求 {url} 时未检测到 Cookie，可能需要先登录")

            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning(f"获取模型列表失败: HTTP {resp.status_code}")
                return []

            data = resp.json()
            items = data.get("items", [])
            logger.info(f"获取到 {len(items)} 个模型")
            return items
        except Exception as e:
            logger.warning(f"获取模型列表异常: {e}")
            return []

    async def get_model(self, model_id: int) -> Optional[Dict[str, Any]]:
        """获取指定模型信息

        Args:
            model_id: 模型ID

        Returns:
            Optional[Dict]: 模型信息，不存在则返回None
        """
        try:
            client = await self._ensure_client()
            url = f"{self.base_url}/v2/models/{model_id}"

            resp = await client.get(url)
            if resp.status_code == 200:
                logger.debug(f"获取模型 {model_id} 信息成功")
                return resp.json()
            elif resp.status_code == 404:
                logger.debug(f"模型 {model_id} 不存在")
                return None
            else:
                logger.warning(f"获取模型 {model_id} 失败: HTTP {resp.status_code}")
                return None
        except Exception as e:
            logger.warning(f"获取模型 {model_id} 异常: {e}")
            return None

    async def create_model(self, payload: Dict[str, Any]) -> tuple[Optional[int], bool]:
        """创建模型部署任务

        Args:
            payload: 模型配置，包含以下字段:
                - name: 模型名称
                - source: 模型来源 (download_url, model_scope, hugging_face, local_path)
                - backend: 推理后端 (vLLM, llama-box等)
                - replicas: 副本数
                - cluster_id: 集群ID
                - worker_selector: Worker选择器
                - gpu_selector: GPU选择器
                等...

        Returns:
            tuple[Optional[int], bool]: (模型ID, 是否已存在)，创建失败返回(None, False)
        """
        try:
            client = await self._ensure_client()
            url = f"{self.base_url}/v2/models"

            model_name = payload.get("name", "unknown")
            logger.info(f"开始创建模型: {model_name}")
            logger.debug(
                f"模型配置: backend={payload.get('backend')}, "
                f"replicas={payload.get('replicas')}, "
                f"source={payload.get('source')}"
            )

            resp = await client.post(url, json=payload)

            if resp.status_code in [200, 201]:
                data = resp.json()
                model_id = data.get("id")
                logger.info(f"模型 {model_name} 创建成功，ID: {model_id}")
                return model_id, False  # 新创建的模型
            elif resp.status_code == 409:
                logger.info(f"模型 {model_name} 已存在于GPUStack，尝试查询模型ID")
                # 模型已存在，尝试查询该模型的ID
                try:
                    models = await self.list_models()
                    for model in models:
                        if model.get("name") == model_name:
                            existing_id = model.get("id")
                            logger.info(f"找到已存在的模型 {model_name}，ID: {existing_id}")
                            return existing_id, True  # 已存在的模型
                    logger.warning(f"模型 {model_name} 已存在但无法查询到ID")
                    return None, False
                except Exception as e:
                    logger.warning(f"查询已存在模型ID失败: {e}")
                    return None, False
            else:
                logger.warning(f"创建模型 {model_name} 失败: HTTP {resp.status_code}")
                try:
                    error_detail = resp.json()
                    logger.debug(f"错误详情: {error_detail}")
                except:
                    logger.debug(f"响应内容: {resp.text}")
                return None, False
        except Exception as e:
            logger.warning(f"创建模型异常: {e}")
            return None, False

    async def delete_model(self, model_id: int) -> bool:
        """删除指定模型

        Args:
            model_id: 模型ID

        Returns:
            bool: 删除成功返回True
        """
        try:
            client = await self._ensure_client()
            url = f"{self.base_url}/v2/models/{model_id}"

            logger.info(f"开始删除模型: {model_id}")
            resp = await client.delete(url)

            if resp.status_code in [200, 204]:
                logger.info(f"模型 {model_id} 删除成功")
                return True
            elif resp.status_code == 404:
                logger.warning(f"模型 {model_id} 不存在")
                return False
            else:
                logger.warning(f"删除模型 {model_id} 失败: HTTP {resp.status_code}")
                return False
        except Exception as e:
            logger.warning(f"删除模型 {model_id} 异常: {e}")
            return False

    # ========== 模型实例管理方法 ==========

    async def get_model_instances(
        self, model_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取模型实例列表

        Args:
            model_id: 模型ID，如果指定则只返回该模型的实例

        Returns:
            List[Dict]: 模型实例列表
        """
        try:
            client = await self._ensure_client()
            url = f"{self.base_url}/v2/model-instances"

            params = {}
            if model_id is not None:
                params["model_id"] = model_id

            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                logger.warning(f"获取模型实例失败: HTTP {resp.status_code}")
                return []

            data = resp.json()
            items = data.get("items", [])
            logger.debug(f"获取到 {len(items)} 个模型实例")
            return items
        except Exception as e:
            logger.warning(f"获取模型实例异常: {e}")
            return []

    async def watch_model_instances(
        self,
        model_id: Optional[int] = None,
        instance_id: Optional[int] = None,
        timeout: int = 3600,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """使用SSE监听模型实例状态变化

        Args:
            model_id: 模型ID，用于过滤指定模型的实例
            instance_id: 实例ID，用于只监听特定实例
            timeout: 超时时间（秒）

        Yields:
            Dict: 实例状态更新事件，包含以下字段:
                - id: 实例ID
                - model_id: 模型ID
                - state: 状态 (initializing, downloading, running, error等)
                - download_progress: 下载进度 (0-100)
                - state_message: 状态消息
                - worker_name: Worker名称
                - gpu_indexes: GPU索引列表
        """
        try:
            client = await self._ensure_client()
            url = f"{self.base_url}/v2/model-instances?watch=true"

            if model_id is not None:
                url += f"&model_id={model_id}"

            logger.info(
                f"开始监听模型实例状态 (model_id={model_id}, "
                f"instance_id={instance_id}, timeout={timeout}s)"
            )

            if not self.has_valid_cookies():
                logger.warning("未检测到有效Cookie，SSE连接可能失败")

            # 使用较长的超时时间用于SSE连接
            async with client.stream(
                "GET",
                url,
                timeout=httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0),
            ) as response:
                if response.status_code != 200:
                    logger.error(f"SSE连接失败: HTTP {response.status_code}")
                    return

                logger.info("SSE连接成功，开始接收事件...")

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    # 解析SSE数据
                    json_str = None
                    if line.startswith("data:"):
                        json_str = line[5:].strip()
                    elif line.startswith("{"):
                        json_str = line.strip()

                    if not json_str:
                        continue

                    try:
                        event_data = json.loads(json_str)

                        # 提取实例数据
                        if "data" in event_data:
                            instance = event_data["data"]
                        else:
                            instance = event_data

                        # 过滤：只处理指定模型或实例的事件
                        inst_id = instance.get("id")
                        inst_model_id = instance.get("model_id")

                        if instance_id is not None and inst_id != instance_id:
                            continue
                        if (
                            model_id is not None
                            and instance_id is None
                            and inst_model_id != model_id
                        ):
                            continue

                        # 返回事件
                        yield instance

                    except json.JSONDecodeError:
                        logger.debug(f"跳过无法解析的SSE行: {line[:100]}")
                        continue
                    except Exception as e:
                        logger.warning(f"处理SSE事件异常: {e}")
                        continue

        except httpx.TimeoutException:
            logger.warning(f"SSE连接超时 ({timeout}s)")
        except Exception as e:
            logger.warning(f"SSE监听异常: {e}")

    async def wait_for_model_ready(
        self,
        model_id: int,
        timeout: int = 3600,
        check_interval: int = 5,
    ) -> bool:
        """等待模型所有实例就绪

        Args:
            model_id: 模型ID
            timeout: 超时时间（秒）
            check_interval: 检查间隔（秒）

        Returns:
            bool: 所有实例就绪返回True，超时或失败返回False
        """
        import asyncio

        logger.info(f"等待模型 {model_id} 就绪 (超时: {timeout}s)")
        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                logger.warning(f"等待模型 {model_id} 就绪超时")
                return False

            # 获取模型信息
            model = await self.get_model(model_id)
            if not model:
                logger.warning(f"模型 {model_id} 不存在")
                return False

            state = model.get("state", "unknown")
            replicas = model.get("replicas", 0)
            ready_replicas = model.get("ready_replicas", 0)

            logger.debug(
                f"模型 {model_id} 状态: {state}, "
                f"就绪副本: {ready_replicas}/{replicas}"
            )

            # 检查是否所有副本都已就绪
            if state == "running" and ready_replicas == replicas and replicas > 0:
                logger.info(f"模型 {model_id} 所有实例已就绪")
                return True

            # 检查是否出错
            if state == "error":
                state_message = model.get("state_message", "")
                logger.error(f"模型 {model_id} 部署失败: {state_message}")
                return False

            # 等待后重试
            await asyncio.sleep(check_interval)

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
