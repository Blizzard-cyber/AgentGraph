# 前端任务规划模式集成文档

## 概述

在前端添加了任务规划模式（Planning Mode），允许用户通过选择 plan agent 来自动生成和执行 DAG 任务计划。

## 修改的文件

### 1. 类型定义 (`src/types/conversation.ts`)

- ✅ 扩展 `ConversationMode` 类型，添加 `'planning'` 模式
- ✅ 更新 `ConversationSummary` 和 `ConversationDetail` 接口的 `type` 字段
- ✅ 在 `InputConfig` 接口中添加：
  - `plan_agent_name?: string` - 规划 agent 名称
  - `include_agents?: string[]` - 可用的 agent 列表

### 2. 模式选择器 (`src/components/chat/input/ModeSelector.tsx`)

#### 新增导入
```tsx
import { Network } from 'lucide-react'; // 规划模式图标
import { Tag } from 'antd'; // 显示选中的 agents
```

#### 新增状态
```tsx
const [planAgentName, setPlanAgentName] = useState<string>('plan_agent');
const [includeAgents, setIncludeAgents] = useState<string[]>([]);
```

#### 新增模式选项
```tsx
{
  key: 'planning' as ConversationMode,
  title: '任务规划',
  description: '自动生成并执行任务计划',
  icon: Network
}
```

#### UI 改进
- 将网格布局从 2 列改为 3 列以容纳新模式
- 添加 Planning 模式特有的控制器：
  - Plan Agent 选择器（选择规划 agent）
  - 可用 Agent 选择器（添加可执行的 agents）
  - Agent 标签列表（显示和移除已选 agents）

### 3. SSE 连接处理 (`src/hooks/useSSEConnection.ts`)

#### 新增 Planning 模式连接逻辑
```tsx
case 'planning': {
  const request = {
    user_query: inputText,
    conversation_id: conversationId,
    plan_agent_name: options.plan_agent_name || 'plan_agent',
    max_concurrent: options.max_concurrent || 5,
    include_agents: options.include_agents || []
  };
  reader = await ConversationService.createPlanningModeSSE(request);
  break;
}
```

#### 新增事件处理
- `planning_start` - 规划开始
- `dag_generated` - DAG 生成完成
- `execution_start` - 执行开始
- `execution_complete` - 执行完成

### 4. 对话服务 (`src/services/conversationService.ts`)

#### 新增 API 方法
```tsx
static async createPlanningModeSSE(request: {
  user_query: string;
  conversation_id?: string;
  plan_agent_name?: string;
  max_concurrent?: number;
  include_agents?: string[];
}): Promise<ReadableStreamDefaultReader<Uint8Array>>
```

调用后端 `/agent/planning-mode` 端点。

### 5. 聊天系统 (`src/pages/ChatSystem.tsx`)

#### 配置保存
在 `handleStartConversation` 中保存 planning 模式配置：
```tsx
setInheritedConfig({
  // ... 其他配置
  plan_agent_name: options.plan_agent_name,
  include_agents: options.include_agents
});
```

#### SSE 连接参数
在 `startConnection` 调用中添加 planning 参数：
```tsx
plan_agent_name: options.plan_agent_name,
include_agents: options.include_agents,
max_concurrent: options.max_concurrent,
```

## 使用流程

### 1. 选择规划模式
用户在新建对话界面看到三个模式选项：
- **Agent 模式** - 单个 agent 执行
- **Graph 模式** - 图工作流执行
- **任务规划** - 自动 DAG 规划和执行

### 2. 配置规划模式

**选择 Plan Agent:**
点击"规划 Agent"选择器，选择用于生成 DAG 计划的 agent（默认为 `plan_agent`）

**添加可用 Agents:**
1. 点击"添加可用 Agent"选择器
2. 选择一个 agent
3. agent 会显示为标签
4. 可以点击标签的 × 移除

**输入任务描述:**
在输入框中描述任务，例如：
```
分析华为和小米两家公司的风险，并生成对比报告
```

### 3. 开始执行
点击发送按钮后：
1. **规划阶段** - Plan agent 分析任务并生成 DAG
2. **DAG 展示** - 显示生成的任务计划（目标、步骤数）
3. **执行阶段** - 根据依赖关系并行/串行执行
4. **结果展示** - 显示执行进度和最终结果

## 前后端通信

### 请求格式
```json
POST /agent/planning-mode
{
  "user_query": "用户任务描述",
  "conversation_id": "会话ID",
  "plan_agent_name": "plan_agent",
  "max_concurrent": 5,
  "include_agents": ["agent1", "agent2"]
}
```

### SSE 事件流
```
data: {"type": "planning_start", "message": "开始任务规划...", "execution_id": "abc123"}

data: {"type": "dag_generated", "dag": {...}, "execution_id": "abc123"}

data: {"type": "execution_start", "message": "开始执行任务...", "execution_id": "abc123"}

data: {"type": "execution_complete", "status": {...}, "execution_id": "abc123"}

data: [DONE]
```

## 前端展示效果

### 模式选择界面
```
┌──────────────┬──────────────┬──────────────┐
│  Agent 模式  │  Graph 模式  │  任务规划    │
│   单agent   │  工作流执行  │  自动规划     │
└──────────────┴──────────────┴──────────────┘
```

### Planning 模式控制区
```
┌─────────────────────────────────────────────┐
│ 输入任务描述...                              │
│                                             │
│ [规划 Agent ▼] [添加可用 Agent ▼]           │
│ [agent1 ×] [agent2 ×] [agent3 ×]           │
└─────────────────────────────────────────[→]┘
```

### 执行过程展示
```
🤖 开始任务规划...

📋 任务计划已生成
   目标: 对比分析两家公司风险
   步骤: 5 个
   开始执行...

✅ 任务执行完成
   状态: completed
   进度: 5/5
```

## 与后端集成

### 后端 API 端点
- `POST /agent/planning-mode` - 执行规划模式

### 后端返回的事件类型
- `planning_start` - 规划开始
- `dag_generated` - DAG 生成
- `execution_start` - 执行开始
- `execution_complete` - 执行完成
- `error` - 错误

## 技术特点

### 1. 响应式设计
- 三列网格布局自适应
- 移动端友好的交互体验

### 2. 实时反馈
- SSE 流式推送执行进度
- 分块渲染，不阻塞 UI

### 3. 灵活配置
- 可自定义规划 agent
- 可指定可用的执行 agents
- 支持调整并发数

### 4. 错误处理
- 完善的错误提示
- 连接异常自动重试
- 状态一致性保证

## 注意事项

1. **Plan Agent 必须存在**
   - 默认使用 `plan_agent`
   - 确保该 agent 已在系统中创建
   - 该 agent 必须能够生成 JSON 格式的 DAG

2. **可用 Agents**
   - 如果不指定，使用所有用户的 agents
   - 指定后仅在这些 agents 中选择
   - 确保选择的 agents 能完成任务

3. **并发控制**
   - 默认最大并发数为 5
   - 可根据系统性能调整
   - 避免过高并发导致资源耗尽

## 未来优化方向

1. **DAG 可视化**
   - 显示任务依赖关系图
   - 实时更新执行状态

2. **历史记录**
   - 保存 DAG 执行历史
   - 支持重放和分析

3. **模板管理**
   - 保存常用任务模板
   - 快速启动相似任务

4. **实时编辑**
   - 执行过程中调整 DAG
   - 人工介入决策

## 总结

任务规划模式为用户提供了一个强大的自动化工具，能够将复杂的多步骤任务自动分解、规划和执行。通过直观的界面和实时反馈，用户可以轻松完成复杂的工作流，大大提高了生产力。
