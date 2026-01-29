# Agent轨迹数据收集功能

## 功能说明

这个功能用于收集Agent执行过程中的轨迹数据，并上传到指定的服务器，用于后训练和分析。

支持两种模式：
- **单Agent模式**：收集单个Agent的执行轨迹
- **Plan模式**：收集多Agent协作的执行轨迹（DAG执行）

## 配置

在 `.env` 文件中添加以下配置（或使用默认值）：

```env
# 是否启用轨迹收集功能（默认启用）
TRAJECTORY_ENABLED=true

# 轨迹数据上传API服务器配置
TRAJECTORY_API_HOST=192.168.1.86
TRAJECTORY_API_PORT=8226
TRAJECTORY_SINGLE_AGENT_PATH=/trajectory/uploadSingleAgentTrajectory
TRAJECTORY_MULTI_AGENT_PATH=/trajectory/uploadMultiAgentTrajectory
TRAJECTORY_USE_HTTPS=true
```

## 工作流程

### 单Agent模式

1. **创建轨迹收集器**：在Agent开始执行时，自动创建轨迹收集器
2. **收集执行步骤**：每次工具调用时，记录以下信息：
   - `stepID`: 步骤ID（自动递增）
   - `agentName`: Agent名称
   - `thought`: Agent的思考过程（从reasoning_content提取）
   - `tool`: 使用的工具名称（格式：`[ToolName]`）
   - `output`: 工具执行结果
   - `depend_on`: 依赖的步骤ID列表

3. **上传轨迹数据**：Agent执行完成后，异步上传轨迹数据到服务器

### Plan模式

1. **创建Plan轨迹收集器**：在DAG执行开始时创建
2. **执行DAG任务**：按照依赖关系执行各个Agent
3. **收集步骤**：每个Agent执行完成后，记录其轨迹信息
4. **上传轨迹数据**：DAG执行完成后，异步上传到多Agent轨迹API

## 数据格式

### 单Agent模式

上传到 `/trajectory/uploadSingleAgentTrajectory` 的JSON格式：

```json
[
  {
    "agentID": "agent_test",
    "userID": "user123",
    "query": "用户的原始查询",
    "steps": [
      {
        "stepID": 1,
        "agentName": "agent_test",
        "thought": "Agent的思考过程",
        "tool": "[ToolName]",
        "output": {
          "result": "工具执行结果"
        },
        "depend_on": []
      }
    ]
  }
]
```

### Plan模式

上传到 `/trajectory/uploadMultiAgentTrajectory` 的JSON格式：

```json
[
  {
    "planAgentID": "plan_agent",
    "userID": "user123",
    "query": "用户的原始查询",
    "steps": [
      {
        "stepID": 1,
        "agentName": "Outline_Agent",
        "thought": "构建报告大纲",
        "tool": "[Draft_Outline]",
        "output": {
          "title": "报告标题",
          "sections": ["章节1", "章节2"]
        },
        "depend_on": []
      },
      {
        "stepID": 2,
        "agentName": "Writer_Agent",
        "thought": "撰写正文内容",
        "tool": "[Generate_Content]",
        "output": "生成的内容...",
        "depend_on": [1]
      }
    ]
  }
]
```

## 启用/禁用

- **启用**：设置 `TRAJECTORY_ENABLED=true`
- **禁用**：设置 `TRAJECTORY_ENABLED=false`

禁用后，轨迹收集器仍会创建，但不会执行上传操作。

## 注意事项

### 单Agent模式
1. **仅单Agent执行**：只在单Agent执行时收集轨迹，不包括：
   - Sub Agent（Graph中的子任务）
   - Graph节点调用

2. **异步上传**：轨迹数据上传是异步的，不会阻塞Agent响应

### Plan模式
1. **多Agent协作**：收集DAG执行过程中所有Agent的轨迹
2. **依赖关系**：自动记录步骤之间的依赖关系（`depend_on`字段）
3. **异步上传**：DAG执行完成后异步上传，不阻塞响应

### 通用
1. **错误处理**：上传失败不会影响Agent的正常执行，错误会记录到日志
2. **SSL验证**：如果是内网环境，已禁用SSL验证（`ssl=False`）

## 日志

查看轨迹收集相关日志：

### 单Agent模式
```bash
# 成功创建收集器
已创建轨迹收集器: agent=agent_test, user=user123

# 添加步骤
添加轨迹步骤 #1: tool=[ToolName], agent=agent_test

# 上传成功
轨迹数据上传成功: agent=agent_test, steps=3

# 上传失败
轨迹数据上传失败: agent=agent_test
```

### Plan模式
```bash
# 成功创建收集器
已创建Plan轨迹收集器: plan_agent=plan_agent, user=user123

# 添加步骤
添加Plan轨迹步骤 #1: tool=[Outline_Agent], agent=Outline_Agent

# 上传成功
Plan轨迹数据上传成功: plan_agent=plan_agent, steps=3

# 上传失败
Plan轨迹数据上传失败: plan_agent=plan_agent
```

## 测试

提供了两个测试脚本：

### 单Agent模式测试
```bash
cd /home/hsz/mcp-agent-graph
python test/test_trajectory.py
```

### Plan模式测试
```bash
cd /home/hsz/mcp-agent-graph
python test/test_plan_trajectory.py
```

## 依赖

需要安装 `aiohttp` 库：

```bash
pip install aiohttp>=3.9.0
```
