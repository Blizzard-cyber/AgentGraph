# Higress网关JWT认证 - 完整配置指南

## 📖 目录
- [认证模式说明](#认证模式说明)
- [配置步骤](#配置步骤)
- [路由正则表达式](#路由正则表达式)
- [验证测试](#验证测试)
- [故障排查](#故障排查)

---


## 认证模式说明

### 🎯 混合认证工作原理

```python
# 认证优先级
if X-User-Id and X-User-Role:
    # 1. 优先使用网关认证（生产环境）
    return CurrentUser(user_id=X-User-Id, role=X-User-Role)
elif Authorization Bearer token:
    # 2. 回退到JWT验证（开发环境）
    return verify_jwt_and_return_user()
else:
    # 3. 返回401未授权
    raise HTTPException(401)
```

### 📊 部署模式对比

| 模式 | 认证位置 | 性能 | 使用场景 |
|------|---------|------|---------|
| 网关模式 | Higress网关 | 最优 (95%提升) | 生产环境 |
| 直连模式 | 应用层JWT验证 | 正常 | 开发/测试环境 |

---

## 配置步骤

### 第1步：生成JWKS配置

```bash
python mag/scripts/generate_jwks.py
```

配置文件会生成到：`docker/mag_services/higress_jwt_config.json`

### 第2步：配置Higress网关

#### 基础JWT配置

```yaml
# 实例级别配置
global_auth: false  # 使用路由级别认证
consumers:
  - name: mag-user
    issuer: mag-backend  # ⚠️ 必须与JWT的iss字段一致
    jwks: |
      {
        "keys": [
          {
            "kty": "oct",
            "kid": "mag-key-1",  # ⚠️ 必须与JWT的kid一致
            "alg": "HS256",
            "k": "ZjdhQlZIeFBzMkd5akxtc1NnMlJ6Skc5aTlmbmRWRl9NMDdkUERFMzhpMFFBNDFTLXJmcGFuRktlUmxZNG9BTkFKb0lWRG1tOENibWMxelNnOVhvRFE"
          }
        ]
      }
    from_headers:
      - name: "Authorization"
        value_prefix: "Bearer "
    claims_to_headers:  # ⚠️ 转发用户信息到后端
      - claim: "sub"
        header: "X-User-Id"
        override: true
      - claim: "role"
        header: "X-User-Role"
        override: true
    keep_token: true
    clock_skew_seconds: 60
```

> **注意**：`jwks.keys[0].k` 的值从 `mag/scripts/higress_jwt/higress_jwt_config.json` 文件中获取

---

## 🚀 Higress网关配置（双路由模式）

> ⚠️ **推荐方案**：在Higress控制台创建**两个独立的路由**，分别处理公开路由和受保护路由，JWT插件只绑定到受保护路由。

### 📋 配置步骤

#### 步骤1：创建公开路由（不需要JWT认证）

**路由名称**：`mag-public`

**配置YAML**：
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mag-public
  annotations:
    higress.io/priority: "100"  # 高优先级，优先匹配
spec:
  ingressClassName: higress
  rules:
    - host: your-domain.com
      http:
        paths:
          # 认证接口
          - path: /api/auth/login
            pathType: Exact
            backend:
              service:
                name: mag-backend
                port:
                  number: 8000
          - path: /api/auth/register
            pathType: Exact
            backend:
              service:
                name: mag-backend
                port:
                  number: 8000
          - path: /api/auth/refresh
            pathType: Exact
            backend:
              service:
                name: mag-backend
                port:
                  number: 8000
          # 分享查看接口
          - path: /api/preview/share
            pathType: Prefix
            backend:
              service:
                name: mag-backend
                port:
                  number: 8000
          - path: /api/share
            pathType: Prefix
            backend:
              service:
                name: mag-backend
                port:
                  number: 8000
```

**控制台操作**：
1. 进入Higress控制台 → 路由管理 → 创建路由
2. 路由名称：`mag-public`
3. 域名：`your-domain.com`
4. 添加路径：
   - `/api/auth/login` (精确匹配)
   - `/api/auth/register` (精确匹配)
   - `/api/auth/refresh` (精确匹配)
   - `/api/preview/share` (前缀匹配)
   - `/api/share` (前缀匹配)
5. 目标服务：选择 `mag-backend`，端口 `8000`
6. 优先级：设置为 `100`
7. **❗不要配置任何插件**

#### 步骤2：创建受保护路由（需要JWT认证）

**路由名称**：`mag-protected`

**配置YAML**：
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mag-protected
  annotations:
    higress.io/priority: "50"  # 较低优先级，兜底路由
spec:
  ingressClassName: higress
  rules:
    - host: your-domain.com
      http:
        paths:
          # 匹配所有/api请求（作为兜底）
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: mag-backend
                port:
                  number: 8000
```

**控制台操作**：
1. 进入Higress控制台 → 路由管理 → 创建路由
2. 路由名称：`mag-protected`
3. 域名：`your-domain.com`
4. 添加路径：`/api` (前缀匹配)
5. 目标服务：选择 `mag-backend`，端口 `8000`
6. 优先级：设置为 `50`

#### 步骤3：为受保护路由配置JWT插件

**在Higress控制台操作**：

1. 进入 `mag-protected` 路由详情页
2. 点击"插件配置" → "添加插件"
3. 选择 "JWT认证" 插件
4. 配置参数：

**插件配置YAML**：
```yaml
global_auth: false
consumers:
  - name: mag-user
    issuer: mag-backend  # ⚠️ 必须与JWT的iss字段一致
    jwks: |
      {
        "keys": [
          {
            "kty": "oct",
            "kid": "mag-key-1",
            "alg": "HS256",
            "k": "<使用generate_jwks.py生成的base64密钥>"
          }
        ]
      }
    from_headers:
      - name: "Authorization"
        value_prefix: "Bearer "
    claims_to_headers:
      - claim: "sub"
        header: "X-User-Id"
        override: true
      - claim: "role"
        header: "X-User-Role"
        override: true
    keep_token: true
    clock_skew_seconds: 60
```

**控制台表单填写**：
- **Global Auth**: `false`（关闭全局认证）
- **Consumer Name**: `mag-user`
- **Issuer**: `mag-backend`
- **JWKS**: 粘贴从 `docker/mag_services/higress_jwt_config.json` 生成的完整JWKS配置
- **从请求头提取Token**:
  - Header名称: `Authorization`
  - 值前缀: `Bearer `
- **Claims映射到请求头**:
  - Claim: `sub` → Header: `X-User-Id` (覆盖: true)
  - Claim: `role` → Header: `X-User-Role` (覆盖: true)
- **保留原Token**: `true`
- **时钟偏移容忍度**: `60` 秒

### 🎯 工作流程说明

```
用户请求 → Higress路由匹配

/api/auth/login      → mag-public (优先级100)    → 直接转发 → 后端
/api/share/abc123    → mag-public (优先级100)    → 直接转发 → 后端
/api/graphs          → mag-protected (优先级50)  → JWT验证 → 后端(带X-User-Id)
/api/conversations   → mag-protected (优先级50)  → JWT验证 → 后端(带X-User-Id)
```

### ⚠️ 关键配置要点

1. **路由优先级**：
   - `mag-public`: 优先级 `100`（高优先级，优先匹配）
   - `mag-protected`: 优先级 `50`（低优先级，兜底匹配）

2. **JWT插件绑定**：
   - ✅ 只绑定到 `mag-protected` 路由
   - ❌ `mag-public` 路由不配置任何插件

3. **密钥一致性**：
   - JWT的`iss`字段 = Higress配置的`issuer`
   - JWT的`kid`字段 = JWKS配置的`kid`
   - JWT签名密钥 = JWKS配置的`k`（base64编码）

4. **路径匹配类型**：
   - 认证接口：`Exact`（精确匹配）
   - 分享接口：`Prefix`（前缀匹配）
   - 兜底路由：`Prefix`（前缀匹配）

---

---

## 📋 接口分类说明

### 🔓 不需要认证的接口（公开访问）

| 路径模式 | 示例 | 说明 |
|---------|------|------|
| `/api/auth/login` | - | 用户登录 |
| `/api/auth/register` | - | 用户注册 |
| `/api/auth/refresh` | - | 刷新Token |
| `/api/preview/share/*` | `/api/preview/share/abc123` | 查看预览分享 |
| `/api/share/*` | `/api/share/xyz789` | 对话分享相关（查看内容、下载文件） |

### 🔒 需要认证的接口（其他所有/api/*）

- `/api/auth/me` - 获取当前用户信息
- `/api/models/*` - 模型管理
- `/api/graphs/*` - 工作流管理
- `/api/conversations/*` - 对话管理
- `/api/mcp/*` - MCP服务器管理
- `/api/memory/*` - 记忆管理
- 其他所有 `/api/*` 接口

---

## 🎯 正则表达式说明

> ⚠️ **关键限制**：Higress/Envoy **不支持负向前瞻** `(?!...)`，但可以通过**双正则路由 + 路由优先级**实现类似效果。

### ✅ 可行方案：双正则路由配置

通过配置两个正则路由，利用路由优先级来实现公开路由和受保护路由的区分。

#### 方案1：Exact/Prefix匹配（推荐，最简单）

参考前面章节的双路由配置，使用Exact和Prefix匹配类型。

#### 方案2：双正则路由（可行，但正则需准确）

**配置思路**：
1. **路由1（mag-public）**：正则匹配公开路由，优先级100，不配置JWT
2. **路由2（mag-protected）**：正则匹配所有/api，优先级50，配置JWT

**路由1：mag-public（优先级100）**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mag-public
  annotations:
    higress.io/path-type: "Regex"
    higress.io/priority: "100"
spec:
  ingressClassName: higress
  rules:
    - host: your-domain.com
      http:
        paths:
          - path: ^/api/(auth/(login|register|refresh)|preview/share/[^/]+|share/.*)$
            pathType: ImplementationSpecific
            backend:
              service:
                name: mag-backend
                port:
                  number: 8000
```

**正则说明**：
```regex
^/api/(auth/(login|register|refresh)|preview/share/[^/]+|share/.*)$
```

**匹配路径**：
- ✅ `/api/auth/login`
- ✅ `/api/auth/register`
- ✅ `/api/auth/refresh`
- ✅ `/api/preview/share/abc123`
- ✅ `/api/share/xyz789`
- ✅ `/api/share/xyz789/files`
- ✅ `/api/share/xyz789/batch`

**不匹配路径**（会走路由2）：
- ❌ `/api/auth/me`
- ❌ `/api/graphs`
- ❌ `/api/models`
- ❌ `/api/conversations`

**路由2：mag-protected（优先级50）**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mag-protected
  annotations:
    higress.io/path-type: "Regex"
    higress.io/priority: "50"
spec:
  ingressClassName: higress
  rules:
    - host: your-domain.com
      http:
        paths:
          - path: ^/api/.*
            pathType: ImplementationSpecific
            backend:
              service:
                name: mag-backend
                port:
                  number: 8000
```

**正则说明**：
```regex
^/api/.*
```

匹配所有 `/api` 开头的路径（作为兜底）

**JWT插件配置（绑定到mag-protected）**：

```yaml
apiVersion: extensions.higress.io/v1alpha1
kind: WasmPlugin
metadata:
  name: mag-jwt-auth
spec:
  defaultConfig:
    global_auth: false
    consumers:
      - name: mag-user
        issuer: mag-backend
        jwks: |
          {
            "keys": [
              {
                "kty": "oct",
                "kid": "mag-key-1",
                "alg": "HS256",
                "k": "<从generate_jwks.py生成>"
              }
            ]
          }
        from_headers:
          - name: "Authorization"
            value_prefix: "Bearer "
        claims_to_headers:
          - claim: "sub"
            header: "X-User-Id"
            override: true
          - claim: "role"
            header: "X-User-Role"
            override: true
        keep_token: true
        clock_skew_seconds: 60
  matchRules:
    - ingress:
        - mag-protected  # 只绑定到受保护路由
      config:
        allow:
          - mag-user
```

#### 工作流程

```
用户请求 → Higress按优先级匹配

/api/auth/login
  → 检查 mag-public (优先级100, 正则)
  → 匹配成功 ✅
  → 不执行JWT验证
  → 转发到后端

/api/graphs
  → 检查 mag-public (优先级100, 正则)
  → 正则不匹配 ❌
  → 检查 mag-protected (优先级50, 正则)
  → 匹配成功 ✅
  → 执行JWT验证
  → 验证通过后转发到后端
```

### 📊 方案对比

| 方案 | 匹配类型 | 优点 | 缺点 |
|------|---------|------|------|
| **方案1：Exact/Prefix** | Exact + Prefix | ✅ 配置直观<br>✅ 不易出错<br>✅ 无需正则知识 | 需要逐个列出路径 |
| **方案2：双正则** | Regex + Regex | ✅ 配置简洁<br>✅ 灵活性高 | ⚠️ 正则需准确<br>⚠️ 调试困难 |

### ⚠️ 使用双正则方案的注意事项

1. **正则必须准确**：公开路由的正则必须完整匹配所有不需要认证的路径
2. **优先级必须正确**：mag-public (100) > mag-protected (50)
3. **正则必须以 `^` 开头，`$` 结尾**：确保完整匹配
4. **需要添加注解**：`higress.io/path-type: "Regex"`
5. **测试充分**：上线前务必测试所有公开路由和受保护路由

### 🧪 验证双正则配置

```bash
# 1. 测试公开路由（应该返回200，无需token）
curl -v http://your-domain.com/api/auth/login \
  -X POST -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

curl -v http://your-domain.com/api/share/test123

# 2. 测试受保护路由（无token应该返回401）
curl -v http://your-domain.com/api/graphs
curl -v http://your-domain.com/api/models

# 3. 测试边界情况
curl -v http://your-domain.com/api/auth/me  # 应该401（不是login/register/refresh）
```

### 📌 配置要点总结

| 配置项 | 方案1（Exact/Prefix） | 方案2（双正则） |
|--------|--------------------|----------------|
| 公开路由匹配 | Exact + Prefix | Regex |
| 受保护路由匹配 | Prefix | Regex |
| 公开路由优先级 | 100 | 100 |
| 受保护路由优先级 | 50 | 50 |
| 配置难度 | ⭐⭐ | ⭐⭐⭐⭐ |
| 维护难度 | ⭐⭐ | ⭐⭐⭐⭐ |
| 推荐度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

### 🚫 不要尝试的方案

1. ❌ 使用负向前瞻正则（不支持，会报错）
2. ❌ 正则匹配公开 + 前缀匹配受保护（优先级问题，前缀会先匹配）
3. ❌ 单个正则路由用复杂逻辑（无法实现排除逻辑）

---

## 🧪 验证测试

### 1. 测试登录（公开路由，无需token）

```bash
curl -v -X POST http://your-domain.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

**预期**：HTTP 200，返回 `access_token` 和 `refresh_token`

### 2. 测试分享查看（公开路由，无需token）

```bash
curl http://your-domain.com/api/preview/share/abc123
curl http://your-domain.com/api/share/xyz789
```

**预期**：HTTP 200 或 404（分享不存在）

### 3. 测试业务接口-无token（应该返回401）

```bash
curl -v http://your-domain.com/api/graphs
curl -v http://your-domain.com/api/models
curl -v http://your-domain.com/api/mcp/status
```

**预期**：HTTP 401，错误信息 `Jwt missing`

### 4. 测试业务接口-有token（应该成功）

```bash
# 获取token
ACCESS_TOKEN=$(curl -s -X POST http://your-domain.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.access_token')

# 访问业务接口
curl http://your-domain.com/api/graphs \
  -H "Authorization: Bearer $ACCESS_TOKEN"

curl http://your-domain.com/api/models \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

**预期**：HTTP 200，返回数据，后端日志显示 `X-User-Id` 和 `X-User-Role` 请求头

### 5. 本地测试脚本

```bash
# 测试JWT生成
python mag/scripts/test_higress_jwt.py

# 测试混合认证
python mag/scripts/test_hybrid_auth.py
```

---

## ⚠️ 故障排查

## ⚠️ 故障排查

### 问题1：登录返回401 "Jwt missing"

**原因**：`mag-public` 路由配置了JWT插件或优先级设置错误

**解决**：
1. 检查 `mag-public` 路由是否配置了任何插件（应该没有）
2. 确认 `mag-public` 优先级为100，`mag-protected` 为50
3. 确认 `/api/auth/login` 在 `mag-public` 路由中且匹配类型为 `Exact`

### 问题2：业务接口返回404

**原因**：`mag-protected` 路由配置不正确

**解决**：
1. 确认 `mag-protected` 路由存在
2. 确认路径为 `/api` (Prefix匹配)
3. 测试是否返回401而不是404（401说明路由正确，只是缺JWT）

### 问题3：JWT验证失败 "Jwt verification fails"

**原因**：密钥配置不一致

**检查清单**：
- [ ] JWT生成的`issuer`是`mag-backend`
- [ ] JWT生成的`kid`是`mag-key-1`
- [ ] Higress配置的`issuer`是`mag-backend`
- [ ] JWKS中的`kid`是`mag-key-1`
- [ ] JWKS中的`k`值正确（使用generate_jwks.py生成）

**验证命令**：
```bash
# 重新生成JWKS
python mag/scripts/generate_jwks.py

# 测试JWT生成
python mag/scripts/test_higress_jwt.py
```

### 问题4：后端收不到X-User-Id请求头

**原因**：未配置`claims_to_headers`或`override`未设置

**解决**：
在JWT插件配置中添加：
```yaml
claims_to_headers:
  - claim: "sub"
    header: "X-User-Id"
    override: true
  - claim: "role"
    header: "X-User-Role"
    override: true
```

### 问题5：开发环境直连后端也需要JWT

**说明**：这是正常的！混合认证模式会自动降级到JWT验证

**验证**：
```bash
# 直连后端测试（端口8000）
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 获取token后访问
curl http://localhost:8000/api/graphs \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---
            value_prefix: "Bearer "
        claims_to_headers:
          - claim: "sub"
            header: "X-User-Id"
          - claim: "role"
            header: "X-User-Role"
        keep_token: true
        clock_skew_seconds: 60
  matchRules:
    - ingress:
        - mag-api-gateway
      config:
        allow:
          - mag-user
      match:
        # 只对需要认证的路由启用JWT验证
        - uri:
            regex: /api/(?!(auth/(login|register|refresh)|preview/share/[^/]+|share/)).*
```

> **关键点**：
> 1. **Ingress 路由**使用简单的 `/api` 前缀匹配所有请求（确保所有API都能到达后端）
> 2. **JWT插件**通过 `matchRules.match.uri.regex` 来控制哪些路由需要认证
> 3. 不要在Ingress层用正则分割路由，否则容易遗漏某些路径

**正确配置方式B - 使用正则路由（需要完整覆盖）**：
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mag-api-gateway
  annotations:
    higress.io/path-type: "Regex"
spec:
  ingressClassName: higress
  rules:
    - host: your-domain.com
      http:
        paths:
          # ⚠️ 必须确保这两条正则能匹配所有/api/*请求
          # 公开路由
          - path: ^/api/(auth/(login|register|refresh)|preview/share/[^/]+|share/.*)$
            pathType: ImplementationSpecific
            backend:
              service:
                name: mag-backend
                port:
                  number: 8000
          # 受保护路由（使用负向前瞻排除公开路由）
          - path: ^/api/(?!(auth/(login|register|refresh)|preview/share/[^/]+|share/)).*$
            pathType: ImplementationSpecific
            backend:
              service:
                name: mag-backend
                port:
                  number: 8000
```

> ⚠️ **重要**：使用方式B时，正则必须以 `^` 开头和 `$` 结尾，并且两条规则必须完整覆盖所有 `/api/*` 路径

**验证方法**：
```bash
# 测试业务接口是否可达（无token，应该返回401而不是404）
curl -v http://your-gateway.com/api/graphs
# 预期: HTTP 401 Unauthorized (说明路由正确，只是缺少JWT)

# 如果返回404，说明路由配置有问题
curl -v http://your-gateway.com/api/conversations
# 预期: HTTP 401 Unauthorized

curl -v http://your-gateway.com/api/mcp/status
# 预期: HTTP 401 Unauthorized
```

### ❌ 问题2：登录失败，返回 "Jwt is missing"

**原因**：Higress的`global_auth: true`导致登录接口也需要JWT

**解决**：设置`global_auth: false`，使用路由级别的认证配置（见上面方式A）

### ❌ 问题3：后端收不到用户信息（X-User-Id为空）

**原因**：未配置`claims_to_headers`

**解决**：
```yaml
claims_to_headers:
  - claim: "sub"
    header: "X-User-Id"
  - claim: "role"
    header: "X-User-Role"
```

### ❌ 问题4：开发环境直连后端失败

**原因**：混合模式未正确配置

**解决**：代码已配置为混合模式，直连时会自动使用JWT验证。检查：
```bash
# 确认所有路由已切换
grep -r "get_current_user[^_]" mag/app/api/*.py
# 应该返回0行

# 确认导入正确
grep "get_current_user_hybrid" mag/app/api/*.py
# 应该有多行
```

---

## 📊 配置检查清单

### 路由配置
- [ ] `mag-public` 路由已创建（优先级100）
- [ ] `mag-public` 包含5个路径（3个Exact + 2个Prefix）
- [ ] `mag-public` 未配置任何插件
- [ ] `mag-protected` 路由已创建（优先级50）
- [ ] `mag-protected` 路径为 `/api` (Prefix)

### JWT插件配置
- [ ] 已生成JWKS配置（`python mag/scripts/generate_jwks.py`）
- [ ] JWT插件绑定到 `mag-protected` 路由
- [ ] `global_auth` 设置为 `false`
- [ ] `issuer` 设置为 `mag-backend`
- [ ] JWKS中`kid`为`mag-key-1`
- [ ] 配置了`from_headers`提取token
- [ ] 配置了`claims_to_headers`映射（override: true）

### 验证测试
- [ ] 登录接口返回200（无需token）
- [ ] 分享接口返回200/404（无需token）
- [ ] 业务接口无token返回401
- [ ] 业务接口有token返回200
- [ ] 后端日志显示`X-User-Id`和`X-User-Role`

---

## 🎯 快速参考

### 关键配置值

| 配置项 | 值 | 说明 |
|-------|-----|------|
| issuer | `mag-backend` | JWT签发者 |
| kid | `mag-key-1` | 密钥ID |
| algorithm | `HS256` | 加密算法 |
| access_token过期 | 15分钟 | 访问令牌有效期 |
| refresh_token过期 | 7天 | 刷新令牌有效期 |

### 网关转发的请求头

| 请求头 | 来源 | 说明 |
|--------|------|------|
| `X-User-Id` | JWT的`sub`字段 | 用户ID |
| `X-User-Role` | JWT的`role`字段 | 用户角色 |
| `X-Mse-Consumer` | 网关添加 | Consumer名称 |
| `Authorization` | 原始请求 | 原始JWT token |

### 常见错误码

| 状态码 | 错误信息 | 原因 | 解决方案 |
|--------|---------|------|---------|
| 401 | Jwt missing | 未携带JWT | 添加Authorization头 |
| 401 | Jwt expired | JWT已过期 | 使用refresh token刷新 |
| 401 | Jwt verification fails | 签名验证失败 | 检查issuer和jwks配置 |
| 403 | Access Denied | 无权限访问 | 检查路由allow配置 |

---

## 🔗 相关资源

- [Higress JWT插件官方文档](https://higress.cn/docs/latest/plugins/authentication/jwt-auth/)
- [RFC 7519 - JSON Web Token](https://www.rfc-editor.org/rfc/rfc7519)
- [RFC 7517 - JSON Web Key](https://www.rfc-editor.org/rfc/rfc7517)

---

## 📞 技术支持

**配置脚本**：
- `mag/scripts/generate_jwks.py` - 生成JWKS配置
- `mag/scripts/test_higress_jwt.py` - 测试JWT配置
- `mag/scripts/test_hybrid_auth.py` - 测试混合认证

**配置文件**：
- `docker/mag_services/higress_jwt_config.json` - Higress配置模板

---

**✨ 配置完成后，你将拥有高性能的网关认证体系！**
