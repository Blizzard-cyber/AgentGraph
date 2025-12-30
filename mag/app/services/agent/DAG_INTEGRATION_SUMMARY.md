# DAG与AgentStreamExecutor集成说明

## 修改概述

已成功将DAG执行器与`AgentStreamExecutor`集成，使DAG能够调用真实的Agent进行任务执行。

## 主要修改

### 1. dag_executor.py

#### AgentInterface接口增强
- 添加了`user_id`和`conversation_id`参数支持
- 新增`execute_stream`方法用于流式执行
- 支持传递用户上下文到Agent执行中

```python
async def execute(self, agent_name: str, action: str, input_data: Dict[str, Any], 
                 user_id: str = None, conversation_id: str = None) -> Dict[str, Any]
```

#### DAGExecutor类改进
- 构造函数接受`user_id`和`conversation_id`参数
- `execute_dag`方法支持传递用户上下文
- `_execute_steps`和`_execute_step`方法传递用户上下文到Agent

### 2. dag_service.py

#### RealAgentInterface实现
- 使用`AgentStreamExecutor`替代模拟执行
- 支持真实的Agent调用和流式输出
- 自动创建临时对话ID用于DAG执行
- 收集和解析流式输出到最终结果

```python
class RealAgentInterface(AgentInterface):
    def __init__(self, agent_executor: AgentStreamExecutor = None):
        self.agent_executor = agent_executor or AgentStreamExecutor()
```

#### API端点改进
- `DAGExecutionRequest`增加`user_id`和`conversation_id`字段
- 执行请求时传递用户上下文
- `list_available_agents`端点返回真实的Agent列表（从数据库获取）

### 3. 关键特性

#### 用户上下文支持
- 所有DAG执行都关联到特定用户
- 支持跨会话的DAG执行追踪
- Agent执行结果可追溯到原始用户请求

#### 流式输出处理
- RealAgentInterface收集流式输出
- 提取Assistant的最终回复作为步骤输出
- 保留执行详情（token使用量、迭代次数等）

#### 错误处理
- Agent执行失败时返回详细错误信息
- DAG执行失败时记录完整错误日志
- 支持部分步骤失败的处理

## 使用示例

### 基本用法

```python
# 创建DAG定义
dag_definition = {
    "目标": "分析公司风险",
    "前提假设": ["公司信息可获取"],
    "约束条件": ["30分钟内完成"],
    "步骤": [
        {
            "id": 1,
            "agent": "CompanySearchAgent",
            "action": "搜索公司基本信息",
            "input_schema": {"company_name": "string"},
            "output_schema": {"company_info": "object"},
            "depends_on": []
        },
        {
            "id": 2,
            "agent": "RiskAnalyzeAgent",
            "action": "分析风险",
            "input_schema": {"company_data": "object"},
            "output_schema": {"risk_report": "object"},
            "depends_on": [1]
        }
    ],
    "completion_criteria": "生成完整风险报告"
}

# 执行DAG
response = await client.post("/api/dag/execute", json={
    "dag_definition": dag_definition,
    "max_concurrent": 3,
    "user_id": "user123",
    "conversation_id": "conv456"
})

# 查询状态
status = await client.get(f"/api/dag/status/{execution_id}")
```

### API端点

- `POST /api/dag/execute` - 执行DAG
- `GET /api/dag/status/{execution_id}` - 查询执行状态
- `GET /api/dag/executions` - 列出所有执行
- `GET /api/dag/agents` - 获取可用Agent列表
- `GET /api/dag/template` - 获取DAG模板
- `DELETE /api/dag/execution/{execution_id}` - 取消执行

## 数据流

```
用户请求
  ↓
DAG定义解析
  ↓
步骤依赖分析
  ↓
并行/串行执行步骤
  ↓ (每个步骤)
RealAgentInterface.execute
  ↓
AgentStreamExecutor.run_agent_stream
  ↓
真实Agent执行
  ↓
流式输出收集
  ↓
步骤结果返回
  ↓
DAG完成
```

## 注意事项

1. **会话管理**: 每个DAG执行可以指定对话ID，或自动生成临时ID
2. **并发控制**: 通过`max_concurrent`参数控制最大并发Agent数量
3. **资源使用**: Agent执行会消耗token，需注意成本控制
4. **执行时长**: 复杂DAG可能需要较长执行时间，建议使用后台任务
5. **错误恢复**: 当前版本步骤失败会导致整个DAG失败，后续可增加重试机制

## 下一步改进

- [ ] 支持步骤重试机制
- [ ] 添加步骤超时控制
- [ ] 实现DAG执行的暂停/恢复
- [ ] 支持动态修改DAG定义
- [ ] 增加执行历史的持久化存储
- [ ] 优化大规模DAG的执行效率
