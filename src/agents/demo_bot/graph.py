"""Project manager for the agent."""

import logging
from typing import TypedDict, Annotated, NotRequired
from langchain.agents import create_agent
from langchain.agents import AgentState
from langgraph.types import Command
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware import ModelRetryMiddleware
from langchain.tools import ToolRuntime, tool
from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain.messages import ToolMessage
from langgraph.types import interrupt

from collections.abc import Callable

from src.agents.common import BaseAgent, load_chat_model
from src.agents.common.tools import get_tools_from_context

logger = logging.getLogger("Yuxi.project_manager")


class QualityMetric(TypedDict):
    name: str
    value: float


class ProjectState(AgentState):
    project_id: NotRequired[str]
    quality_metrics: NotRequired[list[QualityMetric]]


def query_quality_metrics(project_id: str) -> list[QualityMetric]:
    return [
        {
            "name": "quality_metric_1",
            "value": 0.95,
        },
        {
            "name": "quality_metric_2",
            "value": 0.90,
        },
    ]


@tool
def set_project_id(project_id: str, runtime: ToolRuntime) -> Command:
    """Set the project ID."""
    tool_call_id = runtime.tool_call_id

    return Command(
        update={
            "messages": [
                ToolMessage(
                    content="Project ID set successfully.",
                    tool_call_id=tool_call_id,  # Links back to AIMessage tool call
                )
            ],
            "project_id": project_id,
            "quality_metrics": query_quality_metrics(project_id),
        }
    )


@tool
def update_quality_metrics(runtime: ToolRuntime) -> Command:
    """Update the quality metrics."""
    ans = interrupt("是否更新质量指标？")
    tool_call_id = runtime.tool_call_id
    if "no" in ans.lower():
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content="Quality metrics not updated.",
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content="Quality metrics updated successfully.",
                    tool_call_id=tool_call_id,
                )
            ],
            "quality_metrics": query_quality_metrics(runtime.state["project_id"]),
        }
    )


@tool
def query_project_id(name: str) -> str:
    """Query the project ID."""
    if name == "NewTown":
        return "1234567890"
    elif name == "NewStone":
        return "0987654321"
    return "Project ID not found."


class ProjectMiddleware(AgentMiddleware[ProjectState]):
    state_schema = ProjectState

    async def awrap_model_call(
        self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
    ) -> ModelResponse:
        logger.info(f"ProjectMiddleware: request.state = {request.state.get('project_id')}")
        return await handler(request)


class DemoBotAgent(BaseAgent):
    name = "项目管理助手"
    description = "一个用于管理项目的智能体，可以回答问题，可在配置中启用需要的工具。"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def get_graph(self, **kwargs):
        """构建图"""
        if self.graph:
            return self.graph

        # 获取上下文配置
        context = self.context_schema.from_file(module_name=self.module_name)
        context_tools = await get_tools_from_context(context)
        tools = context_tools + [set_project_id, update_quality_metrics, query_project_id]

        # 使用 create_agent 创建智能体
        graph = create_agent(
            model=load_chat_model(context.model),  # 使用 context 中的模型配置
            tools=tools,
            system_prompt=context.system_prompt,
            middleware=[
                ModelRetryMiddleware(),  # 模型重试中间件
                ProjectMiddleware(),
            ],
            checkpointer=await self._get_checkpointer(),
        )

        self.graph = graph
        return graph


def main():
    pass


if __name__ == "__main__":
    main()
    # asyncio.run(main())
