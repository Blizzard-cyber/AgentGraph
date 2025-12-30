# 记忆客户端使用说明

## 概述

记忆客户端 (`memory_client.py`) 是仿照 MCP 客户端架构设计的，用于与记忆服务进行交互的客户端程序。它提供了统一的 API 接口来管理用户记忆，包括添加记忆和搜索记忆功能。

## 架构特点

### 1. 仿照 MCP 客户端设计
- 使用 FastAPI 提供 RESTful API
- 全局状态管理 (`MEMORY_CLIENT`)
- 异步连接和操作
- 完善的错误处理和日志记录

### 2. 功能特性
- 记忆服务连接管理
- 记忆添加和搜索
- 批量操作支持
- 健康检查和状态监控
- 配置灵活性

## 快速开始

### 1. 启动记忆客户端服务

```bash
# 使用默认配置启动
python memory_client.py

# 自定义端口启动
python memory_client.py --host 0.0.0.0 --port 8766

# 指定记忆服务地址启动
python memory_client.py --memory-host 192.168.1.85 --memory-port 8851
```

### 2. 配置记忆服务连接

```bash
# 使用 curl 配置
curl -X POST "http://127.0.0.1:8766/configure" \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.85",
    "port": 8851,
    "use_https": true,
    "timeout": 30.0
  }'
```

### 3. 测试连接

```bash
curl -X POST "http://127.0.0.1:8766/test_connection"
```

## API 接口

### 基础接口

#### GET `/`
检查客户端状态
```json
{
  "status": "running",
  "memory_service": {
    "connected": true,
    "host": "192.168.1.85",
    "port": 8851,
    "base_url": "https://192.168.1.85:8851",
    "error": null
  }
}
```

#### POST `/configure`
配置记忆客户端
```json
{
  "host": "192.168.1.85",
  "port": 8851,
  "use_https": true,
  "timeout": 30.0
}
```

#### POST `/connect`
连接记忆服务

#### GET `/status`
获取详细状态信息

### 记忆操作接口

#### POST `/add_memory`
添加单条记忆
```json
{
  "user_id": "user123",
  "agent_id": "agent456",
  "session_id": "session789",
  "group_id": "group001",
  "content": "用户询问了关于Python的问题",
  "role": "user",
  "metadata": {
    "topic": "programming",
    "language": "python"
  }
}
```

#### POST `/search_memory`
搜索记忆
```json
{
  "user_id": "user123",
  "agent_id": "agent456",
  "session_id": "session789",
  "group_id": "group001",
  "query": "Python编程",
  "limit": "10",
  "filter_dict": {
    "topic": "programming"
  },
  "timeout": 30
}
```

#### POST `/batch_add_memory`
批量添加记忆
```json
[
  {
    "user_id": "user123",
    "agent_id": "agent456",
    "session_id": "session789",
    "group_id": "group001",
    "content": "第一条记忆",
    "role": "user"
  },
  {
    "user_id": "user123",
    "agent_id": "agent456",
    "session_id": "session789",
    "group_id": "group001",
    "content": "第二条记忆",
    "role": "assistant"
  }
]
```

## 使用示例

### Python 客户端示例

```python
import httpx
import asyncio

class MemoryClientExample:
    def __init__(self):
        self.base_url = "http://127.0.0.1:8766"
    
    async def configure_and_test(self):
        async with httpx.AsyncClient() as client:
            # 1. 配置客户端
            config_response = await client.post(
                f"{self.base_url}/configure",
                json={
                    "host": "192.168.1.85",
                    "port": 8851,
                    "use_https": True
                }
            )
            print("配置结果:", config_response.json())
            
            # 2. 添加记忆
            add_response = await client.post(
                f"{self.base_url}/add_memory",
                json={
                    "user_id": "test_user",
                    "agent_id": "test_agent", 
                    "session_id": "test_session",
                    "group_id": "test_group",
                    "content": "这是一个测试记忆",
                    "role": "user"
                }
            )
            print("添加结果:", add_response.json())
            
            # 3. 搜索记忆
            search_response = await client.post(
                f"{self.base_url}/search_memory",
                json={
                    "user_id": "test_user",
                    "agent_id": "test_agent",
                    "session_id": "test_session", 
                    "group_id": "test_group",
                    "query": "测试",
                    "limit": "5"
                }
            )
            print("搜索结果:", search_response.json())

# 运行示例
asyncio.run(MemoryClientExample().configure_and_test())
```

### curl 示例

```bash
# 1. 配置客户端
curl -X POST "http://127.0.0.1:8766/configure" \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.85",
    "port": 8851,
    "use_https": true
  }'

# 2. 添加记忆
curl -X POST "http://127.0.0.1:8766/add_memory" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "agent_id": "test_agent",
    "session_id": "test_session",
    "group_id": "test_group", 
    "content": "用户询问了天气信息",
    "role": "user",
    "metadata": {"topic": "weather"}
  }'

# 3. 搜索记忆
curl -X POST "http://127.0.0.1:8766/search_memory" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "agent_id": "test_agent",
    "session_id": "test_session",
    "group_id": "test_group",
    "query": "天气",
    "limit": "10"
  }'
```

