from typing import Literal, TypedDict, List
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda, RunnableSerializable
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, MessagesState, StateGraph

from core import get_model, settings
from .database import database_chain
from .browser_agent import browser_chain

import json
import logging

# 配置日志
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AgentState(MessagesState, total=False):
	requirement_type: Literal["database", "browser", "other"]
	operation_details: List[str] | None


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


def wrap_model(model: BaseChatModel) -> RunnableSerializable[AgentState, AIMessage]:
	preprocessor = RunnableLambda(
		lambda state: [SystemMessage(content=REQUIREMENT_ANALYSIS_PROMPT)] + state["messages"],
		name="StateModifier",
	)
	return preprocessor | model


async def acall_model(state: AgentState, config: RunnableConfig) -> AgentState:
	m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
	model_runnable = wrap_model(m)
	response = await model_runnable.ainvoke(state, config)

	# 解析返回的JSON
	analysis_result = json.loads(response.content)

	return {
		"messages": [response],
		"requirement_type": analysis_result["requirement_type"],
		"operation_details": analysis_result["operation_details"]
	}


async def analyze_requirement(state: AgentState, config: RunnableConfig) -> AgentState:
	logger.info("==== 开始需求分析 ====")
	result = await acall_model(state, config)
	logger.info("==== 需求分析完成 ====")
	return result

agent.add_node("analyze", analyze_requirement)
agent.set_entry_point("analyze")
# test
agent.add_edge("analyze", END)

# # 步骤2：代码实现
# async def implement_code(state: AgentState, config: RunnableConfig) -> AgentState:
# 	messages = state["messages"]
# 	requirement_type = state["requirement_type"]

# 	logger.info(f"\n==== 代码实现阶段 ====\n需求类型: {requirement_type}")

# 	# 根据需求类型调用不同的实现函数
# 	if requirement_type == "database":
# 		logger.info("调用数据库实现链")
# 		implementation_state = await database_chain.ainvoke({
# 			"messages": messages
# 		}, config)
# 	elif requirement_type == "browser":
# 		logger.info("调用浏览器实现链")
# 		implementation_state = await browser_chain.ainvoke({
# 			"messages": messages
# 		}, config)
# 	else:
# 		logger.warning("不支持的需求类型")
# 		return {
# 			"messages": [AIMessage(content="抱歉，目前我只能处理数据库操作和浏览器操作相关的需求。")]
# 		}

# 	logger.info(f"实现代码:\n{implementation_state['combined_code']}\n")
# 	return {
# 		**state,
# 		"code_implementation": implementation_state["combined_code"]
# 	}

# agent.add_node("implement", implement_code)
# agent.add_edge("analyze", "implement")

# # 步骤3：生成MCP框架代码
# MCP_FRAMEWORK_TEMPLATE = """
# #!/usr/bin/env node

# import { Server } from "@modelcontextprotocol/sdk/server/index.js";
# import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
# import {
#   CallToolRequestSchema,
#   ListToolsRequestSchema,
#   Tool,
# } from "@modelcontextprotocol/sdk/types.js";

# // Tool definitions
# const TOOLS = [] as const;  // 这里将插入工具定义

# // Server setup
# const server = new Server(
#   {
#     name: "mcp-server/custom",
#     version: "0.1.0",
#   },
#   {
#     capabilities: {
#       tools: {},
#     },
#   },
# );

# // Set up request handlers
# server.setRequestHandler(ListToolsRequestSchema, async () => ({
#   tools: TOOLS,
# }));

# server.setRequestHandler(CallToolRequestSchema, async (request) => {
#   try {
#     switch (request.params.name) {
#       // 这里将插入工具处理逻辑
#       default:
#         return {
#           content: [{
#             type: "text",
#             text: `Unknown tool: ${request.params.name}`
#           }],
#           isError: true
#         };
#     }
#   } catch (error) {
#     return {
#       content: [{
#         type: "text",
#         text: `Error: ${error instanceof Error ? error.message : String(error)}`
#       }],
#       isError: true
#     };
#   }
# });

# // Start server
# async function runServer() {
#   const transport = new StdioServerTransport();
#   await server.connect(transport);
#   console.error("MCP Server running on stdio");
# }

# runServer().catch((error) => {
#   console.error("Fatal error running server:", error);
#   process.exit(1);
# });
# """

# # 步骤4：代码测试
# async def generate_mcp_code(state: AgentState, config: RunnableConfig) -> AgentState:
# 	implementation = state["code_implementation"]

# 	logger.info("\n==== MCP框架代码生成阶段 ====")

# 	m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
# 	response = await m.ainvoke([
# 		HumanMessage(content=f"""
#         请将以下实现代码整合到MCP Server框架中：
#         {implementation}

#         MCP Server框架模板：
#         {MCP_FRAMEWORK_TEMPLATE}

#         请返回完整的MCP Server代码。
#         """)
# 	])

# 	logger.info(f"生成的MCP代码:\n{response.content}\n")

# 	return {
# 		**state,
# 		"mcp_code": response.content
# 	}

# agent.add_node("generate", generate_mcp_code)
# agent.add_edge("implement", "generate")


# async def test_code(state: AgentState, config: RunnableConfig) -> AgentState:
# 	mcp_code = state["mcp_code"]

# 	logger.info("\n==== 代码测试阶段 ====")

# 	# 这里预留测试工具接口
# 	test_result = "测试通过"  # 实际应该调用测试工具

# 	logger.info(f"测试结果: {test_result}\n")

# 	return {
# 		**state,
# 		"test_feedback": test_result
# 	}
# agent.add_node("test", test_code)
# agent.add_edge("generate", "test")

# # 步骤5：生成最终响应
# async def generate_response(state: AgentState, config: RunnableConfig) -> AgentState:
# 	mcp_code = state["mcp_code"]
# 	test_feedback = state["test_feedback"]

# 	logger.info("\n==== 生成最终响应 ====")

# 	response = f"""
#     生成的MCP Server代码：
#     ```typescript
#     {mcp_code}
#     ```

#     测试结果：{test_feedback}
#     """

# 	logger.info(f"最终响应:\n{response}\n")
# 	logger.info("==== 完成 ====\n")

# 	return {"messages": [AIMessage(content=response)]}
# agent.add_node("respond", generate_response)
# agent.add_edge("test", "respond")
# agent.add_edge("respond", END)

# 编译 agent
mcp_generate_agent = agent.compile(checkpointer=MemorySaver())
