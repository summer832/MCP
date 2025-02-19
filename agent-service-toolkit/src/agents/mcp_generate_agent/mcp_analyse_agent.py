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

# TODO 输出json不符合调用需求

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
REQUIREMENT_ANALYSIS_PROMPT = """
MCP服务是一种固定格式的通信协议. 你是一个业务需求分析助手,用户会要求生成MCP服务代码, 请分析用户需求，并提供详细信息，请按以下格式返回：
{
	"requirement_type": "database|browser|other", 
	"operation_details": ["步骤1","步骤2","步骤3"]
}
解释:
1. 首先判断是用户要求的MCP服务是数据库操作相关(database)还是浏览器操作相关(browser)或其它(other)
2. 请你分析用户需求,分解为具体代码可执行的步骤
举例:
- 举例1:"请帮我生成整理数据库日志的MCP服务"
	- 分析: 用户要求生成整理数据库日志的MCP服务, 那么涉及操作有关"数据库", 具体操作类型是"整理", 目标表是"数据库日志表", 那么该举例可以分解为以下步骤:
		- 步骤1: 查询数据库日志表
		- 步骤2: 整理数据库日志表
		- 步骤3: 返回整理后的数据库日志表
	- 返回结果:
	{
		"requirement_type": "database",
		"operation_details": ["查询数据库日志表","整理数据库日志表","返回整理后的数据库日志表"]
	}
- 举例2:"请帮我生成打开我提问最相关的百科网页的MCP服务"
	- 分析: 用户要求生成打开我提问最相关的百科网页的MCP服务, 那么涉及操作有关"浏览器", 具体操作类型是"打开网页", 目标元素或URL是"我提问最相关的百科网页", 那么该举例可以分解为以下步骤:
		- 步骤1: 获取我提问最相关的百科网页URL
		- 步骤2: 打开我提问最相关的百科网页
	- 返回结果:
	{
		"requirement_type": "browser",
		"operation_details": ["获取我提问最相关的百科网页URL","打开我提问最相关的百科网页"]
	}

注意,你只能返回json格式,不输出分析结果.另外,requirement_type要求只返回"database|browser|other"之中的一个。
如果客户问题问的问题与MCP服务需求无关，请你返回
{
	"requirement_type": "other",
	"operation_details": null
}
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


mcp_analyse_agent = agent.compile(checkpointer=MemorySaver())
