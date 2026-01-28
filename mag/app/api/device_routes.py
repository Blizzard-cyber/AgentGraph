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
            mac_address=credentials.mac_address,
            ip_address=credentials.ip_address,
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


@router.get("/registration-status")
async def get_registration_status():
    """
    获取设备注册状态

    用于前端页面加载时检查设备当前的注册状态：
    - 未注册：没有本地凭证也没有PSK
    - 等待审批：有PSK但没有凭证（已提交注册申请）
    - 已注册：有本地凭证

    返回:
    - status: 注册状态（unregistered|pending|registered）
    - device_identifier: 设备标识符（如果有）
    - device_id: 设备ID（如果已注册）
    - message: 状态描述
    """
    try:
        from app.core.device_initialization import DeviceInitializer

        # 检查是否有本地凭证
        credentials = DeviceInitializer._load_local_credentials()
        if credentials:
            return {
                "success": True,
                "status": "registered",
                "device_id": credentials.device_id,
                "device_identifier": credentials.device_identifier,
                "device_name": credentials.device_name,
                "device_status": credentials.status.value,
                "mac_address": credentials.mac_address,
                "ip_address": credentials.ip_address,
                "location": credentials.location,
                "message": "设备已注册",
            }

        # 检查是否有PSK（说明已提交注册但未审批）
        psk_data = DeviceInitializer._load_psk()
        if psk_data:
            return {
                "success": True,
                "status": "pending",
                "device_identifier": psk_data.get("device_identifier"),
                "message": "注册申请已提交，等待云端管理员审批",
            }

        # 未注册状态
        return {"success": True, "status": "unregistered", "message": "设备未注册"}

    except Exception as e:
        logger.error(f"获取注册状态失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取注册状态失败: {str(e)}",
        )


@router.post("/check-approval")
async def check_approval_status():
    """
    手动检查设备审批状态

    当设备处于pending状态时，前端可调用此接口检查云端审批状态。
    如果审批通过，将保存凭证到本地。

    返回:
    - success: 是否成功
    - approved: 是否已审批
    - status: 设备状态
    - credentials: 设备凭证（如果已审批）
    - message: 状态消息
    """
    try:
        from app.core.device_initialization import DeviceInitializer

        # 检查审批状态
        approved, message, credentials = await DeviceInitializer.check_approval_status()

        if approved and credentials:
            # 审批通过，保存到数据库
            await DeviceInitializer.on_device_registered(credentials)

            return {
                "success": True,
                "approved": True,
                "status": credentials.status.value,
                "credentials": {
                    "device_id": credentials.device_id,
                    "device_identifier": credentials.device_identifier,
                    "device_name": credentials.device_name,
                    "device_secret": credentials.device_secret,
                    "status": credentials.status.value,
                    "location": credentials.location,
                    "mac_address": credentials.mac_address,
                    "ip_address": credentials.ip_address,
                },
                "message": message,
            }
        else:
            return {"success": True, "approved": False, "message": message}

    except Exception as e:
        logger.error(f"检查审批状态失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检查审批状态失败: {str(e)}",
        )
