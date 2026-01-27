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
        1. 生成本地设备ID和密钥
        2. 调用云端API进行注册
        3. 保存返回的凭证到本地

        Args:
            request: 设备自助注册请求

        Returns:
            Tuple[bool, str, Optional[DeviceCredentials]]: (成功标志, 消息, 设备凭证)
        """
        try:
            # 检查本地是否已注册
            existing_device = await self.device_repository.find_by_device_identifier(
                request.device_identifier
            )
            if existing_device:
                return (
                    False,
                    f"设备标识符 {request.device_identifier} 已注册",
                    None,
                )

            # 生成设备ID和密钥
            device_id = self.generate_device_id()
            device_secret = self.generate_device_secret()

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

            # 保存本地设备凭证（使用驼峰字段）
            credentials = await self.device_repository.create_device(
                device_identifier=request.device_identifier,
                device_id=cloud_device.get("deviceId", device_id),
                device_secret=cloud_device_secret or device_secret,
                device_name=request.device_name,
                status=cloud_device.get("status", "pending"),
                registration_method=cloud_device.get("registrationMethod", "self"),
                location=request.location,
                extra_data=request.extra_data,
            )

            device_credentials = DeviceCredentials(
                device_id=credentials["device_id"],
                device_identifier=request.device_identifier,
                device_secret=cloud_device_secret or device_secret,
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
                return (
                    False,
                    f"设备 {device_id} 不存在",
                    None,
                )

            # 验证设备密钥
            if device["device_secret_hash"] != device_secret:
                logger.warning(f"设备密钥验证失败: {device_id}")
                return (False, "设备密钥验证失败", None)

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

            # 调用云端认证服务获取Token（使用驼峰格式）
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "deviceId": device_id,
                    "deviceSecret": device_secret,
                    "grantType": "client_credentials",
                }

                response = await client.post(
                    f"{self.cloud_gateway_base_url}/auth/devices/token",
                    json=payload,
                )

            if response.status_code != 200:
                logger.warning(f"云端认证失败: {response.status_code}")
                return (
                    False,
                    f"云端认证失败: {response.status_code}",
                    None,
                )

            cloud_response = response.json()
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
