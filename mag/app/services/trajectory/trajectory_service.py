"""
轨迹数据收集和上传服务
用于收集Agent执行过程中的轨迹数据，用于后训练
"""

import json
import logging
import asyncio
from typing import Dict, List, Any, Optional
import aiohttp
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)


class TrajectoryService:
    """轨迹数据收集和上传服务"""

    def __init__(
        self,
        api_host: str = "192.168.1.86",
        api_port: int = 8226,
        single_agent_path: str = "/trajectory/uploadSingleAgentTrajectory",
        multi_agent_path: str = "/trajectory/uploadMultiAgentTrajectory",
        enabled: bool = True,
        use_https: bool = False,
    ):
        """
        初始化轨迹服务

        Args:
            api_host: API服务器主机
            api_port: API服务器端口
            single_agent_path: 单Agent轨迹API路径
            multi_agent_path: 多Agent轨迹API路径
            enabled: 是否启用轨迹收集
            use_https: 是否使用HTTPS
        """
        self.api_host = api_host
        self.api_port = api_port
        self.single_agent_path = single_agent_path
        self.multi_agent_path = multi_agent_path
        self.enabled = enabled
        self.use_https = use_https
        self.protocol = "https" if use_https else "http"
        self.single_agent_url = f"{self.protocol}://{api_host}:{api_port}{single_agent_path}"
        self.multi_agent_url = f"{self.protocol}://{api_host}:{api_port}{multi_agent_path}"

    def create_trajectory_collector(
        self,
        agent_id: str,
        user_id: str,
        query: str,
    ) -> "TrajectoryCollector":
        """
        创建单Agent轨迹收集器

        Args:
            agent_id: Agent ID
            user_id: 用户ID
            query: 用户查询

        Returns:
            轨迹收集器实例
        """
        return TrajectoryCollector(
            agent_id=agent_id,
            user_id=user_id,
            query=query,
            service=self,
        )

    def create_plan_trajectory_collector(
        self,
        plan_agent_id: str,
        user_id: str,
        query: str,
    ) -> "PlanTrajectoryCollector":
        """
        创建Plan模式多Agent轨迹收集器

        Args:
            plan_agent_id: Plan Agent ID
            user_id: 用户ID
            query: 用户查询

        Returns:
            Plan轨迹收集器实例
        """
        return PlanTrajectoryCollector(
            plan_agent_id=plan_agent_id,
            user_id=user_id,
            query=query,
            service=self,
        )

    async def upload_trajectory(self, trajectory_data: Dict[str, Any], is_plan_mode: bool = False) -> bool:
        """
        上传轨迹数据到服务器

        Args:
            trajectory_data: 轨迹数据
            is_plan_mode: 是否为Plan模式（多Agent）

        Returns:
            是否上传成功
        """
        if not self.enabled:
            logger.debug("轨迹收集功能未启用，跳过上传")
            return True

        try:
            # 将单个轨迹包装成列表
            payload = [trajectory_data]

            headers = {"Content-Type": "application/json"}

            # 选择对应的API URL
            api_url = self.multi_agent_url if is_plan_mode else self.single_agent_url
            agent_key = 'planAgentID' if is_plan_mode else 'agentID'
            
            logger.info(f"开始上传{'Plan模式' if is_plan_mode else '单Agent'}轨迹数据: {agent_key}={trajectory_data.get(agent_key)}, steps={len(trajectory_data.get('steps', []))}")

            # 使用aiohttp进行异步HTTP请求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    api_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                    ssl=False,  # 如果是内网环境，可以禁用SSL验证
                ) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        logger.info(f"轨迹数据上传成功: {response_text}")
                        return True
                    else:
                        logger.error(f"轨迹数据上传失败: status={response.status}, response={response_text}")
                        return False

        except asyncio.TimeoutError:
            logger.error(f"轨迹数据上传超时: url={self.api_url}")
            return False
        except Exception as e:
            logger.error(f"轨迹数据上传异常: {str(e)}", exc_info=True)
            return False


