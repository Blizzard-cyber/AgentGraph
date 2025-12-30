#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAG执行服务 - 集成到主应用
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import uuid
from datetime import datetime

# 配置日志
logger = logging.getLogger("dag_service")

from .dag_executor import DAGExecutor, DAGPlan, AgentInterface
from .agent_stream_executor import AgentStreamExecutor

# 创建路由
dag_router = APIRouter(prefix="/api/dag", tags=["DAG Executor"])

# 全局变量存储执行状态
active_executions: Dict[str, DAGPlan] = {}
# 全局 AgentStreamExecutor 实例
agent_executor = AgentStreamExecutor()


class RealAgentInterface(AgentInterface):
    """真实的Agent接口实现 - 使用AgentStreamExecutor"""
    
    def __init__(self, agent_executor: AgentStreamExecutor = None):
        self.agent_executor = agent_executor or AgentStreamExecutor()
    
    async def execute(self, agent_name: str, action: str, input_data: Dict[str, Any],
                     user_id: str = None, conversation_id: str = None) -> Dict[str, Any]:
        """执行真实的agent动作"""
        try:
            # 为DAG执行创建临时对话ID
            temp_conversation_id = conversation_id or f"dag_{uuid.uuid4().hex[:8]}"
            
            # 构建用户提示，包含动作和输入数据
            user_prompt = f"执行动作: {action}\n输入数据: {json.dumps(input_data, ensure_ascii=False, indent=2)}"
            
            # 收集流式输出到最终结果
            final_result = None
            messages = []
            
            async for item in self.agent_executor.run_agent_stream(
                agent_name=agent_name,
                user_prompt=user_prompt,
                user_id=user_id or "dag_user",
                conversation_id=temp_conversation_id,
                max_iterations=10  # 限制迭代次数以避免过长执行
            ):
                if isinstance(item, str):
                    # SSE 字符串，解析并收集
                    if item.startswith("data: ") and not item.startswith("data: [DONE]"):
                        try:
                            data_str = item[6:].strip()
                            if data_str:
                                data = json.loads(data_str)
                                if data.get("role") == "assistant":
                                    messages.append(data)
                        except json.JSONDecodeError:
                            pass
                else:
                    # 最终结果字典
                    final_result = item
            
            # 提取助手的最终回复
            assistant_content = ""
            if final_result and "round_messages" in final_result:
                for msg in final_result["round_messages"]:
                    if msg.get("role") == "assistant" and msg.get("content"):
                        assistant_content += msg["content"] + "\n"
            
            return {
                "agent": agent_name,
                "action": action,
                "status": "success",
                "output": assistant_content.strip() or "执行完成",
                "input_processed": input_data,
                "timestamp": datetime.now().isoformat(),
                "execution_details": {
                    "conversation_id": temp_conversation_id,
                    "iterations": final_result.get("iteration_count", 0) if final_result else 0,
                    "token_usage": final_result.get("round_token_usage", {}) if final_result else {}
                }
            }
                
        except Exception as e:
            logger.error(f"Agent执行失败: {agent_name}.{action}, 错误: {str(e)}")
            return {
                "agent": agent_name,
                "action": action, 
                "status": "error",
                "error": str(e),
                "input_processed": input_data,
                "timestamp": datetime.now().isoformat()
            }
    
    async def execute_stream(self, agent_name: str, action: str, input_data: Dict[str, Any],
                           user_id: str = None, conversation_id: str = None):
        """流式执行agent动作"""
        temp_conversation_id = conversation_id or f"dag_{uuid.uuid4().hex[:8]}"
        user_prompt = f"执行动作: {action}\n输入数据: {json.dumps(input_data, ensure_ascii=False, indent=2)}"
        
        async for item in self.agent_executor.run_agent_stream(
            agent_name=agent_name,
            user_prompt=user_prompt,
            user_id=user_id or "dag_user",
            conversation_id=temp_conversation_id,
            max_iterations=10
        ):
            yield item


