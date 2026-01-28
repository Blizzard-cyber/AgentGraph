"""
设备认证API路由

处理设备自助注册、认证、状态查询等API端点
"""

import logging
import socket
import uuid
from uuid import getnode as get_mac
from fastapi import APIRouter, HTTPException, status, Depends

from app.models.device_schema import (
    DeviceSelfRegisterRequest,
    DeviceAuthRequest,
    DeviceStatusCheckRequest,
    DeviceRegistrationResponse,
    DeviceAuthResponse,
    DeviceStatusResponse,
    DeviceInfo,
)
from app.services.device.device_service import DeviceService
from app.infrastructure.database.mongodb import mongodb_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/device", tags=["Device Registration & Auth"])


def get_device_service() -> DeviceService:
    """获取设备服务实例"""
    if not mongodb_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库服务未就绪"
        )

    return DeviceService(device_repository=mongodb_client.device_repository)


@router.post("/self-register", response_model=DeviceRegistrationResponse)
async def self_register_device(
    request: DeviceSelfRegisterRequest,
    device_service: DeviceService = Depends(get_device_service),
):
    """
    设备自助注册

    边缘设备首次启动时调用此接口向云端注册。

    工作流程：
    1. 验证设备标识符和PSK
    2. 向云端认证服务发送注册请求
    3. 保存返回的设备凭证到本地数据库
    4. 返回设备ID和临时密钥

    请求体:
    - device_identifier: 设备标识符（MAC/SN/UUID）
    - psk: 预共享密钥（工厂预置）
    - device_name: 设备名称
    - location: 设备位置（可选）

    返回:
    - success: 是否成功
    - message: 操作消息
    - device: 设备信息
    - device_secret: 设备密钥（仅首次返回）

    状态码:
    - 200: 注册成功或注册重复
    - 400: 请求参数错误
    - 503: 服务不可用
    """
    try:
        logger.info(f"设备自助注册请求: {request.device_identifier}")

        success, message, credentials = await device_service.self_register_device(
            request
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        # 构建响应
        device_info = DeviceInfo(
            device_id=credentials.device_id,
            device_identifier=credentials.device_identifier,
            device_name=credentials.device_name,
            status=credentials.status,
            location=credentials.location,
            registration_method=credentials.registration_method,
            approved_at=credentials.approved_at,
            activated_at=credentials.activated_at,
            created_at=credentials.created_at,
            updated_at=credentials.updated_at,
        )

        return DeviceRegistrationResponse(
            success=True,
            message=message,
            device=device_info,
            device_secret=credentials.device_secret,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设备注册处理错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注册失败: {str(e)}",
        )


@router.post("/authenticate", response_model=DeviceAuthResponse)
async def authenticate_device(
    request: DeviceAuthRequest,
    device_service: DeviceService = Depends(get_device_service),
):
    """
    设备认证

    设备使用本地保存的凭证（deviceId + deviceSecret）向云端进行认证，
    获取JWT访问令牌。

    工作流程：
    1. 验证本地设备凭证
    2. 向云端认证服务发送认证请求
    3. 获取JWT Token
    4. 更新设备状态为激活（如果还不是）

    请求体:
    - device_id: 设备ID
    - device_secret: 设备密钥
    - grant_type: 授权类型（默认client_credentials）

    返回:
    - success: 是否成功
    - access_token: JWT访问令牌
    - token_type: 令牌类型（Bearer）
    - expires_in: 令牌过期时间（秒）
    - device_info: 设备信息

    状态码:
    - 200: 认证成功
    - 400: 设备不存在或凭证错误
    - 503: 服务不可用
    """
    try:
        logger.info(f"设备认证请求: {request.device_id}")

        success, message, auth_response = await device_service.authenticate_device(
            request.device_id, request.device_secret
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        return auth_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设备认证处理错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"认证失败: {str(e)}",
        )


@router.post("/sync-status")
async def sync_device_status(
    request_body: dict,
    device_service: DeviceService = Depends(get_device_service),
):
    """
    同步设备状态（从云端获取最新审批状态）

    前端定期调用此接口查询设备在云端的最新审批状态。
    如果设备已被审批，将更新本地数据库的状态。

    请求体:
    - device_id: 设备ID

    返回:
    - success: 是否成功
    - status: 设备当前状态（pending|approved|active|disabled）
    - message: 状态消息
    - updated: 是否从云端更新了状态

    状态码:
    - 200: 查询成功
    - 404: 设备不存在
    - 503: 服务不可用
    """
    try:
        device_id = request_body.get("device_id")
        if not device_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少必填字段: device_id",
            )

        logger.info(f"同步设备状态: {device_id}")

        success, message, response = await device_service.sync_device_status(device_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=message
            )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"同步设备状态错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"同步失败: {str(e)}",
        )


