# MCP代码生成Main Agent

from typing import Literal, TypedDict, List
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda, RunnableSerializable
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, MessagesState, StateGraph

from core import get_model, settings

import os
import httpx
import json
import logging

# TODO 代码未实现

# 配置日志
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AgentState(MessagesState, total=False):
	requirement_type: Literal["database", "browser", "other"]
	operation_details: List[str]

# 构建工作流图
agent = StateGraph(AgentState)

# 步骤1：需求分析和分类
COMPOSE_PROMPT = 
"""

"""

# 包装模型
def wrap_model(model: BaseChatModel) -> RunnableSerializable[AgentState, AIMessage]:
	preprocessor = RunnableLambda(
		lambda state: [SystemMessage(content=REQUIREMENT_ANALYSIS_PROMPT)] + state["messages"],
		name="StateModifier",
	)
	return preprocessor | model

# 调用模型
async def acall_model(state: AgentState, config: RunnableConfig) -> AgentState:
	m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
	model_runnable = wrap_model(m)
	response = await model_runnable.ainvoke(state, config)
	logger.info(response)
	analysis_result = json.loads(response.content)
    
	return {
		"messages": state.get("messages", []) + [response],
        "operation_details": analysis_result["operation_details"],
		"requirement_type": analysis_result["requirement_type"]
	}

agent.add_node("model", acall_model)
agent.set_entry_point("model")


agent.add_node("tool", pending_tool_calls)
agent.add_edge("model", "tool")
agent.add_edge("analyze", END)

mcp_compose_agent = agent.compile(checkpointer=MemorySaver())