class DAGDefinition(BaseModel):
    """DAG定义模型"""
    目标: str = Field(..., description="执行目标")
    前提假设: list[str] = Field(default=[], description="前提假设列表")
    约束条件: list[str] = Field(default=[], description="约束条件列表") 
    步骤: list[Dict[str, Any]] = Field(..., description="执行步骤")
    completion_criteria: str = Field(..., description="完成标准")


class DAGExecutionRequest(BaseModel):
    """DAG执行请求"""
    dag_definition: DAGDefinition
    max_concurrent: int = Field(default=5, ge=1, le=20, description="最大并发数")
    execution_name: Optional[str] = Field(None, description="执行名称")
    user_id: Optional[str] = Field(None, description="用户ID")
    conversation_id: Optional[str] = Field(None, description="对话ID")


class DAGExecutionResponse(BaseModel):
    """DAG执行响应"""
    execution_id: str
    status: str
    message: str
    started_at: str


class DAGStatusResponse(BaseModel):
    """DAG状态响应"""
    execution_id: str
    status: str
    goal: str
    progress: Dict[str, Any]
    start_time: Optional[str]
    end_time: Optional[str]
    steps: list[Dict[str, Any]]


# 初始化DAG执行器
agent_interface = RealAgentInterface(agent_executor)


