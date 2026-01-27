"""
设备初始化和启动检查

在应用启动时：
1. 检查是否有本地保存的设备凭证
2. 从本地文件或环境变量恢复设备ID和密钥
3. 与云端同步设备状态
4. 如果需要，自动触发设备注册
"""

import logging
import os
import json
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

from app.infrastructure.database.mongodb import mongodb_client
from app.models.device_schema import (
    DeviceSelfRegisterRequest,
    DeviceStatus,
    DeviceCredentials,
    DeviceRegistrationMethod,
)

logger = logging.getLogger(__name__)


class DeviceInitializer:
    """设备初始化管理器"""

    # 本地设备凭证文件路径
    CREDENTIALS_DIR = Path.home() / ".mag" / "device"
    CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"

    @classmethod
    def ensure_credentials_dir(cls) -> Path:
        """确保凭证目录存在"""
        cls.CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
        return cls.CREDENTIALS_DIR

    @classmethod
    async def initialize_device(cls) -> Tuple[bool, str, Optional[DeviceCredentials]]:
        """
        初始化设备

        流程：
        1. 检查本地是否有保存的凭证
        2. 如果有，从本地加载并验证
        3. 如果没有，提示需要通过API进行自助注册

        Returns:
            Tuple[bool, str, Optional[DeviceCredentials]]: (成功标志, 消息, 设备凭证)
        """
        try:
            logger.info("开始设备初始化...")

            # 检查本地凭证文件
            credentials = cls._load_local_credentials()
            if credentials:
                logger.info(f"找到本地设备凭证: {credentials.device_id}")

                # 验证凭证是否在数据库中存在
                device = await mongodb_client.device_repository.find_by_device_id(
                    credentials.device_id
                )
                if device:
                    logger.info(f"设备凭证已同步到数据库: {credentials.device_id}")
                    return (True, "设备初始化成功，已加载本地凭证", credentials)
                else:
                    logger.warning(f"本地凭证未在数据库中找到: {credentials.device_id}")
                    # 尝试重新保存到数据库
                    result = await cls._restore_device_to_database(credentials)
                    if result:
                        return (True, "设备凭证已恢复到数据库", credentials)

            # 检查环境变量中是否有设备凭证
            device_id = os.getenv("DEVICE_ID")
            device_secret = os.getenv("DEVICE_SECRET")

            if device_id and device_secret:
                logger.info(f"从环境变量加载设备凭证: {device_id}")
                device = await mongodb_client.device_repository.find_by_device_id(
                    device_id
                )
                if device:
                    credentials = DeviceCredentials(
                        device_id=device["device_id"],
                        device_identifier=device["device_identifier"],
                        device_secret=device_secret,
                        status=DeviceStatus(device["status"]),
                        device_name=device["device_name"],
                        location=device.get("location"),
                        registration_method=DeviceRegistrationMethod(
                            device["registration_method"]
                        ),
                        approved_at=device.get("approved_at"),
                        activated_at=device.get("activated_at"),
                        created_at=device["created_at"],
                        updated_at=device["updated_at"],
                    )
                    # 保存到本地文件
                    cls._save_local_credentials(credentials)
                    return (True, "从环境变量加载设备凭证成功", credentials)

            logger.warning("未找到设备凭证，需要进行自助注册")
            return (False, "设备未注册，请先调用设备自助注册API", None)

        except Exception as e:
            logger.error(f"设备初始化失败: {str(e)}")
            return (False, f"初始化失败: {str(e)}", None)

    @classmethod
    def _load_local_credentials(cls) -> Optional[DeviceCredentials]:
        """
        从本地文件加载设备凭证

        Returns:
            Optional[DeviceCredentials]: 设备凭证或None
        """
        try:
            if not cls.CREDENTIALS_FILE.exists():
                return None

            with open(cls.CREDENTIALS_FILE, "r") as f:
                data = json.load(f)

            credentials = DeviceCredentials(
                device_id=data["device_id"],
                device_identifier=data["device_identifier"],
                device_secret=data["device_secret"],
                status=DeviceStatus(data["status"]),
                device_name=data["device_name"],
                location=data.get("location"),
                registration_method=DeviceRegistrationMethod(
                    data["registration_method"]
                ),
                approved_at=data.get("approved_at"),
                activated_at=data.get("activated_at"),
                created_at=datetime.fromisoformat(data["created_at"]),
                updated_at=datetime.fromisoformat(data["updated_at"]),
                extra_data=data.get("extra_data"),
            )

            logger.info(f"从本地加载设备凭证: {credentials.device_id}")
            return credentials

        except Exception as e:
            logger.warning(f"加载本地凭证失败: {str(e)}")
            return None

    @classmethod
    def _save_local_credentials(cls, credentials: DeviceCredentials) -> bool:
        """
        将设备凭证保存到本地文件

        Args:
            credentials: 设备凭证

        Returns:
            bool: 是否保存成功
        """
        try:
            cls.ensure_credentials_dir()

            data = {
                "device_id": credentials.device_id,
                "device_identifier": credentials.device_identifier,
                "device_secret": credentials.device_secret,
                "status": credentials.status.value,
                "device_name": credentials.device_name,
                "location": credentials.location,
                "registration_method": credentials.registration_method.value,
                "approved_at": (
                    credentials.approved_at.isoformat()
                    if credentials.approved_at
                    else None
                ),
                "activated_at": (
                    credentials.activated_at.isoformat()
                    if credentials.activated_at
                    else None
                ),
                "created_at": credentials.created_at.isoformat(),
                "updated_at": credentials.updated_at.isoformat(),
                "extra_data": credentials.extra_data or {},
            }

            with open(cls.CREDENTIALS_FILE, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"设备凭证已保存到本地: {cls.CREDENTIALS_FILE}")
            return True

        except Exception as e:
            logger.error(f"保存本地凭证失败: {str(e)}")
            return False

    @classmethod
    async def _restore_device_to_database(cls, credentials: DeviceCredentials) -> bool:
        """
        将本地凭证恢复到数据库

        Args:
            credentials: 设备凭证

        Returns:
            bool: 是否恢复成功
        """
        try:
            device = await mongodb_client.device_repository.create_device(
                device_identifier=credentials.device_identifier,
                device_id=credentials.device_id,
                device_secret=credentials.device_secret,
                device_name=credentials.device_name,
                status=credentials.status.value,
                registration_method=credentials.registration_method.value,
                location=credentials.location,
                extra_data=credentials.extra_data,
            )

            logger.info(f"设备凭证已恢复到数据库: {credentials.device_id}")
            return True

        except Exception as e:
            logger.error(f"恢复设备凭证到数据库失败: {str(e)}")
            return False

    @classmethod
    async def on_device_registered(cls, credentials: DeviceCredentials) -> bool:
        """
        设备注册成功后调用

        保存凭证到本地文件和环境变量

        Args:
            credentials: 设备凭证

        Returns:
            bool: 是否保存成功
        """
        try:
            # 保存到本地文件
            cls._save_local_credentials(credentials)

            # 更新环境变量
            os.environ["DEVICE_ID"] = credentials.device_id
            os.environ["DEVICE_SECRET"] = credentials.device_secret

            logger.info(f"设备凭证已保存: {credentials.device_id}")
            return True

        except Exception as e:
            logger.error(f"保存设备凭证失败: {str(e)}")
            return False

    @classmethod
    def get_device_identifier() -> str:
        """
        获取设备标识符

        优先级：
        1. 环境变量 DEVICE_IDENTIFIER
        2. 从本地凭证文件
        3. 从网卡MAC地址（Linux/Mac）
        4. 从UUID

        Returns:
            str: 设备标识符
        """
        # 1. 环境变量
        device_id = os.getenv("DEVICE_IDENTIFIER")
        if device_id:
            return device_id

        # 2. 本地凭证文件
        credentials = DeviceInitializer._load_local_credentials()
        if credentials:
            return credentials.device_identifier

        # 3. 从网卡MAC地址（Linux）
        try:
            import uuid

            mac = uuid.getnode()
            device_id = f"MAC:{mac:012x}".upper()
            return device_id
        except Exception:
            pass

        # 4. UUID（最后的选择）
        import uuid

        return f"UUID:{str(uuid.uuid4())}"