## 测试工具

我们提供了完整的测试工具 `test_memory_client.py`：

```bash
# 运行完整测试（包括客户端和直接调用对比）
python test/test_memory_client.py

# 只测试记忆客户端
python test/test_memory_client.py client

# 只测试直接调用记忆服务
python test/test_memory_client.py direct

# 显示帮助
python test/test_memory_client.py help
```

测试包括：
- ✓ 客户端状态检查
- ✓ 配置记忆客户端
- ✓ 测试服务连接
- ✓ 添加单条记忆
- ✓ 搜索记忆
- ✓ 批量添加记忆
- ✓ 直接调用对比

## 与原始调用方式的对比

### 原始方式（直接 HTTP 调用）
```python
import http.client
import json

conn = http.client.HTTPSConnection("192.168.1.85", 8851)
payload = json.dumps({
    "user_info": {
        "user_id": "string",
        "agent_id": "string", 
        "session_id": "string",
        "group_id": "string"
    },
    "memory_info": {
        "content": "string",
        "role": "string",
        "metadata": {}
    }
})
headers = {'Content-Type': 'application/json'}
conn.request("POST", "/api/v1/add_memory", payload, headers)
res = conn.getresponse()
data = res.read()
print(data.decode("utf-8"))
```

### 记忆客户端方式
```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://127.0.0.1:8766/add_memory",
        json={
            "user_id": "string",
            "agent_id": "string",
            "session_id": "string", 
            "group_id": "string",
            "content": "string",
            "role": "string",
            "metadata": {}
        }
    )
    result = response.json()
```

### 优势对比

| 特性 | 原始方式 | 记忆客户端 |
|------|----------|------------|
| **连接管理** | 每次手动创建 | 自动管理连接池 |
| **错误处理** | 需要手动处理 | 统一错误处理 |
| **重试机制** | 需要自己实现 | 内置重试逻辑 |
| **日志记录** | 需要自己添加 | 完整的日志系统 |
| **批量操作** | 需要循环调用 | 原生批量支持 |
| **配置管理** | 硬编码配置 | 动态配置管理 |
| **状态监控** | 无 | 实时状态检查 |
| **异步支持** | 无 | 完整异步支持 |

## 配置选项

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `host` | string | "192.168.1.85" | 记忆服务主机地址 |
| `port` | integer | 8851 | 记忆服务端口 |
| `use_https` | boolean | true | 是否使用 HTTPS |
| `timeout` | float | 30.0 | 请求超时时间（秒） |

## 错误处理

记忆客户端提供了完善的错误处理机制：

### 连接错误
- 自动检测服务可用性
- 连接超时重试
- 详细的错误信息记录

### 请求错误
- HTTP 状态码检查
- 响应格式验证
- 超时处理

### 示例错误响应
```json
{
  "success": false,
  "error": "连接失败: Connection timeout",
  "message": "记忆服务连接超时"
}
```

## 日志系统

记忆客户端使用 Python 的 logging 模块，提供详细的日志信息：

```
2025-12-19 10:30:00 - memory_client - INFO - 记忆客户端启动...
2025-12-19 10:30:01 - memory_client - INFO - ✓ 记忆服务连接成功: https://192.168.1.85:8851
2025-12-19 10:30:05 - memory_client - INFO - 记忆添加成功: test_user/test_session
2025-12-19 10:30:10 - memory_client - INFO - 记忆搜索成功: test_user/test_session, 查询: Python编程
```

## 部署建议

### 开发环境
```bash
# 直接运行
python memory_client.py --host 127.0.0.1 --port 8766
```

### 生产环境
```bash
# 使用 uvicorn 启动
uvicorn memory_client:app --host 0.0.0.0 --port 8766 --workers 4

# 或使用 gunicorn
gunicorn memory_client:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8766
```

### Docker 部署
```dockerfile
FROM python:3.9

COPY memory_client.py /app/
COPY requirements.txt /app/

WORKDIR /app
RUN pip install -r requirements.txt

EXPOSE 8766
CMD ["python", "memory_client.py", "--host", "0.0.0.0", "--port", "8766"]
```

## 扩展功能

记忆客户端设计为可扩展的架构，你可以轻松添加：

1. **缓存层** - Redis 缓存频繁查询
2. **认证中间件** - JWT 或 API Key 验证  
3. **限流功能** - 防止过度调用
4. **监控指标** - Prometheus 监控
5. **负载均衡** - 多个记忆服务实例

这个记忆客户端完全仿照了 MCP 客户端的架构模式，提供了统一、可靠、易用的记忆服务访问接口。