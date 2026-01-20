"""
FastAPI认证依赖注入模块

提供用于路由保护的依赖函数

支持两种认证模式：
1. 应用层JWT验证（传统模式）
2. 网关层验证 + 请求头传递（Higress模式）
"""

from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.auth.jwt import verify_token
from app.models.auth_schema import CurrentUser


# 定义HTTPBearer认证scheme
# 使用HTTPBearer
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    """
    从JWT Token中获取当前用户信息

    这是一个FastAPI依赖函数，用于保护需要认证的路由。
    它从Authorization header中提取Bearer token，验证后返回当前用户信息。

    Args:
        credentials: HTTPBearer自动从请求头中提取的认证凭证

    Returns:
        CurrentUser: 当前登录用户的信息

    Raises:
        HTTPException: 当token无效、过期或格式错误时抛出401错误

    Usage:
        @router.get("/protected")
        async def protected_route(current_user: CurrentUser = Depends(get_current_user)):
            return {"user_id": current_user.user_id, "role": current_user.role}
    """
    # 提取token（credentials.credentials就是Bearer后面的token字符串）
    token = credentials.credentials

    # 验证token并获取payload
    payload = verify_token(token)

    # 构造CurrentUser对象
    current_user = CurrentUser(user_id=payload["sub"], role=payload["role"])

    return current_user


async def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    要求管理员权限的依赖

    验证当前用户是否为管理员（admin或super_admin）

    Args:
        current_user: 当前用户信息（由get_current_user依赖提供）

    Returns:
        CurrentUser: 当前用户信息（已验证为管理员）

    Raises:
        HTTPException: 当用户不是管理员时抛出403错误

    Usage:
        @router.post("/admin/users")
        async def admin_only_route(current_user: CurrentUser = Depends(require_admin)):
            return {"message": "Admin access granted"}
    """
    if not current_user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限"
        )

    return current_user


async def require_super_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    要求超级管理员权限的依赖

    验证当前用户是否为超级管理员

    Args:
        current_user: 当前用户信息（由get_current_user依赖提供）

    Returns:
        CurrentUser: 当前用户信息（已验证为超级管理员）

    Raises:
        HTTPException: 当用户不是超级管理员时抛出403错误

    Usage:
        @router.delete("/admin/users/{user_id}")
        async def super_admin_only_route(
            user_id: str,
            current_user: CurrentUser = Depends(require_super_admin)
        ):
            return {"message": "Super admin access granted"}
    """
    if not current_user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="需要超级管理员权限"
        )

    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> Optional[CurrentUser]:
    """
    可选的用户认证依赖

    如果提供了token则验证，否则返回None。
    适用于某些路由既支持匿名访问又支持登录用户访问的场景。

    Args:
        credentials: 可选的认证凭证

    Returns:
        Optional[CurrentUser]: 如果提供了有效token则返回用户信息，否则返回None

    Usage:
        @router.get("/public-or-private")
        async def mixed_route(current_user: Optional[CurrentUser] = Depends(get_optional_user)):
            if current_user:
                return {"message": f"Hello {current_user.user_id}"}
            else:
                return {"message": "Hello anonymous"}
    """
    if credentials is None:
        return None

    try:
        token = credentials.credentials
        payload = verify_token(token)
        return CurrentUser(user_id=payload["sub"], role=payload["role"])
    except HTTPException:
        # Token无效时返回None而不是抛出异常
        return None


async def get_current_user_from_gateway(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    x_mse_consumer: Optional[str] = Header(None, alias="X-Mse-Consumer"),
) -> Optional[CurrentUser]:
    """
    从Higress网关转发的请求头中获取用户信息（网关侧认证模式）

    当使用Higress网关的JWT插件进行认证时，网关会：
    1. 验证JWT的签名和有效性
    2. 将JWT的payload字段设置到请求头中转发
    3. 添加X-Mse-Consumer标识调用方身份

    Args:
        x_user_id: 网关从JWT的sub字段提取的用户ID
        x_user_role: 网关从JWT的role字段提取的用户角色
        x_mse_consumer: 网关添加的consumer名称

    Returns:
        Optional[CurrentUser]: 如果请求头包含用户信息则返回CurrentUser，否则返回None

    Usage:
        # 在Higress网关后使用此依赖，跳过应用层JWT验证
        @router.get("/models")
        async def get_models(current_user: CurrentUser = Depends(get_current_user_from_gateway)):
            pass

    Note:
        此函数假定请求已通过网关认证，不再进行JWT验证
        仅适用于前端有Higress网关的部署架构
    """
    if not x_user_id or not x_user_role:
        return None

    # 从网关转发的请求头构造用户信息
    return CurrentUser(user_id=x_user_id, role=x_user_role)


async def get_current_user_hybrid(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> CurrentUser:
    """
    混合认证模式：优先使用网关认证，回退到应用层JWT验证

    这是一个兼容性依赖函数，支持：
    1. Higress网关认证：从X-User-Id和X-User-Role获取用户信息
    2. 直接访问：从Authorization header验证JWT

    适用场景：
    - 生产环境使用网关认证
    - 开发/测试环境直接访问后端服务
    - 渐进式迁移到网关认证

    Args:
        x_user_id: 网关转发的用户ID（可选）
        x_user_role: 网关转发的用户角色（可选）
        credentials: Authorization Bearer token（可选）

    Returns:
        CurrentUser: 当前用户信息

    Raises:
        HTTPException: 当两种认证方式都失败时抛出401错误

    Usage:
        @router.get("/models")
        async def get_models(current_user: CurrentUser = Depends(get_current_user_hybrid)):
            # 自动适配网关模式和直连模式
            pass
    """
    # 优先使用网关认证
    if x_user_id and x_user_role:
        return CurrentUser(user_id=x_user_id, role=x_user_role)

    # 回退到JWT验证
    if credentials:
        token = credentials.credentials
        payload = verify_token(token)
        return CurrentUser(user_id=payload["sub"], role=payload["role"])

    # 两种方式都没有提供认证信息
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未提供认证信息",
        headers={"WWW-Authenticate": "Bearer"},
    )
