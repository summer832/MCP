# MCP代码生成Main Agent

from typing import Literal, TypedDict, List
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda, RunnableSerializable
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, MessagesState, StateGraph

from core import get_model, settings
from agents.mcp_generate_agent.mcp_analyse_agent import mcp_analyse_agent
from agents.mcp_generate_agent.mcp_compose_agent import mcp_compose_agent

import os
import httpx
import json
import logging

# TODO 流程未测试, 循环调用未实现
# 配置日志
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AgentState(MessagesState, total=False):
	current_stage: Literal["analyze", "generate", "compose"]
	analysis_result: dict
	generated_code: str
	final_code: str

CONTROLLER_PROMPT = """
你是一个MCP服务代码生成的协调者。你需要协调以下流程:
1. 分析用户需求
2. 生成相应代码
3. 优化代码结构
请确保每个步骤都正确执行并产生预期的输出.
"""

# 包装模型
def wrap_model(model: BaseChatModel) -> RunnableSerializable[AgentState, AIMessage]:
	preprocessor = RunnableLambda(
		lambda state: [SystemMessage(content=CONTROLLER_PROMPT)] + state["messages"],
		name="StateModifier",
	)
	return preprocessor | model

# 调用模型
async def acall_model(state: AgentState, config: RunnableConfig) -> AgentState:
	m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
	model_runnable = wrap_model(m)
	response = await model_runnable.ainvoke(state, config)
	logger.info(response)
    
	return {
		"messages": state["messages"] + [response],
        "current_stage": "analyze"
	}
agent = StateGraph(AgentState)
agent.add_node("model", acall_model)
agent.set_entry_point("model")

# 需求分析
agent.add_node("analyze", mcp_analyse_agent.invoke)
agent.add_edge("generate", "analyze")

def analyse_route(state: AgentState) -> Literal["generate", "end"]:
	return "end" if not state.get("analysis_result") else "generate"

agent.add_conditional_edges(
	"analyze",
	analyse_route,
	{
		"generate": "generate",
		"end": END
	}
)

# 代码生成
async def generate_code(state: AgentState) -> AgentState:
    requirement_type = state["analysis_result"]["requirement_type"]
    operation_details = state["analysis_result"]["operation_details"]
    
    # 根据需求类型选择URL
    if requirement_type == "database":
        url = "https://reqres.in/"
    elif requirement_type == "browser":
        url = "https://reqres.in/"
    else:
        logger.info("不支持的需求类型")
        return {
            "messages": state["messages"] + [
                AIMessage(content="抱歉，目前只能处理数据库操作和浏览器操作相关的需求。")
            ],
            "current_stage": "end"
        }

    # 调用URL生成代码
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json={"messages": str(operation_details)})
            response.raise_for_status()
            generated_code = response.text
            
            # 将生成的代码写入文件
            output_file_path = "mcp_toolcall_test.txt"
            with open(output_file_path, "w") as file:
                file.write(generated_code)
            
            logger.info(f"生成的代码已写入文件: {output_file_path}")
            
            return {
                "messages": state["messages"],
                "generated_code": generated_code,
                "current_stage": "compose"
            }
            
        except httpx.HTTPError as e:
            logger.error(f"代码生成请求失败: {e}")
            return {
                "messages": state["messages"] + [
                    AIMessage(content="代码生成请求失败，请稍后重试。")
                ],
                "current_stage": "end"
            }
agent.add_node("generate", generate_code)

def generate_route(state: AgentState) -> Literal["compose", "end"]:
	return "end" if not state.get("generated_code") else "compose"
agent.add_conditional_edges(
	"generate",
	analyse_route,
	{
		"compose": "compose",
		"end": END
	}
)

# 代码整合
agent.add_node("compose", mcp_compose_agent.invoke)
agent.add_edge("compose", END)

mcp_generate_agent = agent.compile(checkpointer=MemorySaver())
