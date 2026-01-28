"""
设备初始化和启动检查

在应用启动时：
1. 检查是否有本地保存的设备凭证
2. 如果没有，获取设备硬件标识符（MAC地址），生成PSK并向云端注册
3. 轮询检查云端审批状态
4. 审批通过后，获取并保存云端下发的凭证
5. 完成设备认证
"""

import logging
import os
import json
import secrets
import base64
import asyncio
import socket
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
import uuid
import httpx

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

    # 本地设备凭证文件路径（在项目根目录下的.mag文件夹）
    # 当前文件: mcp-agent-graph/mag/app/core/device_initialization.py
    # 项目根目录: mcp-agent-graph/
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    CREDENTIALS_DIR = PROJECT_ROOT / ".mag" / "device"
    CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"
    PSK_FILE = CREDENTIALS_DIR / "psk.json"

    # 云端API地址
    CLOUD_AUTH_URL = os.getenv("CLOUD_AUTH_URL", "http://192.168.1.90:8088/auth")

    @classmethod
    def ensure_credentials_dir(cls) -> Path:
        """确保凭证目录存在"""
        logger.info(f"CLOUD_AUTH_URL配置: {cls.CLOUD_AUTH_URL}")
        cls.CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
        return cls.CREDENTIALS_DIR

    @classmethod
    def get_hardware_identifier(cls) -> str:
        """
        获取设备硬件标识符（不可伪造）

        优先级：
        1. 环境变量 DEVICE_IDENTIFIER（用于开发测试）
        2. 网卡MAC地址（Linux/Mac）
        3. /etc/machine-id（Linux systemd）
        4. UUID（最后选择，不推荐）

        Returns:
            str: 设备硬件标识符
        """
        # 1. 环境变量（仅用于开发测试）
        device_id = os.getenv("DEVICE_IDENTIFIER")
        if device_id:
            logger.warning(f"使用环境变量中的设备标识符: {device_id}")
            return device_id

        # 2. MAC地址（推荐）
        try:
            mac = uuid.getnode()
            mac_hex = f"{mac:012x}"
            # 格式化为标准MAC地址格式
            mac_address = ":".join([mac_hex[i : i + 2] for i in range(0, 12, 2)])
            logger.info(f"使用MAC地址作为设备标识符: {mac_address}")
            return mac_address
        except Exception as e:
            logger.warning(f"获取MAC地址失败: {e}")

        # 3. machine-id（Linux systemd）
        try:
            machine_id_path = Path("/etc/machine-id")
            if machine_id_path.exists():
                machine_id = machine_id_path.read_text().strip()
                logger.info(f"使用machine-id作为设备标识符: {machine_id[:16]}...")
                return f"machine-{machine_id}"
        except Exception as e:
            logger.warning(f"读取machine-id失败: {e}")

        # 4. UUID（最后选择）
        device_uuid = str(uuid.uuid4())
        logger.warning(f"使用UUID作为设备标识符（不推荐）: {device_uuid}")
        return f"uuid-{device_uuid}"

    @classmethod
    def _get_ip_address(cls) -> str:
        """
        获取设备的IP地址

        Returns:
            str: IP地址
        """
        try:
            # 创建一个UDP socket连接到外部地址（不会真正发送数据）
            # 这样可以获取本机的出口IP地址
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
            return ip_address
        except Exception as e:
            logger.warning(f"获取IP地址失败: {e}")
            try:
                # 备用方案：获取hostname对应的IP
                return socket.gethostbyname(socket.gethostname())
            except Exception as e2:
                logger.error(f"获取IP地址备用方案也失败: {e2}")
                return "0.0.0.0"

    @classmethod
    def generate_psk(cls) -> str:
        """
        生成设备预共享密钥（PSK）

        PSK与设备硬件标识符绑定，用于向云端证明设备身份
        格式：psk_ + base64编码的随机字节

        Returns:
            str: PSK字符串（格式：psk_xxxxx，至少32字符）
        """
        # 生成256位（32字节）的随机密钥
        psk_bytes = secrets.token_bytes(32)
        # Base64编码（43字符）
        psk_encoded = base64.urlsafe_b64encode(psk_bytes).decode("utf-8").rstrip("=")
        # 添加psk_前缀以符合云端验证规则
        psk = f"psk_{psk_encoded}"
        return psk

    @classmethod
    async def auto_register_device(cls) -> Tuple[bool, str, Optional[dict]]:
        """
        自动注册设备到云端

        流程：
        1. 获取设备硬件标识符（MAC地址等）
        2. 生成PSK并保存到本地
        3. 向云端发送注册请求（携带设备标识符 + PSK）
        4. 云端验证并等待管理员审批
        5. 轮询检查审批状态
        6. 审批通过后获取云端下发的凭证

        Returns:
            Tuple[bool, str, Optional[dict]]: (成功标志, 消息, 注册信息)
        """
        try:
            # 1. 获取设备硬件标识符
            device_identifier = cls.get_hardware_identifier()
            logger.info(f"设备标识符: {device_identifier}")

            # 2. 生成PSK
            psk = cls.generate_psk()
            logger.info(f"已生成PSK: {psk[:10]}...")

            # 保存PSK到本地（用于后续轮询验证）
            cls._save_psk(device_identifier, psk)

            # 3. 获取设备信息
            # 设备名称使用hostname
            device_name = os.getenv("DEVICE_NAME", socket.gethostname())

            # 默认位置为NDSL机房
            location = os.getenv("DEVICE_LOCATION", "NDSL机房")

            # 获取IP地址
            ip_address = cls._get_ip_address()

            # MAC地址（从device_identifier提取）
            mac_address = device_identifier

            logger.info(f"设备名称: {device_name}")
            logger.info(f"设备位置: {location}")
            logger.info(f"MAC地址: {mac_address}")
            logger.info(f"IP地址: {ip_address}")

            # 4. 向云端发送注册请求
            registration_data = {
                "device_identifier": device_identifier,
                "psk": psk,
                "device_name": device_name,
                "location": location,
                "mac_address": mac_address,
                "ip_address": ip_address,
                "hardware_info": cls._get_hardware_info(),
            }

            register_url = f"{cls.CLOUD_AUTH_URL}/devices/self-register"
            logger.info(f"向云端注册，URL: {register_url}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    register_url,
                    json=registration_data,
                )

                if response.status_code == 201:
                    result = response.json()
                    logger.info(f"设备注册成功: {result}")

                    # 首次注册时不保存凭证文件（pending状态），只将device_secret添加到PSK文件中
                    # 这样可以在审批后使用原始密钥
                    if result.get("device") and result["device"].get("device_secret"):
                        device_data = result["device"]
                        # 更新PSK文件，添加device_secret和device_id
                        psk_data = cls._load_psk()
                        if psk_data:
                            # 直接使用device_data中的值来保存
                            cls._save_psk(
                                psk_data["device_identifier"],
                                psk_data["psk"],
                                device_data["device_name"],
                                device_data["device_secret"],
                                device_data["device_id"],
                            )
                            logger.info(
                                f"已将device_secret保存到PSK文件中: {device_data['device_secret'][:20]}..."
                            )

                    logger.info("设备注册请求已提交，等待管理员审批")
                    return (True, "设备注册请求已提交，等待管理员审批", result)
                elif response.status_code == 409:
                    # 设备已存在，可能之前注册过
                    logger.info("设备已注册，检查审批状态...")
                    return (True, "设备已注册，检查审批状态", None)
                else:
                    error_msg = response.json().get("message", "未知错误")
                    logger.error(f"设备注册失败: {error_msg}")
                    return (False, f"注册失败: {error_msg}", None)

        except Exception as e:
            logger.error(f"自动注册设备失败: {str(e)}")
            return (False, f"注册失败: {str(e)}", None)

    @classmethod
    async def check_approval_status(
        cls,
    ) -> Tuple[bool, str, Optional[DeviceCredentials]]:
        """
        检查设备审批状态并获取凭证

        Returns:
            Tuple[bool, str, Optional[DeviceCredentials]]: (是否已审批, 消息, 凭证)
        """
        try:
            # 读取本地保存的PSK
            psk_data = cls._load_psk()
            if not psk_data:
                return (False, "未找到本地PSK，请先注册", None)

            device_identifier = psk_data["device_identifier"]
            psk = psk_data["psk"]

            # 向云端查询审批状态（通过尝试获取设备信息）
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 获取设备名称（使用hostname）
                device_name = os.getenv("DEVICE_NAME", socket.gethostname())

                # 获取IP地址
                ip_address = cls._get_ip_address()

                # MAC地址
                mac_address = device_identifier

                # 使用self-register接口检查状态（如果已审批会返回凭证）
                response = await client.post(
                    f"{cls.CLOUD_AUTH_URL}/devices/self-register",
                    json={
                        "device_identifier": device_identifier,
                        "psk": psk,
                        "device_name": device_name,
                        "mac_address": mac_address,
                        "ip_address": ip_address,
                    },
                )

                if response.status_code == 200:
                    result = response.json()

                    logger.info(f"云端响应状态码: {response.status_code}")
                    logger.info(f"云端响应数据: {result}")

                    # 检查是否有device字段（审批通过后会返回）
                    if result.get("success") and result.get("device"):
                        device_data = result["device"]

                        logger.info(f"设备数据: {device_data}")
                        logger.info(f"设备状态: {device_data.get('status')}")

                        # 检查状态是否为approved或active
                        if device_data.get("status") in ["approved", "active"]:
                            # 审批通过，从PSK文件读取device_secret
                            psk_data = cls._load_psk()

                            if not psk_data:
                                logger.error("未找到PSK文件，无法完成审批流程")
                                return (False, "PSK文件丢失，请重新注册", None)

                            device_secret = psk_data.get("device_secret")
                            if not device_secret:
                                logger.error("PSK文件中缺少device_secret")
                                return (False, "PSK文件不完整，请重新注册", None)

                            # 创建凭证（使用PSK文件中保存的明文密钥）
                            credentials = DeviceCredentials(
                                device_id=device_data["device_id"],
                                device_identifier=device_data["device_identifier"],
                                device_secret=device_secret,  # 使用PSK文件中保存的明文密钥
                                status=DeviceStatus(device_data["status"]),
                                device_name=device_data["device_name"],
                                location=device_data.get("location"),
                                mac_address=device_data.get("mac_address")
                                or device_data.get("macAddress"),
                                ip_address=device_data.get("ip_address")
                                or device_data.get("ipAddress"),
                                registration_method=DeviceRegistrationMethod(
                                    device_data.get("registration_method", "auto")
                                ),
                                approved_at=(
                                    datetime.fromisoformat(device_data["approved_at"])
                                    if device_data.get("approved_at")
                                    else None
                                ),
                                created_at=(
                                    datetime.fromisoformat(device_data["created_at"])
                                    if device_data.get("created_at")
                                    else datetime.now()
                                ),
                                updated_at=(
                                    datetime.fromisoformat(device_data["updated_at"])
                                    if device_data.get("updated_at")
                                    else datetime.now()
                                ),
                            )

                            # 保存完整凭证文件
                            cls._save_local_credentials(credentials)

                            # 删除PSK文件（已完成注册）
                            cls._delete_psk()

                            logger.info(
                                f"设备审批通过，凭证已保存，状态: {credentials.status.value}"
                            )
                            logger.info(
                                f"使用的device_secret: {credentials.device_secret[:20]}..."
                            )
                            return (True, "设备审批通过", credentials)
                        else:
                            # 仍在pending状态
                            status = device_data.get("status", "pending")
                            logger.info(f"设备审批状态: {status}")
                            return (False, f"设备状态: {status}，等待审批", None)
                    else:
                        # 返回成功但没有device信息，说明还在pending
                        message = result.get("message", "等待审批")
                        logger.info(f"设备状态: {message}")
                        return (False, message, None)
                elif response.status_code == 403:
                    error_msg = response.json().get("message", "PSK验证失败")
                    logger.error(f"PSK验证失败: {error_msg}")
                    return (False, f"验证失败: {error_msg}", None)
                else:
                    try:
                        error_msg = response.json().get("message", "未知错误")
                    except:
                        error_msg = f"HTTP {response.status_code}"
                    logger.error(f"检查审批状态失败: {error_msg}")
                    return (False, f"检查失败: {error_msg}", None)

        except Exception as e:
            logger.error(f"检查审批状态失败: {str(e)}")
            return (False, f"检查失败: {str(e)}", None)

    @classmethod
    def _get_hardware_info(cls) -> dict:
        """获取设备硬件信息"""
        import platform

        return {
            "system": platform.system(),
            "node": platform.node(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        }

    @classmethod
    def _save_psk(
        cls,
        device_identifier: str,
        psk: str,
        device_name: Optional[str] = None,
        device_secret: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> bool:
        """保存PSK到本地文件"""
        try:
            cls.ensure_credentials_dir()

            data = {
                "device_identifier": device_identifier,
                "psk": psk,
                "created_at": datetime.now().isoformat(),
            }

            # 如果提供了device_secret，说明已注册成功，保存以便审批后使用
            if device_secret:
                data["device_secret"] = device_secret
            if device_id:
                data["device_id"] = device_id
            if device_name:
                data["device_name"] = device_name

            with open(cls.PSK_FILE, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"PSK已保存到本地: {cls.PSK_FILE}")
            return True
        except Exception as e:
            logger.error(f"保存PSK失败: {str(e)}")
            return False

    @classmethod
    def _load_psk(cls) -> Optional[dict]:
        """从本地文件加载PSK"""
        try:
            if not cls.PSK_FILE.exists():
                return None

            with open(cls.PSK_FILE, "r") as f:
                data = json.load(f)

            return data
        except Exception as e:
            logger.warning(f"加载PSK失败: {str(e)}")
            return None

    @classmethod
    def _delete_psk(cls) -> bool:
        """删除PSK文件（注册完成后）"""
        try:
            if cls.PSK_FILE.exists():
                cls.PSK_FILE.unlink()
                logger.info("PSK文件已删除")
            return True
        except Exception as e:
            logger.error(f"删除PSK文件失败: {str(e)}")
            return False

    @classmethod
    async def initialize_device(cls) -> Tuple[bool, str, Optional[DeviceCredentials]]:
        """
        初始化设备

        流程：
        1. 检查本地是否有保存的凭证
        2. 如果有凭证，直接使用
        3. 如果没有凭证但有PSK，检查审批状态
        4. 如果都没有，自动注册并等待审批

        Returns:
            Tuple[bool, str, Optional[DeviceCredentials]]: (成功标志, 消息, 设备凭证)
        """
        try:
            logger.info("开始设备初始化...")

            # 1. 检查本地凭证文件
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
                    logger.warning(f"本地凭证未在数据库中找到，尝试恢复...")
                    result = await cls._restore_device_to_database(credentials)
                    if result:
                        return (True, "设备凭证已恢复到数据库", credentials)

            # 2. 检查是否有PSK（说明已注册但未审批）
            psk_data = cls._load_psk()
            if psk_data:
                logger.info("发现待审批的注册请求，检查审批状态...")
                approved, message, credentials = await cls.check_approval_status()
                if approved and credentials:
                    # 审批通过，保存到数据库
                    await cls.on_device_registered(credentials)
                    return (True, message, credentials)
                else:
                    # 仍在等待审批
                    return (False, message, None)

            # 3. 没有凭证也没有PSK，执行自动注册
            logger.info("设备未注册，开始自动注册流程...")
            success, message, result = await cls.auto_register_device()

            if success:
                # 注册请求已提交，等待审批
                logger.info("设备注册请求已提交，启动审批状态轮询...")
                return (False, message, None)
            else:
                return (False, message, None)

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
                mac_address=data.get("mac_address"),
                ip_address=data.get("ip_address"),
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
                "mac_address": credentials.mac_address,
                "ip_address": credentials.ip_address,
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

        保存凭证到本地文件、数据库和环境变量

        Args:
            credentials: 设备凭证

        Returns:
            bool: 是否保存成功
        """
        try:
            # 保存到本地文件
            cls._save_local_credentials(credentials)

            # 保存到数据库
            await cls._restore_device_to_database(credentials)

            # 更新环境变量
            os.environ["DEVICE_ID"] = credentials.device_id
            os.environ["DEVICE_SECRET"] = credentials.device_secret

            logger.info(f"设备凭证已保存: {credentials.device_id}")
            return True

        except Exception as e:
            logger.error(f"保存设备凭证失败: {str(e)}")
            return False

    @classmethod
    async def start_approval_polling(cls, interval: int = 30, max_attempts: int = 120):
        """
        启动审批状态轮询

        Args:
            interval: 轮询间隔（秒）
            max_attempts: 最大轮询次数
        """
        logger.info(f"启动审批状态轮询（间隔{interval}秒，最多{max_attempts}次）...")

        for attempt in range(max_attempts):
            try:
                approved, message, credentials = await cls.check_approval_status()

                if approved and credentials:
                    logger.info("设备审批通过！")
                    await cls.on_device_registered(credentials)
                    return credentials

                logger.info(f"[{attempt+1}/{max_attempts}] {message}")
                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"轮询出错: {str(e)}")
                await asyncio.sleep(interval)

        logger.warning("审批轮询超时，请检查云端审批状态")
        return None