@dag_router.post("/execute", response_model=DAGExecutionResponse)
async def execute_dag(
    request: DAGExecutionRequest,
    background_tasks: BackgroundTasks
):
    """
    执行DAG计划
    """
    try:
        execution_id = str(uuid.uuid4())[:12]
        
        # 转换为执行器需要的格式
        dag_definition = request.dag_definition.model_dump()
        
        # 验证DAG定义
        if not dag_definition.get("步骤"):
            raise HTTPException(status_code=400, detail="DAG必须包含至少一个步骤")
        
        # 在后台执行DAG
        background_tasks.add_task(
            _execute_dag_background,
            execution_id,
            dag_definition,
            request.max_concurrent,
            request.user_id,
            request.conversation_id
        )
        
        return DAGExecutionResponse(
            execution_id=execution_id,
            status="started",
            message=f"DAG执行已启动: {request.execution_name or execution_id}",
            started_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动DAG执行失败: {str(e)}")


async def _execute_dag_background(
    execution_id: str,
    dag_definition: Dict[str, Any],
    max_concurrent: int,
    user_id: str = None,
    conversation_id: str = None
):
    """后台执行DAG"""
    try:
        # 创建新的执行器实例，传入用户上下文
        executor = DAGExecutor(
            agent_interface, 
            max_concurrent=max_concurrent,
            user_id=user_id,
            conversation_id=conversation_id
        )
        
        # 执行DAG
        dag_plan = await executor.execute_dag(
            dag_definition, 
            user_id=user_id, 
            conversation_id=conversation_id
        )
        dag_plan.execution_id = execution_id  # 使用自定义ID
        
        # 存储结果
        active_executions[execution_id] = dag_plan
        
    except Exception as e:
        logger.error(f"DAG后台执行失败: {execution_id}, 错误: {str(e)}")
        # 创建失败的DAG计划记录
        from .dag_executor import DAGPlan, StepStatus
        
        failed_plan = DAGPlan(
            execution_id=execution_id,
            goal=dag_definition.get("目标", "未知目标"),
            assumptions=dag_definition.get("前提假设", []),
            constraints=dag_definition.get("约束条件", []),
            steps=[],
            completion_criteria=dag_definition.get("completion_criteria", "")
        )
        failed_plan.status = "failed"
        failed_plan.start_time = datetime.now()
        failed_plan.end_time = datetime.now()
        
        active_executions[execution_id] = failed_plan


@dag_router.get("/status/{execution_id}", response_model=DAGStatusResponse)
async def get_dag_status(execution_id: str):
    """
    获取DAG执行状态
    """
    if execution_id not in active_executions:
        raise HTTPException(status_code=404, detail="执行ID不存在")
    
    dag_plan = active_executions[execution_id]
    status = dag_executor.get_execution_status(dag_plan)
    
    return DAGStatusResponse(**status)


@dag_router.get("/executions")
async def list_executions():
    """
    列出所有DAG执行
    """
    executions = []
    for execution_id, dag_plan in active_executions.items():
        executions.append({
            "execution_id": execution_id,
            "goal": dag_plan.goal,
            "status": dag_plan.status,
            "start_time": dag_plan.start_time.isoformat() if dag_plan.start_time else None,
            "end_time": dag_plan.end_time.isoformat() if dag_plan.end_time else None,
            "total_steps": len(dag_plan.steps),
            "completed_steps": sum(1 for s in dag_plan.steps if s.status.value == "completed")
        })
    
    return {
        "total": len(executions),
        "executions": executions
    }


@dag_router.delete("/execution/{execution_id}")
async def cancel_execution(execution_id: str):
    """
    取消DAG执行
    """
    if execution_id not in active_executions:
        raise HTTPException(status_code=404, detail="执行ID不存在")
    
    dag_plan = active_executions[execution_id]
    
    if dag_plan.status in ["completed", "failed"]:
        raise HTTPException(status_code=400, detail="执行已完成，无法取消")
    
    # 标记为取消状态（实际的取消逻辑需要在执行器中实现）
    dag_plan.status = "cancelled"
    dag_plan.end_time = datetime.now()
    
    return {"message": f"执行 {execution_id} 已取消"}


@dag_router.get("/template")
async def get_dag_template():
    """
    获取DAG定义模板
    """
    return {
        "目标": "描述要达成的目标",
        "前提假设": [
            "假设1：数据源可用",
            "假设2：相关服务正常运行"
        ],
        "约束条件": [
            "时间限制：30分钟内完成",
            "资源限制：内存使用不超过4GB"
        ],
        "步骤": [
            {
                "id": 1,
                "agent": "agent_name",
                "action": "action_name",
                "input_schema": {
                    "type": "object",
                    "required": ["param1"],
                    "properties": {
                        "param1": {"type": "string", "description": "参数说明"}
                    }
                },
                "output_schema": {
                    "type": "object", 
                    "required": ["result"],
                    "properties": {
                        "result": {"type": "string", "description": "输出说明"}
                    }
                },
                "depends_on": []
            }
        ],
        "completion_criteria": "所有步骤成功完成"
    }


@dag_router.get("/agents")
async def list_available_agents():
    """
    列出可用的agent
    """
    try:
        # 尝试从数据库获取真实的agent列表
        from app.infrastructure.database.mongodb.client import mongodb_client
        
        # 获取所有agent分类
        categories = await mongodb_client.agent_repository.list_agent_categories("system")
        
        agents_info = []
        for category in categories:
            agents = await mongodb_client.agent_repository.list_agents_in_category(
                user_id="system",
                category=category["category"]
            )
            
            for agent in agents:
                agents_info.append({
                    "name": agent["name"],
                    "description": f"{category['category']} Agent",
                    "category": category["category"],
                    "actions": ["execute", "analyze", "process"],  # 通用动作
                    "tags": agent.get("tags", [])
                })
        
        return {
            "agents": agents_info
        }
        
    except Exception as e:
        logger.warning(f"获取agent列表失败，返回默认列表: {str(e)}")
        # 如果获取真实agent失败，返回默认列表
        return {
            "agents": [
                {
                    "name": "plan_agent",
                    "description": "任务规划Agent",
                    "category": "planning",
                    "actions": ["plan", "analyze", "structure"]
                },
                {
                    "name": "RiskAnalyzeAgent",
                    "description": "风险分析Agent", 
                    "category": "work-agent",
                    "actions": ["analyze_risk", "assess_compliance", "generate_report"]
                },
                {
                    "name": "CompanySearchAgent",
                    "description": "公司搜索Agent",
                    "category": "work-agent", 
                    "actions": ["search_company", "fetch_data", "validate_info"]
                }
            ]
        }


# 导出路由以便在main.py中引入
__all__ = ["dag_router"]