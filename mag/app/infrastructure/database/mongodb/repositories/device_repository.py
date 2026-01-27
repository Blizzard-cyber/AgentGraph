"""
设备数据仓库

负责设备数据的CRUD操作和认证凭证管理
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from bson import ObjectId

logger = logging.getLogger(__name__)


class DeviceRepository:
    """设备Repository - 负责devices集合的操作"""

    def __init__(self, db, devices_collection):
        """初始化设备Repository

        Args:
            db: MongoDB数据库实例
            devices_collection: devices集合
        """
        self.db = db
        self.collection = devices_collection

    async def create_device(
        self,
        device_identifier: str,
        device_id: str,
        device_secret: str,
        device_name: str,
        status: str = "pending",
        registration_method: str = "self",
        location: Optional[str] = None,
        extra_data: Optional[dict] = None,
    ) -> dict:
        """
        创建设备记录

        Args:
            device_identifier: 设备标识符（MAC/SN/UUID）
            device_id: 设备ID
            device_secret: 设备密钥（加密存储）
            device_name: 设备名称
            status: 设备状态 (pending|approved|active|disabled)
            registration_method: 注册方式 (self|manual)
            location: 设备位置
            extra_data: 额外的设备信息

        Returns:
            dict: 创建的设备文档

        Raises:
            Exception: 设备已存在或创建失败
        """
        try:
            now = datetime.now()

            # 检查设备是否已存在
            existing = await self.find_by_device_id(device_id)
            if existing:
                raise ValueError(f"设备ID {device_id} 已存在")

            existing_identifier = await self.find_by_device_identifier(
                device_identifier
            )
            if existing_identifier:
                raise ValueError(f"设备标识符 {device_identifier} 已存在")

            device_doc = {
                "device_id": device_id,
                "device_identifier": device_identifier,
                "device_name": device_name,
                "device_secret_hash": device_secret,  # 实际应该哈希存储
                "status": status,
                "registration_method": registration_method,
                "location": location,
                "extra_data": extra_data or {},
                "approved_at": None,
                "activated_at": None,
                "last_auth_at": None,
                "created_at": now,
                "updated_at": now,
            }

            result = await self.collection.insert_one(device_doc)
            device_doc["_id"] = result.inserted_id

            logger.info(f"设备创建成功: {device_id}")
            return device_doc

        except Exception as e:
            logger.error(f"创建设备失败: {str(e)}")
            raise

    async def find_by_device_id(self, device_id: str) -> Optional[dict]:
        """通过设备ID查询设备"""
        try:
            device = await self.collection.find_one({"device_id": device_id})
            return device
        except Exception as e:
            logger.error(f"查询设备失败: {str(e)}")
            return None

    async def find_by_device_identifier(self, device_identifier: str) -> Optional[dict]:
        """通过设备标识符查询设备"""
        try:
            device = await self.collection.find_one(
                {"device_identifier": device_identifier}
            )
            return device
        except Exception as e:
            logger.error(f"查询设备标识符失败: {str(e)}")
            return None

    async def update_device_status(
        self, device_id: str, status: str, extra_updates: Optional[dict] = None
    ) -> Optional[dict]:
        """
        更新设备状态

        Args:
            device_id: 设备ID
            status: 新状态
            extra_updates: 额外的更新字段

        Returns:
            dict: 更新后的设备文档
        """
        try:
            now = datetime.now()
            updates = {"status": status, "updated_at": now}

            # 根据状态更新时间戳
            if status == "approved":
                updates["approved_at"] = now
            elif status == "active":
                updates["activated_at"] = now

            # 合并额外的更新
            if extra_updates:
                updates.update(extra_updates)

            device = await self.collection.find_one_and_update(
                {"device_id": device_id}, {"$set": updates}, return_document=True
            )

            if device:
                logger.info(f"设备状态更新成功: {device_id} -> {status}")
            return device

        except Exception as e:
            logger.error(f"更新设备状态失败: {str(e)}")
            raise

    async def update_last_auth(self, device_id: str) -> Optional[dict]:
        """更新设备最后认证时间"""
        try:
            device = await self.collection.find_one_and_update(
                {"device_id": device_id},
                {"$set": {"last_auth_at": datetime.now()}},
                return_document=True,
            )
            return device
        except Exception as e:
            logger.error(f"更新最后认证时间失败: {str(e)}")
            raise

    async def get_device_info(self, device_id: str) -> Optional[dict]:
        """获取设备信息（不包含密钥）"""
        try:
            device = await self.find_by_device_id(device_id)
            if device:
                # 移除敏感信息
                device.pop("device_secret_hash", None)
            return device
        except Exception as e:
            logger.error(f"获取设备信息失败: {str(e)}")
            return None

    async def verify_device_secret(self, device_id: str, device_secret: str) -> bool:
        """验证设备密钥"""
        try:
            device = await self.find_by_device_id(device_id)
            if not device:
                return False

            # 实际应该使用密钥比对函数
            stored_secret = device.get("device_secret_hash", "")
            return stored_secret == device_secret

        except Exception as e:
            logger.error(f"验证设备密钥失败: {str(e)}")
            return False

    async def list_devices(
        self,
        status: Optional[str] = None,
        registration_method: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple:
        """
        列表查询设备

        Args:
            status: 设备状态过滤
            registration_method: 注册方式过滤
            skip: 分页跳过数
            limit: 分页限制数

        Returns:
            tuple: (总数, 设备列表)
        """
        try:
            filter_query = {}

            if status:
                filter_query["status"] = status

            if registration_method:
                filter_query["registration_method"] = registration_method

            total = await self.collection.count_documents(filter_query)

            cursor = self.collection.find(filter_query).skip(skip).limit(limit)
            devices = await cursor.to_list(length=limit)

            return total, devices

        except Exception as e:
            logger.error(f"列表查询设备失败: {str(e)}")
            raise

    async def delete_device(self, device_id: str) -> bool:
        """删除设备"""
        try:
            result = await self.collection.delete_one({"device_id": device_id})
            if result.deleted_count > 0:
                logger.info(f"设备删除成功: {device_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"删除设备失败: {str(e)}")
            raise

    async def count_by_identifier(self, device_identifier: str) -> int:
        """统计具有相同标识符的设备数量"""
        try:
            count = await self.collection.count_documents(
                {"device_identifier": device_identifier}
            )
            return count
        except Exception as e:
            logger.error(f"统计设备失败: {str(e)}")
            return 0
