# DAG执行器前端配置

## API端点

### 基础路径: `/api/dag`

### 可用端点:

1. **获取DAG模板**
   - `GET /api/dag/template`
   - 返回标准DAG定义模板

2. **获取可用Agent**
   - `GET /api/dag/agents`
   - 返回可用的agent列表和支持的action

3. **执行DAG**
   - `POST /api/dag/execute`
   - 请求体: `DAGExecutionRequest`
   - 返回: `DAGExecutionResponse`

4. **查看执行状态**
   - `GET /api/dag/status/{execution_id}`
   - 返回: `DAGStatusResponse`

5. **列出所有执行**
   - `GET /api/dag/executions`
   - 返回执行历史列表

6. **取消执行**
   - `DELETE /api/dag/execution/{execution_id}`

## 前端界面建议

### 1. DAG设计器
```html
<!-- DAG可视化设计界面 -->
<div id="dag-designer">
  <!-- 工具栏 -->
  <div class="toolbar">
    <button onclick="addStep()">添加步骤</button>
    <button onclick="validateDAG()">验证DAG</button>
    <button onclick="executeDAG()">执行DAG</button>
  </div>
  
  <!-- 画布区域 -->
  <div class="canvas" id="dag-canvas">
    <!-- 步骤节点和连线会在这里动态生成 -->
  </div>
  
  <!-- 属性面板 -->
  <div class="properties-panel">
    <h3>步骤属性</h3>
    <form id="step-form">
      <label>ID: <input type="number" name="id" required></label>
      <label>Agent: <select name="agent"></select></label>
      <label>Action: <select name="action"></select></label>
      <label>依赖步骤: <input type="text" name="depends_on" placeholder="1,2,3"></label>
    </form>
  </div>
</div>
```

### 2. 执行监控界面
```html
<!-- 执行监控界面 -->
<div id="execution-monitor">
  <div class="execution-header">
    <h2>DAG执行监控</h2>
    <div class="status-badge" id="overall-status">Running</div>
  </div>
  
  <div class="progress-section">
    <div class="progress-bar">
      <div class="progress-fill" style="width: 60%"></div>
    </div>
    <span class="progress-text">3/5 步骤完成 (60%)</span>
  </div>
  
  <div class="steps-list">
    <div class="step-item completed">
      <span class="step-id">1</span>
      <span class="step-name">data_collector.fetch_data</span>
      <span class="step-status">✓ 已完成</span>
      <span class="step-duration">2.3s</span>
    </div>
    <!-- 更多步骤... -->
  </div>
</div>
```

### 3. JavaScript交互代码
```javascript
// DAG执行器前端交互
class DAGManager {
  constructor(baseUrl = '/api/dag') {
    this.baseUrl = baseUrl;
    this.currentExecution = null;
  }
  
  async executeDAG(dagDefinition, maxConcurrent = 5) {
    const response = await fetch(`${this.baseUrl}/execute`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        dag_definition: dagDefinition,
        max_concurrent: maxConcurrent
      })
    });
    
    const result = await response.json();
    this.currentExecution = result.execution_id;
    return result;
  }
  
  async getStatus(executionId = this.currentExecution) {
    const response = await fetch(`${this.baseUrl}/status/${executionId}`);
    return await response.json();
  }
  
  async monitorExecution(executionId, callback) {
    const monitor = setInterval(async () => {
      try {
        const status = await this.getStatus(executionId);
        callback(status);
        
        if (['completed', 'failed', 'cancelled'].includes(status.status)) {
          clearInterval(monitor);
        }
      } catch (error) {
        console.error('监控失败:', error);
        clearInterval(monitor);
      }
    }, 2000);
    
    return monitor;
  }
}

// 使用示例
const dagManager = new DAGManager();

// 执行DAG
const dagDef = {
  "目标": "数据处理流水线",
  "前提假设": ["数据可用"],
  "约束条件": ["30分钟内完成"],
  "步骤": [...],
  "completion_criteria": "所有步骤完成"
};

dagManager.executeDAG(dagDef).then(result => {
  console.log('执行开始:', result);
  
  // 监控执行进度
  dagManager.monitorExecution(result.execution_id, (status) => {
    updateUI(status);
  });
});

function updateUI(status) {
  document.getElementById('overall-status').textContent = status.status;
  
  const progress = status.progress.percentage;
  document.querySelector('.progress-fill').style.width = `${progress}%`;
  document.querySelector('.progress-text').textContent = 
    `${status.progress.completed}/${status.progress.total} 步骤完成 (${progress.toFixed(1)}%)`;
}
```

## 使用流程

1. **设计DAG**: 在前端界面设计执行流程图
2. **配置步骤**: 为每个步骤选择agent和action，设置依赖关系
3. **验证DAG**: 检查DAG的有效性（无循环依赖等）
4. **执行DAG**: 提交到后端执行
5. **监控进度**: 实时查看执行状态和步骤进度
6. **查看结果**: 执行完成后查看输出结果

## 扩展功能

- **模板管理**: 保存和复用常用的DAG模板
- **历史记录**: 查看历史执行记录和结果
- **错误诊断**: 详细的错误信息和失败原因分析
- **资源监控**: 监控CPU、内存等资源使用情况
- **通知提醒**: 执行完成或失败时的通知功能