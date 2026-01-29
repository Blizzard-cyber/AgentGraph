"""
设备注册和认证相关的数据模型和 Schema
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class DeviceStatus(str, Enum):
    """设备状态枚举"""

    PENDING = "pending"  # 待审批
    APPROVED = "approved"  # 已审批
    ACTIVE = "active"  # 已激活
    DISABLED = "disabled"  # 已禁用


class DeviceRegistrationMethod(str, Enum):
    """设备注册方式"""

    SELF = "self"  # 设备自助注册
    MANUAL = "manual"  # 管理员手动注册


# ==================== 请求 Schema ====================


class DeviceSelfRegisterRequest(BaseModel):
    """设备自助注册请求

    用于边缘设备首次启动时向云端注册
    """

    device_identifier: str = Field(
        ..., description="设备标识符（MAC/SN/UUID）", min_length=1
    )
    psk: str = Field(..., description="预共享密钥（Pre-Shared Key）", min_length=32)
    device_name: str = Field(..., description="设备名称", min_length=1, max_length=255)
    location: Optional[str] = Field(None, description="设备位置", max_length=255)
    extra_data: Optional[dict] = Field(None, description="额外的设备信息")


class DeviceAuthRequest(BaseModel):
    """设备认证请求

    设备使用 deviceId + deviceSecret 换取 JWT Token
    """

    device_id: str = Field(..., description="设备ID")
    device_secret: str = Field(..., description="设备密钥")
    grant_type: str = Field(default="client_credentials", description="授权类型")


class DeviceStatusCheckRequest(BaseModel):
    """设备状态检查请求"""

    device_id: str = Field(..., description="设备ID")
    device_identifier: Optional[str] = Field(
        None, description="设备标识符（可选，用于查询未注册的设备）"
    )


# ==================== 响应 Schema ====================


class DeviceInfo(BaseModel):
    """设备信息（不包含敏感数据）"""

    device_id: str
    device_identifier: str
    device_name: str
    status: DeviceStatus
    location: Optional[str] = None
    mac_address: Optional[str] = None
    ip_address: Optional[str] = None
    registration_method: DeviceRegistrationMethod
    approved_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeviceRegistrationResponse(BaseModel):
    """设备注册响应"""

    success: bool
    message: str
    device: DeviceInfo
    device_secret: Optional[str] = Field(
        None, description="一次性设备密钥（仅首次返回）"
    )


class DeviceAuthResponse(BaseModel):
    """设备认证响应"""

    success: bool
    access_token: str = Field(..., description="JWT Access Token")
    token_type: str = Field(default="Bearer")
    expires_in: int = Field(..., description="Token过期时间（秒）")
    device_info: DeviceInfo


class DeviceStatusResponse(BaseModel):
    """设备状态响应"""

    device_id: str
    device_identifier: str
    device_name: str
    status: DeviceStatus
    location: Optional[str] = None
    registration_method: DeviceRegistrationMethod
    created_at: datetime
    approved_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None
    message: str


class DeviceCredentialsResponse(BaseModel):
    """设备凭证保存的本地响应

    边缘系统启动后保存的凭证信息
    """

    device_id: str
    device_secret: str
    status: DeviceStatus
    created_at: datetime


# ==================== 内部数据模型 ====================


class DeviceCredentials(BaseModel):
    """设备凭证（用于本地存储和管理）"""

    device_id: str
    device_identifier: str
    device_secret: str
    status: DeviceStatus = DeviceStatus.PENDING
    device_name: str
    location: Optional[str] = None
    mac_address: Optional[str] = None
    ip_address: Optional[str] = None
    registration_method: DeviceRegistrationMethod
    approved_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    extra_data: Optional[dict] = None

    class Config:
        from_attributes = True
