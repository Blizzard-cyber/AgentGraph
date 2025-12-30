# 任务规划模式集成文档

## 概述

任务规划模式是一个智能任务编排系统，它能够：
1. 使用 `plan_agent` 根据用户查询自动生成 DAG（有向无环图）执行计划
2. 根据 DAG 中定义的前驱后继关系，自动并行或串行执行各个 Agent
3. 全程异步执行，支持复杂的多步骤任务编排
4. 流式返回执行过程和结果

## 架构设计

### 核心组件

#### 1. PlanService (`plan_service.py`)
负责任务规划和 DAG 生成的核心服务。

**主要功能：**
- `generate_dag_from_query()`: 调用 plan_agent 生成 DAG 计划
- `execute_planning_mode()`: 执行完整的规划模式流程
- `_build_planning_prompt()`: 构建给 plan_agent 的提示词
- `_parse_dag_from_response()`: 从 plan_agent 的回复中解析 DAG 定义

#### 2. DAGExecutor (`dag_executor.py`)
DAG 执行引擎，负责按照依赖关系执行各个步骤。

**执行特点：**
- 自动识别无依赖步骤，并行执行
- 有依赖关系的步骤按顺序串行执行
- 支持最大并发数控制
- 自动处理步骤失败和错误传播

#### 3. RealAgentInterface (`dag_service.py`)
真实的 Agent 执行接口，连接 DAG 执行器和 AgentStreamExecutor。

**功能：**
- 封装 AgentStreamExecutor 的调用
- 处理流式输出并转换为 DAG 所需的结果格式
- 管理临时对话 ID 和用户上下文

## API 接口

### POST /agent/planning-mode

执行任务规划模式的主接口。

**请求参数：**
```json
{
  "user_query": "用户的任务描述",
  "conversation_id": "可选的对话ID",
  "max_concurrent": 5,
  "include_agents": ["agent1", "agent2"]  // 可选，指定可用的agent
}
```

**响应格式：**

流式 SSE 响应，包含以下事件类型：

1. **planning_start** - 规划开始
```json
{
  "type": "planning_start",
  "message": "开始任务规划...",
  "execution_id": "abc123"
}
```

2. **dag_generated** - DAG 生成完成
```json
{
  "type": "dag_generated",
  "dag": {
    "目标": "完成用户任务",
    "前提假设": ["..."],
    "约束条件": ["..."],
    "步骤": [
      {
        "id": 1,
        "agent": "agent_name",
        "action": "执行动作",
        "input_schema": {...},
        "output_schema": {...},
        "depends_on": []
      }
    ],
    "completion_criteria": "完成标准"
  },
  "execution_id": "abc123"
}
```

3. **execution_start** - 开始执行
```json
{
  "type": "execution_start",
  "message": "开始执行任务...",
  "execution_id": "abc123"
}
```

4. **execution_complete** - 执行完成
```json
{
  "type": "execution_complete",
  "status": {
    "execution_id": "abc123",
    "status": "completed",
    "progress": {
      "total": 5,
      "completed": 5,
      "failed": 0,
      "running": 0,
      "percentage": 100
    },
    "steps": [...]
  },
  "execution_id": "abc123"
}
```

5. **error** - 错误
```json
{
  "type": "error",
  "message": "错误信息",
  "execution_id": "abc123"
}
```

## 执行流程

### 完整流程图

```
用户查询
    ↓
[1] 调用 plan_agent 生成 DAG
    ↓
[2] 解析 DAG 定义
    ↓
[3] 创建 DAGExecutor
    ↓
[4] 分析依赖关系
    ↓
[5] 并行执行无依赖步骤
    ↓
[6] 等待依赖完成，执行后继步骤
    ↓
[7] 收集所有步骤结果
    ↓
[8] 返回完整执行状态
```

### 详细说明

#### 阶段 1：任务规划
1. 接收用户查询
2. 构建规划提示词（包含可用 agent 列表）
3. 调用 `plan_agent` 生成 DAG 计划
4. 解析 plan_agent 的回复，提取 JSON 格式的 DAG 定义

