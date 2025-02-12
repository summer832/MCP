from typing import List, TypedDict
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, MessagesState, END
from core import get_model, settings
import json


# 数据库实现相关的状态
class ModuleInfo(TypedDict):
	name: str
	description: str


class CodeBlock(TypedDict):
	name: str
	code: str
	description: str


class DatabaseState(MessagesState, total=False):
	modules: List[ModuleInfo] | None  # 模块分析结果
	interface_design: str | None      # 接口定义
	code_blocks: List[CodeBlock] | None  # 各模块实现
	combined_code: str | None         # 最终组合的代码


# 步骤1：需求分析和模块拆分
async def analyze_database_modules(state: DatabaseState, config: RunnableConfig) -> DatabaseState:
	requirement = state["messages"][-1].content
	m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))

	response = await m.ainvoke([
		HumanMessage(content=f"""
        分析以下数据库操作需求，列出需要实现的具体功能模块：
        {requirement}
        
        请以JSON格式返回必要的模块列表，例如:
        [
            {{"name": "数据库连接", "description": "创建和管理数据库连接"}},
            {{"name": "查询生成", "description": "自然语言转换为SQL"}},
            {{"name": "查询执行", "description": "执行SQL并处理结果"}},
            {{"name": "错误处理", "description": "统一的错误处理机制"}},
            {{"name": "结果格式化", "description": "将查询结果转换为MCP规范的格式"}}
        ]
        """)
	])

	modules = json.loads(response.content)
	return {**state, "modules": modules}


# 步骤2：接口设计
async def design_interfaces(state: DatabaseState, config: RunnableConfig) -> DatabaseState:
	requirement = state["messages"][-1].content
	modules = state["modules"]
	
	m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
	response = await m.ainvoke([
		HumanMessage(content=f"""
        为以下数据库操作需求设计TypeScript接口：
        
        需求：{requirement}
        
        模块列表：
        {json.dumps(modules, indent=2)}
        
        请设计：
        1. 参数接口（包含所有必要的输入参数）
        2. 返回值接口（符合MCP响应格式）
        3. 内部数据结构（如有必要）
        """)
	])
	
	return {**state, "interface_design": response.content}


# 步骤3：实现各个模块
async def implement_database_modules(state: DatabaseState, config: RunnableConfig) -> DatabaseState:
	# 获取当前需求
	requirement = state["messages"][-1].content
	operation_details = state["operation_details"]
	
	# 创建一个全新的对话上下文
	database_messages = [
		SystemMessage(content="""你是一个数据库开发专家。你需要根据需求生成相应的数据库操作代码。
请注意：
1. 使用 TypeScript 实现
2. 实现完整的错误处理
3. 使用 async/await 处理异步操作
4. 添加必要的注释
5. 确保代码的安全性和性能
"""),
		HumanMessage(content=f"""
需求描述：{requirement}

操作细节：
- 操作类型：{operation_details['operation_type']}
- 目标表：{operation_details['target_table']}
- SQL操作：{', '.join(operation_details['sql_operations'])}
- 参数：{json.dumps(operation_details['parameters'], ensure_ascii=False, indent=2)}

请生成相应的数据库操作代码。
""")
	]

	# 使用新的对话上下文调用 LLM
	m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
	response = await m.ainvoke(database_messages)
	
	# 解析响应并生成代码
	implementation_result = {
		"code": response.content,
		"status": "success",
		"message": "数据库模块实现完成"
	}
	
	# 将实现结果添加到原始状态，但保持原有消息历史不变
	return {
		**state,
		"database_implementation": implementation_result,
		"messages": state["messages"] + [AIMessage(content=f"数据库模块实现完成：\n```typescript\n{response.content}\n```")]
	}


# 步骤4：组合代码
async def combine_database_code(state: DatabaseState, config: RunnableConfig) -> DatabaseState:
	interfaces = state["interface_design"]
	code_blocks = state["code_blocks"]

	m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
	response = await m.ainvoke([
		HumanMessage(content=f"""
        将以下数据库操作相关的代码组合成一个完整的实现：
        
        接口定义：
        {interfaces}
        
        模块代码：
        {json.dumps(code_blocks, indent=2)}
        
        要求：
        1. 正确的代码组织顺序
        2. 完整的错误处理
        3. 清晰的模块导出
        4. 符合 MCP Server 工具实现规范
        """)
	])

	return {**state, "combined_code": response.content}


DATABASE_FRAMEWORK_TEMPLATE = """
// 2. 接口设计
interface QueryOrdersParams {
    userId: string;
    startDate?: string;
    endDate?: string;
}

interface OrderResult {
    orderId: string;
    date: string;
    amount: number;
    status: string;
}

// 3. 核心功能实现
async function generateOrderQuery(params: QueryOrdersParams): Promise<string> {
    // 自然语言转SQL
    // 参数处理和SQL生成
}

async function executeQuery(sql: string): Promise<OrderResult[]> {
    // 执行SQL并处理结果
}

// 4. 工具封装
async function queryOrders(params: QueryOrdersParams): Promise<{
    content: Array<{type: "text" | "json", data: any}>,
    isError: boolean
}> {
    try {
        // 参数验证
        if (!params.userId) {
            throw new Error("userId is required");
        }
        
        // 生成SQL
        const sql = await generateOrderQuery(params);
        
        // 执行查询
        const results = await executeQuery(sql);
        
        // 格式化返回
        return {
            content: [
                {
                    type: "json",
                    data: results
                }
            ],
            isError: false
        };
    } catch (error) {
        return {
            content: [{
                type: "text",
                text: `Error: ${error.message}`
            }],
            isError: true
        };
    }
}
"""

# 构建数据库操作的子图
database_graph = StateGraph(DatabaseState)

# 添加节点
database_graph.add_node("analyze_modules", analyze_database_modules)
database_graph.add_node("design_interfaces", design_interfaces)
database_graph.add_node("implement_modules", implement_database_modules)
database_graph.add_node("combine_code", combine_database_code)

# 设置流程
database_graph.set_entry_point("analyze_modules")
database_graph.add_edge("analyze_modules", "design_interfaces")
database_graph.add_edge("design_interfaces", "implement_modules")
database_graph.add_edge("implement_modules", "combine_code")
database_graph.add_edge("combine_code", END)

# 编译子图
database_chain = database_graph.compile()
