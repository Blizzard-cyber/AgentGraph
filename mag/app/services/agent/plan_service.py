#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务规划服务 - 使用plan_agent生成DAG并执行
"""

import asyncio
import json
import logging
import re
from typing import Dict, Any, Optional, AsyncGenerator
from datetime import datetime
import uuid

from .agent_stream_executor import AgentStreamExecutor
from .dag_executor import DAGExecutor
from .dag_service import RealAgentInterface

logger = logging.getLogger("plan_service")


class PlanService:
    """任务规划服务"""
    
    def __init__(self):
        self.agent_executor = AgentStreamExecutor()
        self.agent_interface = RealAgentInterface(self.agent_executor)
    
    async def generate_dag_from_query(
        self, 
        user_query: str,
        user_id: str,
        conversation_id: str,
        available_agents: list[Dict[str, Any]] = None,
        plan_agent_name: str = "plan_agent"
    ) -> Dict[str, Any]:
        """
        使用plan_agent根据用户查询生成DAG计划
        
        Args:
            user_query: 用户查询
            user_id: 用户ID
            conversation_id: 对话ID
            available_agents: 可用的agent列表
            plan_agent_name: 规划agent的名称，默认为"plan_agent"
            
        Returns:
            DAG定义字典
        """
        try:
            # 构建规划提示
            planning_prompt = self._build_planning_prompt(user_query, available_agents)
            
            logger.info(f"开始任务规划（使用{plan_agent_name}），用户查询: {user_query[:100]}...")
            
            # 收集plan_agent的流式输出
            final_result = None
            assistant_content = ""
            
            async for item in self.agent_executor.run_agent_stream(
                agent_name=plan_agent_name,
                user_prompt=planning_prompt,
                user_id=user_id,
                conversation_id=conversation_id,
                max_iterations=5
            ):
                if isinstance(item, str):
                    # SSE 字符串
                    if item.startswith("data: ") and not item.startswith("data: [DONE]"):
                        try:
                            data_str = item[6:].strip()
                            if data_str:
                                data = json.loads(data_str)
                                if data.get("role") == "assistant" and data.get("content"):
                                    assistant_content += data["content"]
                        except json.JSONDecodeError:
                            pass
                else:
                    # 最终结果
                    final_result = item
            
            # 从助手回复中提取DAG定义
            if final_result and "round_messages" in final_result:
                for msg in final_result["round_messages"]:
                    if msg.get("role") == "assistant" and msg.get("content"):
                        assistant_content += msg["content"]
            
            # 解析DAG定义
            dag_definition = self._parse_dag_from_response(assistant_content)
            
            logger.info(f"任务规划完成，生成 {len(dag_definition.get('步骤', []))} 个步骤")
            
            return dag_definition
            
        except Exception as e:
            logger.error(f"生成DAG计划失败: {str(e)}")
            raise
    
    def _build_planning_prompt(
        self, 
        user_query: str,
        available_agents: list[Dict[str, Any]] = None
    ) -> str:
        """构建规划提示"""
        
        # 可用agent信息
        agents_info = ""
        if available_agents:
            agents_info = "\n可用的Agent列表：\n"
            for agent in available_agents:
                agents_info += f"- {agent['name']}: {agent.get('description', '')}\n"
                agents_info += f"  类别: {agent.get('category', 'unknown')}\n"
                agents_info += f"  可用动作: {', '.join(agent.get('actions', []))}\n"
        
        prompt = f"""你是一个任务规划专家。请根据用户的需求，生成一个DAG（有向无环图）执行计划。

用户需求：
{user_query}

{agents_info}

请生成一个详细的DAG计划，包含以下内容：

1. **目标**：明确描述要达成的目标
2. **前提假设**：列出执行计划的前提条件
3. **约束条件**：列出时间、资源等约束
4. **步骤**：定义具体的执行步骤，每个步骤包括：
   - id: 步骤编号（从1开始）
   - agent: 使用的agent名称
   - action: 要执行的动作描述
   - input_schema: 输入数据结构
   - output_schema: 输出数据结构
   - depends_on: 依赖的步骤ID列表（空列表表示可以立即执行）
5. **completion_criteria**：完成标准

请以JSON格式输出，格式如下：

