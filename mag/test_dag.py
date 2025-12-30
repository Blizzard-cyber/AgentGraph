#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAG执行器测试脚本
"""

import asyncio
import json
import httpx
import time

async def test_dag_api():
    """测试DAG API"""
    base_url = "http://localhost:9999/api/dag"
    
    # 1. 获取DAG模板
    print("=== 1. 获取DAG模板 ===")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/template")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    
    # 2. 获取可用的agent
    print("\n=== 2. 获取可用agent ===")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/agents")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    
    # 3. 创建并执行DAG
    print("\n=== 3. 执行DAG ===")
    dag_definition = {
        "目标": "完成数据处理流水线测试",
        "前提假设": ["测试环境可用", "模拟数据已准备"],
        "约束条件": ["5分钟内完成", "并发不超过3个步骤"],
        "步骤": [
            {
                "id": 1,
                "agent": "data_collector",
                "action": "fetch_data",
                "input_schema": {"source": "string"},
                "output_schema": {"data": "object"},
                "depends_on": []
            },
            {
                "id": 2,
                "agent": "data_processor",
                "action": "clean_data",
                "input_schema": {"data": "object"},
                "output_schema": {"cleaned_data": "object"},
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
                "output_schema": {"analysis_result": "object"},
                "depends_on": [2, 3]
            },
            {
                "id": 5,
                "agent": "reporter",
                "action": "generate_report",
                "input_schema": {"analysis_result": "object"},
                "output_schema": {"report": "string"},
                "depends_on": [4]
            }
        ],
        "completion_criteria": "生成最终分析报告"
    }
    
    request_data = {
        "dag_definition": dag_definition,
        "max_concurrent": 3,
        "execution_name": "测试数据流水线"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{base_url}/execute", json=request_data)
        execution_result = response.json()
        print(json.dumps(execution_result, indent=2, ensure_ascii=False))
        
        execution_id = execution_result["execution_id"]
        
        # 4. 监控执行状态
        print(f"\n=== 4. 监控执行状态 (ID: {execution_id}) ===")
        
        for i in range(20):  # 最多检查20次
            await asyncio.sleep(2)  # 等待2秒
            
            status_response = await client.get(f"{base_url}/status/{execution_id}")
            status = status_response.json()
            
            print(f"\n--- 检查 {i+1} ---")
            print(f"状态: {status['status']}")
            print(f"进度: {status['progress']['completed']}/{status['progress']['total']} ({status['progress']['percentage']:.1f}%)")
            
            # 显示步骤状态
            for step in status['steps']:
                step_status = step['status']
                duration = step.get('result', {}).get('execution_duration')
                duration_str = f" ({duration:.2f}s)" if duration else ""
                print(f"  步骤 {step['id']}: {step['agent']}.{step['action']} - {step_status}{duration_str}")
            
            if status['status'] in ['completed', 'failed', 'cancelled']:
                print(f"\n执行完成，最终状态: {status['status']}")
                break
        
        # 5. 列出所有执行
        print("\n=== 5. 所有执行记录 ===")
        list_response = await client.get(f"{base_url}/executions")
        executions = list_response.json()
        print(json.dumps(executions, indent=2, ensure_ascii=False))


async def test_local_dag():
    """本地测试DAG执行器"""
    print("=== 本地DAG执行器测试 ===")
    
    from dag_executor import DAGExecutor, MockAgentInterface
    
    dag_definition = {
        "目标": "本地测试流水线",
        "前提假设": ["本地环境可用"],
        "约束条件": ["快速执行"],
        "步骤": [
            {
                "id": 1,
                "agent": "step1_agent",
                "action": "init",
                "input_schema": {},
                "output_schema": {"result": "string"},
                "depends_on": []
            },
            {
                "id": 2,
                "agent": "step2_agent", 
                "action": "process",
                "input_schema": {"input": "string"},
                "output_schema": {"processed": "string"},
                "depends_on": [1]
            },
            {
                "id": 3,
                "agent": "step3_agent",
                "action": "finalize", 
                "input_schema": {"processed": "string"},
                "output_schema": {"final": "string"},
                "depends_on": [2]
            }
        ],
        "completion_criteria": "所有步骤完成"
    }
    
    # 创建执行器
    agent_interface = MockAgentInterface()
    executor = DAGExecutor(agent_interface, max_concurrent=2)
    
    # 执行DAG
    dag_plan = await executor.execute_dag(dag_definition)
    
    # 输出结果
    status = executor.get_execution_status(dag_plan)
    print(json.dumps(status, indent=2, ensure_ascii=False))


async def main():
    """主测试函数"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "local":
        await test_local_dag()
    else:
        try:
            await test_dag_api()
        except Exception as e:
            print(f"API测试失败: {e}")
            print("可能服务器未启动，尝试本地测试...")
            await test_local_dag()


if __name__ == "__main__":
    asyncio.run(main())