class TrajectoryCollector:
    """轨迹数据收集器"""

    def __init__(
        self,
        agent_id: str,
        user_id: str,
        query: str,
        service: TrajectoryService,
    ):
        """
        初始化轨迹收集器

        Args:
            agent_id: Agent ID
            user_id: 用户ID
            query: 用户查询
            service: 轨迹服务实例
        """
        self.agent_id = agent_id
        self.user_id = user_id
        self.query = query
        self.service = service
        self.steps: List[Dict[str, Any]] = []
        self.step_counter = 0

    def add_step(
        self,
        agent_name: str,
        thought: str,
        tool: str,
        output: Any,
        depend_on: Optional[List[int]] = None,
    ) -> int:
        """
        添加一个执行步骤

        Args:
            agent_name: Agent名称
            thought: Agent的思考过程
            tool: 使用的工具名称
            output: 工具输出结果
            depend_on: 依赖的步骤ID列表

        Returns:
            当前步骤的ID
        """
        self.step_counter += 1
        step_id = self.step_counter

        step = {
            "stepID": step_id,
            "agentName": agent_name,
            "thought": thought,
            "tool": tool,
            "output": output,
            "depend_on": depend_on or [],
        }

        self.steps.append(step)
        logger.debug(f"添加轨迹步骤 #{step_id}: tool={tool}, agent={agent_name}")

        return step_id

    def get_trajectory_data(self) -> Dict[str, Any]:
        """
        获取完整的轨迹数据

        Returns:
            轨迹数据字典
        """
        return {
            "agentID": self.agent_id,
            "userID": self.user_id,
            "query": self.query,
            "steps": self.steps,
        }

    async def upload(self) -> bool:
        """
        上传收集的轨迹数据

        Returns:
            是否上传成功
        """
        if not self.steps:
            logger.debug("没有轨迹步骤，跳过上传")
            return True

        trajectory_data = self.get_trajectory_data()
        return await self.service.upload_trajectory(trajectory_data)


class PlanTrajectoryCollector:
    """Plan模式多Agent轨迹数据收集器"""

    def __init__(
        self,
        plan_agent_id: str,
        user_id: str,
        query: str,
        service: TrajectoryService,
    ):
        """
        初始化Plan轨迹收集器

        Args:
            plan_agent_id: Plan Agent ID
            user_id: 用户ID
            query: 用户查询
            service: 轨迹服务实例
        """
        self.plan_agent_id = plan_agent_id
        self.user_id = user_id
        self.query = query
        self.service = service
        self.steps: List[Dict[str, Any]] = []
        self.step_counter = 0

    def add_step(
        self,
        agent_name: str,
        thought: str,
        tool: str,
        output: Any,
        depend_on: Optional[List[int]] = None,
    ) -> int:
        """
        添加一个执行步骤

        Args:
            agent_name: Agent名称
            thought: Agent的思考过程
            tool: 使用的工具名称
            output: 工具输出结果
            depend_on: 依赖的步骤ID列表

        Returns:
            当前步骤的ID
        """
        self.step_counter += 1
        step_id = self.step_counter

        step = {
            "stepID": step_id,
            "agentName": agent_name,
            "thought": thought,
            "tool": tool,
            "output": output,
            "depend_on": depend_on or [],
        }

        self.steps.append(step)
        logger.debug(f"添加Plan轨迹步骤 #{step_id}: tool={tool}, agent={agent_name}")

        return step_id

    def get_trajectory_data(self) -> Dict[str, Any]:
        """
        获取完整的Plan轨迹数据

        Returns:
            轨迹数据字典
        """
        return {
            "planAgentID": self.plan_agent_id,
            "userID": self.user_id,
            "query": self.query,
            "steps": self.steps,
        }

    async def upload(self) -> bool:
        """
        上传收集的Plan轨迹数据

        Returns:
            是否上传成功
        """
        if not self.steps:
            logger.debug("没有Plan轨迹步骤，跳过上传")
            return True

        trajectory_data = self.get_trajectory_data()
        return await self.service.upload_trajectory(trajectory_data, is_plan_mode=True)


# 全局轨迹服务实例（从配置读取）
trajectory_service = TrajectoryService(
    api_host=settings.TRAJECTORY_API_HOST,
    api_port=settings.TRAJECTORY_API_PORT,
    single_agent_path=settings.TRAJECTORY_SINGLE_AGENT_PATH,
    multi_agent_path=settings.TRAJECTORY_MULTI_AGENT_PATH,
    enabled=settings.TRAJECTORY_ENABLED,
    use_https=settings.TRAJECTORY_USE_HTTPS,
)
