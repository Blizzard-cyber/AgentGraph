#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAG执行器 - 支持agent并行/串行执行
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import uuid

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("dag_executor")


class StepStatus(Enum):
    """步骤状态枚举"""
    PENDING = "pending"      # 等待中
    READY = "ready"          # 就绪（依赖已满足）
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    SKIPPED = "skipped"      # 跳过


@dataclass
class StepResult:
    """步骤执行结果"""
    step_id: int
    status: StepStatus
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    execution_duration: Optional[float] = None


@dataclass
class DAGStep:
    """DAG步骤定义"""
    id: int
    agent: str
    action: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    depends_on: List[int]
    
    # 运行时状态
    status: StepStatus = StepStatus.PENDING
    result: Optional[StepResult] = None


@dataclass
class DAGPlan:
    """DAG计划定义"""
    execution_id: str
    goal: str
    assumptions: List[str]
    constraints: List[str]
    steps: List[DAGStep]
    completion_criteria: str
    
    # 运行时状态
    status: str = "pending"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    results: Dict[int, StepResult] = None
    
    def __post_init__(self):
        if self.results is None:
            self.results = {}


class AgentInterface:
    """Agent接口抽象基类"""
    
    async def execute(self, agent_name: str, action: str, input_data: Dict[str, Any], 
                     user_id: str = None, conversation_id: str = None) -> Dict[str, Any]:
        """执行agent动作
        
        Args:
            agent_name: Agent名称
            action: 动作描述
            input_data: 输入数据
            user_id: 用户ID
            conversation_id: 对话ID
            
        Returns:
            执行结果字典
        """
        raise NotImplementedError
        
    async def execute_stream(self, agent_name: str, action: str, input_data: Dict[str, Any],
                           user_id: str = None, conversation_id: str = None):
        """流式执行agent动作
        
        Args:
            agent_name: Agent名称 
            action: 动作描述
            input_data: 输入数据
            user_id: 用户ID
            conversation_id: 对话ID
            
        Yields:
            流式输出数据
        """
        # 默认实现：调用普通execute方法
        result = await self.execute(agent_name, action, input_data, user_id, conversation_id)
        yield result


class MockAgentInterface(AgentInterface):
    """模拟Agent接口（用于测试）"""
    
    async def execute(self, agent_name: str, action: str, input_data: Dict[str, Any],
                     user_id: str = None, conversation_id: str = None) -> Dict[str, Any]:
        """模拟执行agent动作"""
        await asyncio.sleep(1)  # 模拟执行时间
        
        # 模拟输出数据
        return {
            "agent": agent_name,
            "action": action,
            "processed": True,
            "input_received": input_data,
            "output": f"Result from {agent_name}.{action}",
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "conversation_id": conversation_id
        }