@router.post("/status", response_model=DeviceStatusResponse)
async def check_device_status(
    request: DeviceStatusCheckRequest,
    device_service: DeviceService = Depends(get_device_service),
):
    """
    查询设备状态

    获取设备当前的注册和认证状态。

    请求体:
    - device_id: 设备ID
    - device_identifier: 设备标识符（可选，用于首次查询）

    返回:
    - device_id: 设备ID
    - device_identifier: 设备标识符
    - device_name: 设备名称
    - status: 设备状态（pending|approved|active|disabled）
    - location: 设备位置
    - registration_method: 注册方式
    - created_at: 创建时间
    - approved_at: 审批时间
    - activated_at: 激活时间
    - message: 状态消息

    状态码:
    - 200: 查询成功
    - 404: 设备不存在
    - 503: 服务不可用
    """
    try:
        logger.info(f"设备状态查询: {request.device_id}")

        success, message, status_response = await device_service.get_device_status(
            request.device_id
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)

        return status_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设备状态查询错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询失败: {str(e)}",
        )


@router.get("/health")
async def device_service_health():
    """
    设备服务健康检查

    返回:
    - status: 服务状态
    - database_connected: 数据库连接状态
    """
    return {
        "status": "ok",
        "service": "device-auth-service",
        "database_connected": mongodb_client.is_connected,
    }


@router.get("/system-info")
async def get_system_info():
    """
    获取本机系统信息用于设备注册表单默认值

    返回:
    - hostname: 本机主机名
    - mac_address: 本机MAC地址
    - device_id_suggestion: 建议的设备标识符 (MAC地址的格式化版本)
    """
    try:
        # 获取主机名
        hostname = socket.gethostname()

        # 获取MAC地址
        mac_int = get_mac()
        mac_address = ":".join(("%012x" % mac_int)[i : i + 2] for i in range(0, 12, 2))

        # 生成建议的设备标识符
        device_id_suggestion = f"MAC-{mac_address}"

        return {
            "success": True,
            "hostname": hostname,
            "mac_address": mac_address,
            "device_id_suggestion": device_id_suggestion,
            "default_location": "Chengdu",
        }
    except Exception as e:
        logger.error(f"获取系统信息失败: {str(e)}")
        # 返回默认值，即使出错也能继续注册
        return {
            "success": False,
            "hostname": "Unknown",
            "mac_address": "00:00:00:00:00:00",
            "device_id_suggestion": f"UUID-{str(uuid.uuid4())}",
            "default_location": "Chengdu",
        }


@router.post("/heartbeat")
async def device_heartbeat(
    request_body: dict,
    device_service: DeviceService = Depends(get_device_service),
):
    """
    设备心跳接口

    边缘设备定时调用此接口，向云端发送心跳以维持连接状态。

    请求体:
    - device_id: 设备ID

    返回:
    - success: 是否成功
    - message: 操作消息
    - online: 是否在线

    状态码:
    - 200: 心跳记录成功
    - 400: 请求参数错误
    - 404: 设备不存在
    - 503: 服务不可用
    """
    try:
        device_id = request_body.get("device_id")
        if not device_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少必填字段: device_id",
            )

        logger.info(f"设备心跳: {device_id}")

        success, message, response = await device_service.send_heartbeat(device_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=message
            )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设备心跳错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"心跳发送失败: {str(e)}",
        )
