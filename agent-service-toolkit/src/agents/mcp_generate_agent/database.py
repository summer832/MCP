from typing import List, TypedDict
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, MessagesState, END
from core import get_model, settings
import json


# 数据库实现相关的状态
class CodeBlock(TypedDict):
	name: str
	code: str
	description: str


class DatabaseState(MessagesState, total=False):
	modules: List[dict] | None
	code_blocks: List[CodeBlock] | None
	combined_code: str | None


# 步骤1：需求拆分
async def analyze_database_modules(state: DatabaseState, config: RunnableConfig) -> DatabaseState:
	requirement = state["messages"][-1].content
	m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))

	response = await m.ainvoke([
		HumanMessage(content=f"""
        分析以下数据库操作需求，列出需要实现的具体功能模块：
        {requirement}
        
        请以JSON格式返回数据库操作相关的模块，例如：
        [
            {{"name": "数据库连接", "description": "创建和管理数据库连接"}},
            {{"name": "查询操作", "description": "执行SQL查询并处理结果"}}
        ]
        """)
	])

	modules = json.loads(response.content)
	return {
		**state,
		"modules": modules
	}


# 步骤2：实现各个模块
async def implement_database_modules(state: DatabaseState, config: RunnableConfig) -> DatabaseState:
	requirement = state["messages"][-1].content
	modules = state["modules"]

	m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
	code_blocks = []

	for module in modules:
		response = await m.ainvoke([
			HumanMessage(content=f"""
            实现以下数据库功能模块：
            模块名称：{module['name']}
            功能描述：{module['description']}
            完整需求：{requirement}
            
            要求：
            1. 使用 TypeScript 实现
            2. 包含数据库连接和错误处理
            3. 使用 async/await 处理异步操作
            4. 添加必要的注释
            """)
		])

		code_blocks.append({
			"name": module["name"],
			"code": response.content,
			"description": module["description"]
		})

	return {
		**state,
		"code_blocks": code_blocks
	}


# 步骤3：组合代码
async def combine_database_code(state: DatabaseState, config: RunnableConfig) -> DatabaseState:
	code_blocks = state["code_blocks"]

	m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
	response = await m.ainvoke([
		HumanMessage(content=f"""
        将以下数据库操作相关的代码块组合成一个完整的实现：
        {json.dumps(code_blocks, indent=2)}
        
        要求：
        1. 正确的代码组织顺序
        2. 清晰的模块导出
        3. 完整的错误处理
        4. 符合 MCP Server 工具实现规范
        """)
	])

	return {
		**state,
		"combined_code": response.content
	}


# 构建数据库操作的子图
database_graph = StateGraph(DatabaseState)

# 添加节点
database_graph.add_node("analyze_modules", analyze_database_modules)
database_graph.add_node("implement_modules", implement_database_modules)
database_graph.add_node("combine_code", combine_database_code)

# 设置流程
database_graph.set_entry_point("analyze_modules")
database_graph.add_edge("analyze_modules", "implement_modules")
database_graph.add_edge("implement_modules", "combine_code")
database_graph.add_edge("combine_code", END)

# 编译子图
database_chain = database_graph.compile()
