"""
设备注册和认证服务

处理设备自助注册、凭证存储、设备认证等业务逻辑
"""

import logging
import os
import secrets
import string
from typing import Optional, Tuple
from datetime import datetime, timedelta
import httpx

from app.models.device_schema import (
    DeviceSelfRegisterRequest,
    DeviceAuthRequest,
    DeviceInfo,
    DeviceRegistrationResponse,
    DeviceAuthResponse,
    DeviceStatusResponse,
    DeviceCredentials,
    DeviceStatus,
    DeviceRegistrationMethod,
)
from app.infrastructure.database.mongodb.repositories.device_repository import (
    DeviceRepository,
)
from app.auth.jwt import create_tokens
from app.core.config import settings

logger = logging.getLogger(__name__)


class DeviceService:
    """设备注册和认证服务"""

    def __init__(self, device_repository: DeviceRepository):
        """
        初始化设备服务

        Args:
            device_repository: 设备数据仓库
        """
        self.device_repository = device_repository
        self.cloud_gateway_base_url = os.getenv(
            "CLOUD_GATEWAY_BASE_URL", "http://192.168.1.90:8088"
        )

    @staticmethod
    def generate_device_id() -> str:
        """生成设备ID"""
        # 格式: dev_xxxxxxxxxxxx
        random_part = secrets.token_urlsafe(12)
        return f"dev_{random_part}"

    @staticmethod
    def generate_device_secret(length: int = 48) -> str:
        """生成设备密钥"""
        # 格式: dev_sec_xxxxxxxxxxxx
        alphabet = string.ascii_letters + string.digits
        random_part = "".join(secrets.choice(alphabet) for _ in range(length - 8))
        return f"dev_sec_{random_part}"

    async def self_register_device(
        self,
        request: DeviceSelfRegisterRequest,
    ) -> Tuple[bool, str, Optional[DeviceCredentials]]:
        """
        设备自助注册（向云端注册）

        流程：
        1. 调用云端API进行注册（云端会处理重复注册和PSK验证）
        2. 保存返回的凭证到本地
        3. 如果本地已有旧记录，自动删除并使用新凭证

        Args:
            request: 设备自助注册请求

        Returns:
            Tuple[bool, str, Optional[DeviceCredentials]]: (成功标志, 消息, 设备凭证)
        """
        try:
            # 检查本地是否有旧记录（不阻止注册，只是记录日志）
            existing_device = await self.device_repository.find_by_device_identifier(
                request.device_identifier
            )
            if existing_device:
                logger.info(
                    f"设备 {request.device_identifier} 本地已有记录，将向云端请求重新注册"
                )

            # 调用云端认证服务进行注册（使用驼峰格式）
            logger.info(f"准备向云端注册设备: {request.device_identifier}")
            logger.info(
                f"云端URL: {self.cloud_gateway_base_url}/auth/devices/self-register"
            )

            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "deviceIdentifier": request.device_identifier,
                    "psk": request.psk,
                    "deviceName": request.device_name,
                    "location": request.location,
                }

                logger.info(
                    f"请求payload: deviceIdentifier={request.device_identifier}, deviceName={request.device_name}"
                )

                response = await client.post(
                    f"{self.cloud_gateway_base_url}/auth/devices/self-register",
                    json=payload,
                )

                logger.info(f"云端响应: HTTP {response.status_code}")

            # 检查响应状态码（200或201都是成功）
            if response.status_code not in [200, 201]:
                error_detail = response.text
                logger.warning(
                    f"云端注册失败 (HTTP {response.status_code}): {error_detail}"
                )
                return (
                    False,
                    f"云端注册失败: HTTP {response.status_code} - {error_detail[:100]}",
                    None,
                )

            cloud_response = response.json()
            if not cloud_response.get("success"):
                return (
                    False,
                    cloud_response.get("message", "云端注册失败"),
                    None,
                )

            # 提取云端返回的凭证
            cloud_device = cloud_response.get("device", {})
            # deviceSecret 在 device 对象内，不是在顶层
            cloud_device_secret = cloud_device.get("deviceSecret")

            logger.info(
                f"云端注册成功: deviceId={cloud_device.get('deviceId')}, status={cloud_device.get('status')}"
            )

            # 如果本地已有旧记录，先删除
            if existing_device:
                logger.info(f"删除本地旧记录: {existing_device['device_id']}")
                await self.device_repository.delete_device(existing_device["device_id"])

            # 保存本地设备凭证（使用驼峰字段）
            credentials = await self.device_repository.create_device(
                device_identifier=request.device_identifier,
                device_id=cloud_device.get("deviceId"),
                device_secret=cloud_device_secret,
                device_name=request.device_name,
                status=cloud_device.get("status", "pending"),
                registration_method=cloud_device.get("registrationMethod", "self"),
                location=request.location,
                extra_data=request.extra_data,
            )

            device_credentials = DeviceCredentials(
                device_id=credentials["device_id"],
                device_identifier=request.device_identifier,
                device_secret=cloud_device_secret,
                status=DeviceStatus(credentials["status"]),
                device_name=request.device_name,
                location=request.location,
                registration_method=DeviceRegistrationMethod(
                    credentials["registration_method"]
                ),
                created_at=credentials["created_at"],
                updated_at=credentials["updated_at"],
                extra_data=credentials.get("extra_data"),
            )

            logger.info(f"设备自助注册成功: {device_credentials.device_id}")
            return (
                True,
                "设备注册成功，等待管理员审批",
                device_credentials,
            )

        except Exception as e:
            logger.error(f"设备自助注册失败: {str(e)}")
            return (False, f"注册失败: {str(e)}", None)

    async def authenticate_device(
        self,
        device_id: str,
        device_secret: str,
    ) -> Tuple[bool, str, Optional[DeviceAuthResponse]]:
        """
        设备认证（获取JWT Token）

        流程：
        1. 验证设备凭证
        2. 调用云端API进行认证
        3. 获取JWT Token

        Args:
            device_id: 设备ID
            device_secret: 设备密钥

        Returns:
            Tuple[bool, str, Optional[DeviceAuthResponse]]: (成功标志, 消息, 认证响应)
        """
        try:
            # 检查本地设备是否存在
            device = await self.device_repository.find_by_device_id(device_id)
            if not device:
                logger.error(f"设备不存在: {device_id}")
                return (
                    False,
                    f"设备 {device_id} 不存在",
                    None,
                )

            logger.info(f"找到设备: {device_id}, 状态: {device.get('status')}")

            # 验证设备密钥（直接比对，因为当前存储的是明文）
            stored_secret = device.get("device_secret_hash", "")
            if stored_secret != device_secret:
                logger.warning(
                    f"设备密钥验证失败: {device_id}, 提供密钥: {device_secret[:20]}..., 存储密钥: {stored_secret[:20]}..."
                )
                return (False, "设备密钥验证失败", None)

            logger.info(f"设备密钥验证成功: {device_id}")

            # 认证前先从云端同步设备状态（获取最新的审批状态）
            logger.info(f"开始同步云端设备状态: {device_id}")
            try:
                status_url = f"{self.cloud_gateway_base_url}/auth/devices/{device_id}"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(status_url)

                    if response.status_code == 200:
                        cloud_device = response.json()
                        cloud_status = cloud_device.get("status")
                        local_status = device.get("status")

                        # 如果云端状态与本地不同，更新本地状态
                        if cloud_status != local_status:
                            await self.device_repository.update_device_status(
                                device_id, cloud_status
                            )
                            logger.info(
                                f"设备状态已更新: {device_id}, {local_status} -> {cloud_status}"
                            )
                            device = await self.device_repository.find_by_device_id(
                                device_id
                            )
                        else:
                            logger.info(
                                f"设备状态无变化: {device_id}, 状态: {cloud_status}"
                            )
                    else:
                        logger.warning(
                            f"从云端同步状态失败: HTTP {response.status_code}"
                        )
            except Exception as e:
                logger.warning(f"同步云端状态异常: {str(e)}, 继续使用本地状态")

            # 检查设备状态
            status = device.get("status")
            if status == "disabled":
                return (False, "设备已被禁用", None)
            elif status == "pending":
                return (
                    False,
                    "设备等待管理员审批，请稍候",
                    None,
                )

            logger.info(f"设备状态检查通过: {device_id}, 状态: {status}")

            # 调用云端认证服务获取Token
            # 注意：发送给云端时需要转换为驼峰格式
            auth_url = f"{self.cloud_gateway_base_url}/auth/devices/token"
            logger.info(f"调用云端认证URL: {auth_url}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "deviceId": device_id,
                    "deviceSecret": device_secret,
                    "grantType": "client_credentials",
                }

                logger.info(f"发送认证请求: {payload}")

                response = await client.post(
                    auth_url,
                    json=payload,
                )

            logger.info(f"云端认证响应: HTTP {response.status_code}")

            if response.status_code != 200:
                logger.warning(
                    f"云端认证失败: {response.status_code}, 响应: {response.text}"
                )
                return (
                    False,
                    f"云端认证失败: {response.status_code}",
                    None,
                )

            cloud_response = response.json()
            logger.info(f"云端认证响应内容: {cloud_response}")

            if not cloud_response.get("success"):
                return (
                    False,
                    cloud_response.get("message", "云端认证失败"),
                    None,
                )

            # 更新最后认证时间
            await self.device_repository.update_last_auth(device_id)

            # 如果还不是active状态，则更新为active
            if status != "active":
                await self.device_repository.update_device_status(device_id, "active")
                logger.info(f"设备状态更新为active: {device_id}")

            # 构建认证响应
            device_info = DeviceInfo(
                device_id=device["device_id"],
                device_identifier=device["device_identifier"],
                device_name=device["device_name"],
                status=DeviceStatus(device["status"]),
                location=device.get("location"),
                registration_method=DeviceRegistrationMethod(
                    device["registration_method"]
                ),
                approved_at=device.get("approved_at"),
                activated_at=device.get("activated_at"),
                created_at=device["created_at"],
                updated_at=device["updated_at"],
            )

            auth_response = DeviceAuthResponse(
                success=True,
                access_token=cloud_response.get("accessToken", ""),
                token_type="Bearer",
                expires_in=cloud_response.get("expiresIn", 86400),
                device_info=device_info,
            )

            logger.info(f"设备认证成功: {device_id}")
            return (True, "认证成功", auth_response)

        except Exception as e:
            logger.error(f"设备认证失败: {str(e)}")
            return (False, f"认证失败: {str(e)}", None)

    async def get_device_status(
        self,
        device_id: str,
    ) -> Tuple[bool, str, Optional[DeviceStatusResponse]]:
        """
        获取设备状态

        Args:
            device_id: 设备ID

        Returns:
            Tuple[bool, str, Optional[DeviceStatusResponse]]: (成功标志, 消息, 设备状态)
        """
        try:
            device = await self.device_repository.get_device_info(device_id)
            if not device:
                return (False, f"设备 {device_id} 不存在", None)

            status_response = DeviceStatusResponse(
                device_id=device["device_id"],
                device_identifier=device["device_identifier"],
                device_name=device["device_name"],
                status=DeviceStatus(device["status"]),
                location=device.get("location"),
                registration_method=DeviceRegistrationMethod(
                    device["registration_method"]
                ),
                created_at=device["created_at"],
                approved_at=device.get("approved_at"),
                activated_at=device.get("activated_at"),
                message=self._get_status_message(device["status"]),
            )

            return (True, "获取成功", status_response)

        except Exception as e:
            logger.error(f"获取设备状态失败: {str(e)}")
            return (False, f"获取失败: {str(e)}", None)

    @staticmethod
    def _get_status_message(status: str) -> str:
        """获取状态对应的消息"""
        messages = {
            "pending": "等待管理员审批",
            "approved": "已审批，可进行认证",
            "active": "已激活，正常运行",
            "disabled": "已禁用，无法使用",
        }
        return messages.get(status, "未知状态")

    async def send_heartbeat(
        self,
        device_id: str,
    ) -> Tuple[bool, str, Optional[dict]]:
        """
        向云端发送设备心跳

        Args:
            device_id: 设备ID

        Returns:
            Tuple[bool, str, Optional[dict]]: (成功标志, 消息, 响应数据)
        """
        try:
            # 查询本地设备信息
            device = await self.device_repository.find_by_device_id(device_id)
            if not device:
                return (False, f"设备 {device_id} 不存在", None)

            # 调用云端心跳接口
            heartbeat_url = f"{self.cloud_gateway_base_url}/auth/devices/heartbeat"
            logger.info(f"向云端发送心跳: {heartbeat_url}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    heartbeat_url,
                    json={"device_id": device_id},
                    timeout=10.0,
                )

                if response.status_code != 200:
                    return (
                        False,
                        f"云端心跳返回状态 {response.status_code}",
                        None,
                    )

                response_data = response.json()
                if not response_data.get("success"):
                    return (
                        False,
                        response_data.get("message", "心跳记录失败"),
                        None,
                    )

                # 更新本地设备的最后心跳时间
                await self.device_repository.update_device_status(
                    device_id,
                    device.get("status"),
                    {"last_heartbeat_at": datetime.now()},
                )

                return (
                    True,
                    "心跳发送成功",
                    {
                        "success": True,
                        "message": "心跳记录成功",
                        "device_id": device_id,
                        "online": True,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

        except httpx.TimeoutException:
            logger.error(f"心跳请求超时: {device_id}")
            return (False, "心跳请求超时", None)
        except Exception as e:
            logger.error(f"心跳发送失败: {str(e)}")
            return (False, f"心跳发送失败: {str(e)}", None)

    async def sync_device_status(
        self,
        device_id: str,
    ) -> Tuple[bool, str, Optional[dict]]:
        """
        从云端同步设备状态

        前端定期调用此接口，获取云端最新的审批状态。
        如果云端状态为 approved，则更新本地状态，允许设备进行认证。

        Args:
            device_id: 设备ID

        Returns:
            Tuple[bool, str, Optional[dict]]: (成功标志, 消息, 响应数据)
        """
        try:
            # 查询本地设备
            device = await self.device_repository.find_by_device_id(device_id)
            if not device:
                return (False, f"设备 {device_id} 不存在", None)

            local_status = device.get("status")

            # 向云端查询设备最新状态
            status_url = f"{self.cloud_gateway_base_url}/auth/devices"
            logger.info(f"向云端查询设备状态: {status_url}")

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{status_url}/{device_id}",
                    timeout=10.0,
                )

                if response.status_code == 404:
                    return (False, "设备在云端不存在", None)
                elif response.status_code != 200:
                    logger.warning(f"云端查询失败: HTTP {response.status_code}")
                    return (False, f"云端查询失败: {response.status_code}", None)

                cloud_device = response.json()
                cloud_status = cloud_device.get("status")

            logger.info(f"云端设备状态: {cloud_status}, 本地状态: {local_status}")

            # 如果云端状态更新（特别是已审批），则更新本地
            updated = False
            if cloud_status != local_status:
                await self.device_repository.update_device_status(
                    device_id, cloud_status
                )
                updated = True
                logger.info(f"设备状态已更新: {device_id} -> {cloud_status}")

            return (
                True,
                "状态同步成功",
                {
                    "success": True,
                    "message": "状态同步成功",
                    "device_id": device_id,
                    "status": cloud_status,
                    "updated": updated,
                    "timestamp": datetime.now().isoformat(),
                },
            )

        except httpx.TimeoutException:
            logger.error(f"状态同步超时: {device_id}")
            return (False, "状态同步超时", None)
        except Exception as e:
            logger.error(f"状态同步失败: {str(e)}")
            return (False, f"状态同步失败: {str(e)}", None)