#### 阶段 2：DAG 执行
1. 创建 DAGExecutor 实例
2. 验证 DAG 有效性（循环依赖检查）
3. 按依赖关系执行步骤：
   - 无依赖步骤立即并行执行
   - 有依赖步骤等待前驱完成后执行
   - 控制最大并发数
4. 收集每个步骤的执行结果

#### 阶段 3：结果返回
1. 流式返回执行进度
2. 返回最终执行状态
3. 包含每个步骤的详细信息

## DAG 定义格式

### 标准格式

```json
{
  "目标": "明确的目标描述",
  "前提假设": [
    "假设1：数据源可用",
    "假设2：相关服务正常"
  ],
  "约束条件": [
    "时间限制：30分钟内完成",
    "资源限制：内存不超过4GB"
  ],
  "步骤": [
    {
      "id": 1,
      "agent": "CompanySearchAgent",
      "action": "搜索公司信息",
      "input_schema": {
        "type": "object",
        "required": ["company_name"],
        "properties": {
          "company_name": {
            "type": "string",
            "description": "公司名称"
          }
        }
      },
      "output_schema": {
        "type": "object",
        "required": ["company_info"],
        "properties": {
          "company_info": {
            "type": "object",
            "description": "公司详细信息"
          }
        }
      },
      "depends_on": []
    },
    {
      "id": 2,
      "agent": "RiskAnalyzeAgent",
      "action": "分析公司风险",
      "input_schema": {
        "type": "object",
        "required": ["company_info"],
        "properties": {
          "company_info": {
            "type": "object",
            "description": "公司信息"
          }
        }
      },
      "output_schema": {
        "type": "object",
        "required": ["risk_report"],
        "properties": {
          "risk_report": {
            "type": "object",
            "description": "风险分析报告"
          }
        }
      },
      "depends_on": [1]
    }
  ],
  "completion_criteria": "所有步骤成功完成且生成最终报告"
}
```

### 字段说明

- **目标**: 任务的总体目标
- **前提假设**: 执行所需的前提条件
- **约束条件**: 时间、资源等约束
- **步骤**: 执行步骤数组
  - `id`: 唯一步骤编号
  - `agent`: 执行该步骤的 agent 名称
  - `action`: 该步骤的动作描述
  - `input_schema`: 输入数据结构定义
  - `output_schema`: 输出数据结构定义
  - `depends_on`: 依赖的步骤 ID 列表（空列表表示可立即执行）
- **completion_criteria**: 完成判断标准

## 并行与串行执行

### 并行执行
当多个步骤的 `depends_on` 为空或依赖都已完成时，这些步骤会并行执行。

**示例：**
```json
{
  "步骤": [
    {"id": 1, "agent": "A", "depends_on": []},
    {"id": 2, "agent": "B", "depends_on": []},
    {"id": 3, "agent": "C", "depends_on": []}
  ]
}
```
步骤 1、2、3 会同时执行。

### 串行执行
当步骤有依赖关系时，会等待依赖步骤完成后再执行。

**示例：**
```json
{
  "步骤": [
    {"id": 1, "agent": "A", "depends_on": []},
    {"id": 2, "agent": "B", "depends_on": [1]},
    {"id": 3, "agent": "C", "depends_on": [2]}
  ]
}
```
执行顺序：步骤 1 → 步骤 2 → 步骤 3

### 混合模式
```json
{
  "步骤": [
    {"id": 1, "agent": "A", "depends_on": []},
    {"id": 2, "agent": "B", "depends_on": [1]},
    {"id": 3, "agent": "C", "depends_on": [1]},
    {"id": 4, "agent": "D", "depends_on": [2, 3]}
  ]
}
```
执行流程：
1. 步骤 1 独立执行
2. 步骤 1 完成后，步骤 2 和 3 并行执行
3. 步骤 2 和 3 都完成后，步骤 4 执行

## 使用示例

### 场景 1：简单查询
**用户输入：** "帮我分析一下华为公司的风险"

**生成的 DAG：**
```json
{
  "目标": "分析华为公司的风险",
  "步骤": [
    {
      "id": 1,
      "agent": "CompanySearchAgent",
      "action": "搜索华为公司信息"
    },
    {
      "id": 2,
      "agent": "RiskAnalyzeAgent",
      "action": "分析风险",
      "depends_on": [1]
    }
  ]
}
```