```json
{{
  "目标": "描述要达成的目标",
  "前提假设": ["假设1", "假设2"],
  "约束条件": ["约束1", "约束2"],
  "步骤": [
    {{
      "id": 1,
      "agent": "agent_name",
      "action": "执行的动作描述",
      "input_schema": {{
        "type": "object",
        "required": ["param1"],
        "properties": {{
          "param1": {{"type": "string", "description": "参数说明"}}
        }}
      }},
      "output_schema": {{
        "type": "object",
        "required": ["result"],
        "properties": {{
          "result": {{"type": "string", "description": "输出说明"}}
        }}
      }},
      "depends_on": []
    }}
  ],
  "completion_criteria": "所有步骤成功完成"
}}
```

注意事项：
1. 根据步骤之间的依赖关系设置depends_on，没有依赖的步骤将并行执行
2. 有依赖关系的步骤将串行执行
3. 确保不会产生循环依赖
4. 选择合适的agent来执行每个步骤
5. 输入和输出schema要清晰明确

请现在生成DAG计划："""
        
        return prompt
    
    def _parse_dag_from_response(self, response: str) -> Dict[str, Any]:
        """从plan_agent的回复中解析DAG定义"""
        try:
            # 尝试提取JSON代码块
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                dag_definition = json.loads(json_str)
                return dag_definition
            
            # 尝试直接解析整个回复为JSON
            try:
                dag_definition = json.loads(response)
                return dag_definition
            except json.JSONDecodeError:
                pass
            
            # 尝试查找JSON对象
            json_match = re.search(r'\{.*"目标".*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                dag_definition = json.loads(json_str)
                return dag_definition
            
            # 解析失败，返回默认结构
            logger.warning("无法从回复中解析DAG定义，使用默认结构")
            return {
                "目标": "执行用户任务",
                "前提假设": ["Agent服务可用"],
                "约束条件": ["在合理时间内完成"],
                "步骤": [],
                "completion_criteria": "任务完成"
            }
            
        except Exception as e:
            logger.error(f"解析DAG定义失败: {str(e)}")
            raise ValueError(f"解析DAG定义失败: {str(e)}")
    
    async def execute_planning_mode(
        self,
        user_query: str,
        user_id: str,
        conversation_id: str,
        available_agents: list[Dict[str, Any]] = None,
        max_concurrent: int = 5,
        plan_agent_name: str = "plan_agent"
    ) -> AsyncGenerator[str, None]:
        """
        执行规划模式：生成DAG并执行
        
        Args:
            user_query: 用户查询
            user_id: 用户ID
            conversation_id: 对话ID
            available_agents: 可用的agent列表
            max_concurrent: 最大并发数
            plan_agent_name: 规划agent的名称，默认为"plan_agent"
            
        Yields:
            SSE格式的流式输出
        """
        try:
            execution_id = str(uuid.uuid4())[:12]
            
            # 阶段1：发送规划开始消息
            yield f"data: {json.dumps({'type': 'planning_start', 'message': f'开始任务规划（使用{plan_agent_name}）...', 'execution_id': execution_id}, ensure_ascii=False)}\n\n"
            
            # 阶段2：生成DAG计划
            dag_definition = await self.generate_dag_from_query(
                user_query,
                user_id,
                conversation_id,
                available_agents,
                plan_agent_name
            )
            
            # 发送DAG计划
            yield f"data: {json.dumps({'type': 'dag_generated', 'dag': dag_definition, 'execution_id': execution_id}, ensure_ascii=False)}\n\n"
            
            # 阶段3：执行DAG
            yield f"data: {json.dumps({'type': 'execution_start', 'message': '开始执行任务...', 'execution_id': execution_id}, ensure_ascii=False)}\n\n"
            
            # 创建DAG执行器
            executor = DAGExecutor(
                self.agent_interface,
                max_concurrent=max_concurrent,
                user_id=user_id,
                conversation_id=conversation_id
            )
            
            # 异步执行DAG
            dag_plan = await executor.execute_dag(
                dag_definition,
                user_id=user_id,
                conversation_id=conversation_id
            )
            
            # 阶段4：发送执行结果
            status = executor.get_execution_status(dag_plan)
            yield f"data: {json.dumps({'type': 'execution_complete', 'status': status, 'execution_id': execution_id}, ensure_ascii=False)}\n\n"
            
            # 发送完成标记
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"规划模式执行失败: {str(e)}")
            error_msg = {
                'type': 'error',
                'message': f'执行失败: {str(e)}',
                'execution_id': execution_id if 'execution_id' in locals() else 'unknown'
            }
            yield f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"


# 全局实例
plan_service = PlanService()
