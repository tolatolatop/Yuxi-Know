"""通用的 Context 相关中间件"""

from collections.abc import Callable

from langchain.agents.middleware import ModelRequest, ModelResponse, dynamic_prompt, wrap_model_call

from src.agents.common import load_chat_model
from src.utils import logger


@dynamic_prompt
def context_aware_prompt(request: ModelRequest) -> str:
    """从 runtime context 动态生成系统提示词"""
    return request.runtime.context.system_prompt


def _build_user_context_prompt(request: ModelRequest) -> str | None:
    """构造用户信息提示词块"""
    context = request.runtime.context
    user_id = getattr(context, "user_id", None)
    username = getattr(context, "username", None)
    user_role = getattr(context, "user_role", None)

    if not (user_id or username or user_role):
        return None

    lines = ["以下为当前用户信息："]
    if user_id:
        lines.append(f"- user_id: {user_id}")
    if username:
        lines.append(f"- username: {username}")
    if user_role:
        lines.append(f"- user_role: {user_role}")
    return "\n".join(lines)


@wrap_model_call
async def inject_user_context(request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
    """将运行时用户信息注入到系统提示中"""
    user_prompt = _build_user_context_prompt(request)
    if user_prompt:
        messages = [
            {"role": "system", "content": user_prompt},
            *request.messages,
        ]
        request = request.override(messages=messages)
    return await handler(request)


@wrap_model_call
async def context_based_model(request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
    """从 runtime context 动态选择模型"""
    model_spec = request.runtime.context.model
    model = load_chat_model(model_spec)

    request = request.override(model=model)
    logger.debug(f"Using model {model_spec} for request {request.messages[-1].content[:200]}")
    return await handler(request)
