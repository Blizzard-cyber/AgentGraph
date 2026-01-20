"""
生成用于Higress网关JWT验证的JWKS配置

该脚本从项目配置中读取JWT密钥，并生成符合JWKS标准的JSON格式
用于在Higress网关配置JWT鉴权插件
"""

import sys
import json
import base64
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import settings


def generate_jwks_for_hs256():
    """
    生成HS256算法的JWKS配置

    HS256使用对称密钥（HMAC + SHA256）
    """
    secret_key = settings.JWT_SECRET_KEY

    # Base64 URL编码密钥（不带padding）
    k_value = base64.urlsafe_b64encode(secret_key.encode()).decode().rstrip("=")

    jwks = {
        "keys": [
            {
                "kty": "oct",  # Key Type: oct表示对称密钥（Octet sequence）
                "kid": "mag-key-1",  # Key ID: 密钥唯一标识
                "alg": "HS256",  # Algorithm: 签名算法
                "use": "sig",  # Public Key Use: 用于签名
                "k": k_value,  # Key Value: Base64url编码的密钥
            }
        ]
    }

    return jwks


def generate_higress_config():
    """
    生成完整的Higress JWT插件配置示例
    """
    jwks = generate_jwks_for_hs256()

    config = {
        "global_auth": False,  # 重要：设置为False，避免登录接口也需要JWT认证
        "consumers": [
            {
                "name": "mag-user",
                "issuer": "mag-backend",  # 必须与JWT中的iss字段匹配
                "jwks": json.dumps(jwks, indent=2),
                "from_headers": [{"name": "Authorization", "value_prefix": "Bearer "}],
                "from_params": ["access_token"],
                "claims_to_headers": [
                    {"claim": "sub", "header": "X-User-Id", "override": True},
                    {"claim": "role", "header": "X-User-Role", "override": True},
                ],
                "keep_token": True,
                "clock_skew_seconds": 60,
            }
        ],
    }

    return config


def main():
    print("=" * 80)
    print("Higress网关JWT鉴权插件配置生成工具")
    print("=" * 80)
    print()

    print("【1】JWKS配置（用于网关JWT验证）")
    print("-" * 80)
    jwks = generate_jwks_for_hs256()
    print(json.dumps(jwks, indent=2, ensure_ascii=False))
    print()

    print("【2】Higress完整配置示例")
    print("-" * 80)
    config = generate_higress_config()
    print(json.dumps(config, indent=2, ensure_ascii=False))
    print()

    print("=" * 80)
    print("配置说明：")
    print("1. global_auth设置为false，避免登录接口也需要JWT认证")
    print("2. 在Higress中为需要认证的路由配置: allow: [mag-user]")
    print("3. 不配置allow的路由（/api/auth/login等）保持公开访问")
    print("4. issuer必须为'mag-backend'，与项目JWT中的iss字段匹配")
    print("5. kid必须为'mag-key-1'，与JWT Header中的kid字段匹配")
    print("6. 认证通过后，网关会将user_id和role转发到X-User-Id和X-User-Role请求头")
    print("7. 后端服务可以直接从请求头读取用户信息，无需再次验证JWT")
    print("=" * 80)
    print()

    # 保存配置到文件
    output_file = project_root / "scripts" / "higress_jwt" / "higress_jwt_config.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"✓ 配置已保存到: {output_file}")


if __name__ == "__main__":
    main()