### 场景 2：复杂多步骤任务
**用户输入：** "对比分析华为和小米两家公司的风险，并生成对比报告"

**生成的 DAG：**
```json
{
  "目标": "对比分析华为和小米的风险",
  "步骤": [
    {
      "id": 1,
      "agent": "CompanySearchAgent",
      "action": "搜索华为公司信息"
    },
    {
      "id": 2,
      "agent": "CompanySearchAgent",
      "action": "搜索小米公司信息"
    },
    {
      "id": 3,
      "agent": "RiskAnalyzeAgent",
      "action": "分析华为风险",
      "depends_on": [1]
    },
    {
      "id": 4,
      "agent": "RiskAnalyzeAgent",
      "action": "分析小米风险",
      "depends_on": [2]
    },
    {
      "id": 5,
      "agent": "ReportAgent",
      "action": "生成对比报告",
      "depends_on": [3, 4]
    }
  ]
}
```

**执行流程：**
- 步骤 1、2 并行执行（搜索两家公司）
- 步骤 3、4 并行执行（分析两家公司风险）
- 步骤 5 串行执行（生成最终对比报告）

## 错误处理

### 规划阶段错误
- plan_agent 调用失败
- DAG 解析失败
- DAG 结构无效（循环依赖）

**处理方式：** 返回错误事件，终止执行

### 执行阶段错误
- 单个步骤执行失败
- Agent 不存在
- 超时

**处理方式：**
1. 标记失败步骤
2. 取消依赖该步骤的后续步骤
3. 继续执行其他无关步骤
4. 返回部分成功的结果

## 性能优化

### 并发控制
- 通过 `max_concurrent` 参数限制最大并发数
- 默认值：5
- 避免过多并发导致资源耗尽

### 资源管理
- 使用 asyncio.Semaphore 控制并发
- 自动清理已完成的任务
- 限制内存使用

### 超时控制
- Agent 执行超时保护
- DAG 整体执行超时
- 可配置的超时参数

## 配置说明

### plan_agent 配置要求
plan_agent 必须能够：
1. 理解用户任务需求
2. 了解可用的 agent 能力
3. 生成符合格式的 JSON DAG 定义
4. 合理安排步骤依赖关系

**推荐配置：**
- 模型：GPT-4 或同等能力的模型
- 温度：0.7（平衡创造性和准确性）
- 系统提示：强调 JSON 格式输出和依赖关系设计

### Agent 可用性
- 所有参与 DAG 的 agent 必须事先创建
- Agent 必须支持指定的动作
- Agent 需要有合理的超时设置

## 最佳实践

### DAG 设计
1. **明确目标**：清晰定义每个步骤的输入输出
2. **合理分解**：将复杂任务分解为独立的步骤
3. **优化并行**：尽量减少不必要的依赖，增加并行度
4. **错误容忍**：考虑步骤失败的影响

### 提示词设计
1. **详细描述**：给 plan_agent 提供充分的上下文
2. **明确约束**：说明时间、资源等限制
3. **示例引导**：提供类似任务的示例

### 监控和调试
1. 查看 DAG 生成结果
2. 跟踪每个步骤的执行状态
3. 分析执行时间和资源使用
4. 收集失败原因和改进建议

## 未来扩展

### 计划中的功能
1. **动态调整**：执行过程中调整 DAG 结构
2. **条件分支**：根据步骤结果选择不同路径
3. **循环执行**：支持重试和迭代
4. **人工介入**：在关键步骤等待人工确认
5. **结果缓存**：复用相同步骤的结果
6. **可视化**：DAG 执行过程的图形化展示

### API 扩展
1. 暂停/恢复 DAG 执行
2. DAG 模板管理
3. 执行历史查询
4. 性能分析报告

## 总结

任务规划模式提供了一个强大而灵活的任务编排框架，能够：
- ✅ 自动生成执行计划
- ✅ 智能并行和串行执行
- ✅ 全程异步无阻塞
- ✅ 完整的错误处理
- ✅ 实时进度反馈

这使得复杂的多步骤任务能够自动化执行，大大提高了系统的能力和用户体验。