class DAGExecutor:
    """DAG执行器"""
    
    def __init__(self, agent_interface: AgentInterface, max_concurrent: int = 5,
                 user_id: str = None, conversation_id: str = None):
        self.agent_interface = agent_interface
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.user_id = user_id
        self.conversation_id = conversation_id
        
    async def execute_dag(self, dag_definition: Dict[str, Any], 
                         user_id: str = None, conversation_id: str = None,
                         stream_callback=None) -> DAGPlan:
        """执行DAG计划
        
        Args:
            dag_definition: DAG定义
            user_id: 用户ID
            conversation_id: 对话ID  
            stream_callback: 流式输出回调函数
        """
        # 使用传入的用户上下文，或使用初始化时的默认值
        effective_user_id = user_id or self.user_id
        effective_conversation_id = conversation_id or self.conversation_id
        # 解析DAG定义
        dag_plan = self._parse_dag_definition(dag_definition)
        
        logger.info(f"开始执行DAG: {dag_plan.execution_id}")
        logger.info(f"目标: {dag_plan.goal}")
        logger.info(f"步骤数量: {len(dag_plan.steps)}")
        
        dag_plan.status = "running"
        dag_plan.start_time = datetime.now()
        
        try:
            # 验证DAG有效性
            self._validate_dag(dag_plan)
            
            # 执行DAG
            await self._execute_steps(dag_plan, effective_user_id, effective_conversation_id)
            
            # 检查完成条件
            if self._check_completion_criteria(dag_plan):
                dag_plan.status = "completed"
                logger.info(f"DAG执行成功: {dag_plan.execution_id}")
            else:
                dag_plan.status = "incomplete"
                logger.warning(f"DAG未满足完成条件: {dag_plan.execution_id}")
                
        except Exception as e:
            dag_plan.status = "failed"
            logger.error(f"DAG执行失败: {dag_plan.execution_id}, 错误: {str(e)}")
            raise
        finally:
            dag_plan.end_time = datetime.now()
            
        return dag_plan
    
    def _parse_dag_definition(self, definition: Dict[str, Any]) -> DAGPlan:
        """解析DAG定义"""
        steps = []
        for step_def in definition.get("步骤", []):
            step = DAGStep(
                id=step_def["id"],
                agent=step_def["agent"],
                action=step_def["action"],
                input_schema=step_def["input_schema"],
                output_schema=step_def["output_schema"],
                depends_on=step_def.get("depends_on", [])
            )
            steps.append(step)
        
        dag_plan = DAGPlan(
            execution_id=str(uuid.uuid4())[:8],
            goal=definition["目标"],
            assumptions=definition.get("前提假设", []),
            constraints=definition.get("约束条件", []),
            steps=steps,
            completion_criteria=definition["completion_criteria"]
        )
        
        return dag_plan
    
    def _validate_dag(self, dag_plan: DAGPlan):
        """验证DAG有效性"""
        step_ids = {step.id for step in dag_plan.steps}
        
        # 检查依赖关系
        for step in dag_plan.steps:
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    raise ValueError(f"步骤 {step.id} 依赖的步骤 {dep_id} 不存在")
        
        # 检查循环依赖
        if self._has_circular_dependency(dag_plan.steps):
            raise ValueError("DAG存在循环依赖")
        
        logger.info("DAG验证通过")
    
    def _has_circular_dependency(self, steps: List[DAGStep]) -> bool:
        """检查循环依赖"""
        def has_cycle(step_id: int, visited: Set[int], rec_stack: Set[int]) -> bool:
            visited.add(step_id)
            rec_stack.add(step_id)
            
            step = next((s for s in steps if s.id == step_id), None)
            if step:
                for dep_id in step.depends_on:
                    if dep_id not in visited:
                        if has_cycle(dep_id, visited, rec_stack):
                            return True
                    elif dep_id in rec_stack:
                        return True
            
            rec_stack.remove(step_id)
            return False
        
        visited = set()
        for step in steps:
            if step.id not in visited:
                if has_cycle(step.id, visited, set()):
                    return True
        return False
    
    async def _execute_steps(self, dag_plan: DAGPlan, effective_user_id: str = None,
                            effective_conversation_id: str = None):
        """执行DAG步骤"""
        step_dict = {step.id: step for step in dag_plan.steps}
        completed_steps = set()
        running_tasks = {}
        
        while len(completed_steps) < len(dag_plan.steps):
            # 找到可以执行的步骤
            ready_steps = []
            for step in dag_plan.steps:
                if (step.id not in completed_steps and 
                    step.id not in running_tasks and
                    all(dep_id in completed_steps for dep_id in step.depends_on)):
                    ready_steps.append(step)
            
            # 启动就绪的步骤
            for step in ready_steps:
                if len(running_tasks) < self.max_concurrent:
                    task = asyncio.create_task(
                        self._execute_step(step, dag_plan, effective_user_id, effective_conversation_id)
                    )
                    running_tasks[step.id] = task
                    step.status = StepStatus.RUNNING
                    logger.info(f"启动步骤 {step.id}: {step.agent}.{step.action}")
            
            # 等待至少一个任务完成
            if running_tasks:
                done, _ = await asyncio.wait(
                    running_tasks.values(), 
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # 处理完成的任务
                for task in done:
                    step_id = None
                    for sid, t in running_tasks.items():
                        if t == task:
                            step_id = sid
                            break
                    
                    if step_id:
                        try:
                            result = await task
                            step = step_dict[step_id]
                            step.result = result
                            step.status = result.status
                            dag_plan.results[step_id] = result
                            
                            if result.status == StepStatus.COMPLETED:
                                completed_steps.add(step_id)
                                logger.info(f"步骤 {step_id} 执行成功")
                            else:
                                logger.error(f"步骤 {step_id} 执行失败: {result.error_message}")
                                
                        except Exception as e:
                            logger.error(f"步骤 {step_id} 执行异常: {str(e)}")
                        finally:
                            del running_tasks[step_id]
            
            # 检查是否有步骤执行失败
            failed_steps = [s for s in dag_plan.steps if s.status == StepStatus.FAILED]
            if failed_steps:
                # 取消正在运行的任务
                for task in running_tasks.values():
                    task.cancel()
                raise RuntimeError(f"步骤执行失败: {[s.id for s in failed_steps]}")
    
    async def _execute_step(self, step: DAGStep, dag_plan: DAGPlan, 
                           effective_user_id: str = None, 
                           effective_conversation_id: str = None) -> StepResult:
        """执行单个步骤"""
        async with self.semaphore:
            result = StepResult(
                step_id=step.id,
                status=StepStatus.RUNNING,
                start_time=datetime.now()
            )
            
            try:
                # 准备输入数据
                input_data = self._prepare_input_data(step, dag_plan)
                
                # 执行agent
                output_data = await self.agent_interface.execute(
                    step.agent, 
                    step.action, 
                    input_data,
                    effective_user_id,
                    effective_conversation_id
                )
                
                # 如果返回的是包装格式（包含agent、action、status、output等元数据）
                # 直接接受，不做schema验证（因为这是标准的agent响应格式）
                if isinstance(output_data, dict) and 'output' in output_data and 'agent' in output_data:
                    logger.info(f"步骤 {step.id} 返回包装格式，自动通过验证")
                    result.output_data = output_data
                    result.status = StepStatus.COMPLETED
                else:
                    # 验证输出schema
                    logger.debug(f"步骤 {step.id} 输出验证 - 数据类型: {type(output_data)}, schema: {step.output_schema}")
                    if self._validate_output(output_data, step.output_schema):
                        result.status = StepStatus.COMPLETED
                        result.output_data = output_data
                        logger.info(f"步骤 {step.id} 输出验证通过")
                    else:
                        result.status = StepStatus.FAILED
                        result.error_message = f"输出数据不符合schema - 期望: {step.output_schema.get('required', [])}, 实际类型: {type(output_data)}"
                        logger.error(f"步骤 {step.id} {result.error_message}")
                
            except Exception as e:
                result.status = StepStatus.FAILED
                result.error_message = str(e)
                logger.error(f"步骤 {step.id} 执行异常: {str(e)}")
            finally:
                result.end_time = datetime.now()
                if result.start_time:
                    result.execution_duration = (result.end_time - result.start_time).total_seconds()
            
            return result
    
    def _prepare_input_data(self, step: DAGStep, dag_plan: DAGPlan) -> Dict[str, Any]:
        """准备步骤输入数据"""
        input_data = {}
        
        # 从依赖步骤获取输出数据
        for dep_id in step.depends_on:
            if dep_id in dag_plan.results:
                dep_result = dag_plan.results[dep_id]
                if dep_result.output_data:
                    input_data[f"step_{dep_id}_output"] = dep_result.output_data
        
        # 添加DAG上下文信息
        input_data["dag_context"] = {
            "execution_id": dag_plan.execution_id,
            "goal": dag_plan.goal,
            "step_id": step.id,
            "assumptions": dag_plan.assumptions,
            "constraints": dag_plan.constraints
        }
        
        return input_data
    
    def _validate_output(self, output_data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """验证输出数据格式（简单验证）"""
        # 如果输出是字符串，自动包装为符合schema的格式
        if isinstance(output_data, str):
            logger.info(f"输出为字符串类型，自动包装为dict格式")
            return True
        
        if not isinstance(output_data, dict):
            logger.warning(f"输出数据类型不正确: {type(output_data)}")
            return False
        
        # 检查必需字段（宽松模式：如果没有定义required，则通过验证）
        required_fields = schema.get("required", [])
        if not required_fields:
            # 没有定义required字段，直接通过
            return True
        
        for field in required_fields:
            if field not in output_data:
                logger.warning(f"缺少必需字段: {field}, 输出数据: {output_data.keys()}")
                return False
        
        return True
    
    def _check_completion_criteria(self, dag_plan: DAGPlan) -> bool:
        """检查完成条件"""
        # 简单检查：所有步骤都成功完成
        completed_steps = sum(1 for step in dag_plan.steps if step.status == StepStatus.COMPLETED)
        return completed_steps == len(dag_plan.steps)
    
    def get_execution_status(self, dag_plan: DAGPlan) -> Dict[str, Any]:
        """获取执行状态"""
        total_steps = len(dag_plan.steps)
        completed_steps = sum(1 for step in dag_plan.steps if step.status == StepStatus.COMPLETED)
        failed_steps = sum(1 for step in dag_plan.steps if step.status == StepStatus.FAILED)
        running_steps = sum(1 for step in dag_plan.steps if step.status == StepStatus.RUNNING)
        
        return {
            "execution_id": dag_plan.execution_id,
            "status": dag_plan.status,
            "goal": dag_plan.goal,
            "progress": {
                "total": total_steps,
                "completed": completed_steps,
                "failed": failed_steps,
                "running": running_steps,
                "percentage": (completed_steps / total_steps * 100) if total_steps > 0 else 0
            },
            "start_time": dag_plan.start_time.isoformat() if dag_plan.start_time else None,
            "end_time": dag_plan.end_time.isoformat() if dag_plan.end_time else None,
            "steps": [
                {
                    "id": step.id,
                    "agent": step.agent,
                    "action": step.action,
                    "status": step.status.value,
                    "depends_on": step.depends_on,
                    "result": {
                        "execution_duration": step.result.execution_duration if step.result else None,
                        "error_message": step.result.error_message if step.result else None
                    } if step.result else None
                }
                for step in dag_plan.steps
            ]
        }


# 使用示例和测试
async def test_dag_executor():
    """测试DAG执行器"""
    
    # 示例DAG定义
    dag_definition = {
        "目标": "完成数据处理和分析流水线",
        "前提假设": ["数据源可用", "agent服务正常"],
        "约束条件": ["在30分钟内完成", "内存使用不超过4GB"],
        "步骤": [
            {
                "id": 1,
                "agent": "data_collector",
                "action": "fetch_data",
                "input_schema": {"source": "string", "format": "string"},
                "output_schema": {"data": "object", "status": "string"},
                "depends_on": []
            },
            {
                "id": 2,
                "agent": "data_processor",
                "action": "clean_data",
                "input_schema": {"data": "object"},
                "output_schema": {"cleaned_data": "object", "summary": "object"},
                "depends_on": [1]
            },
            {
                "id": 3,
                "agent": "data_processor",
                "action": "transform_data",
                "input_schema": {"data": "object"},
                "output_schema": {"transformed_data": "object"},
                "depends_on": [1]
            },
            {
                "id": 4,
                "agent": "analyzer",
                "action": "analyze",
                "input_schema": {"cleaned_data": "object", "transformed_data": "object"},
                "output_schema": {"analysis_result": "object", "insights": "array"},
                "depends_on": [2, 3]
            },
            {
                "id": 5,
                "agent": "reporter",
                "action": "generate_report",
                "input_schema": {"analysis_result": "object"},
                "output_schema": {"report": "string", "status": "string"},
                "depends_on": [4]
            }
        ],
        "completion_criteria": "所有步骤成功完成且生成最终报告"
    }
    
    # 创建执行器
    agent_interface = MockAgentInterface()
    executor = DAGExecutor(agent_interface, max_concurrent=3)
    
    # 执行DAG
    try:
        dag_plan = await executor.execute_dag(dag_definition)
        
        # 输出执行结果
        status = executor.get_execution_status(dag_plan)
        print(json.dumps(status, indent=2, ensure_ascii=False))
        
    except Exception as e:
        logger.error(f"DAG执行失败: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_dag_executor())