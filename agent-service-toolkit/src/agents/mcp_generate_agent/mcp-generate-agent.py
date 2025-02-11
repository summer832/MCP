from typing import Literal, TypedDict
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda, RunnableSerializable
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, MessagesState, StateGraph

from core import get_model, settings

# 定义状态类型
class AgentState(MessagesState, total=False):
    requirement_type: Literal["database", "browser"] | None
    code_implementation: str | None
    mcp_code: str | None
    test_feedback: str | None

# 步骤1：需求分析和分类
async def analyze_requirement(state: AgentState, config: RunnableConfig) -> AgentState:
    messages = state["messages"]
    requirement = messages[-1].content
    
    # 调用模型进行需求分类
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    response = await m.ainvoke([
        HumanMessage(content=f"""
        请分析以下需求，判断是数据库操作型(database)还是浏览器操作型(browser)需求：
        {requirement}
        只需要返回 'database' 或 'browser'，不需要其他解释。
        """)
    ])
    
    requirement_type = response.content.strip()
    return {
        "messages": messages,
        "requirement_type": requirement_type
    }

# 步骤2：代码实现
async def implement_code(state: AgentState, config: RunnableConfig) -> AgentState:
    messages = state["messages"]
    requirement = messages[-1].content
    requirement_type = state["requirement_type"]
    
    # 根据需求类型选择不同的实现模板
    template = DATABASE_TEMPLATE if requirement_type == "database" else BROWSER_TEMPLATE
    
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    response = await m.ainvoke([
        HumanMessage(content=f"""
        请根据以下需求实现具体的功能代码：
        {requirement}
        
        实现模板：
        {template}
        
        请只返回实现代码，不需要解释。
        """)
    ])
    
    return {
        "messages": messages,
        "requirement_type": requirement_type,
        "code_implementation": response.content
    }

# 步骤3：生成MCP框架代码
async def generate_mcp_code(state: AgentState, config: RunnableConfig) -> AgentState:
    implementation = state["code_implementation"]
    
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    response = await m.ainvoke([
        HumanMessage(content=f"""
        请将以下实现代码整合到MCP Server框架中：
        {implementation}
        
        MCP Server框架模板：
        {MCP_FRAMEWORK_TEMPLATE}
        
        请返回完整的MCP Server代码。
        """)
    ])
    
    return {
        **state,
        "mcp_code": response.content
    }

# 步骤4：代码测试
async def test_code(state: AgentState, config: RunnableConfig) -> AgentState:
    mcp_code = state["mcp_code"]
    
    # 这里预留测试工具接口
    test_result = "测试通过"  # 实际应该调用测试工具
    
    return {
        **state,
        "test_feedback": test_result
    }

# 步骤5：生成最终响应
async def generate_response(state: AgentState, config: RunnableConfig) -> AgentState:
    mcp_code = state["mcp_code"]
    test_feedback = state["test_feedback"]
    
    response = f"""
    生成的MCP Server代码：
    ```typescript
    {mcp_code}
    ```
    
    测试结果：{test_feedback}
    """
    
    return {"messages": [AIMessage(content=response)]}

# 定义模板
DATABASE_TEMPLATE = """
// 数据库操作相关的实现模板
async function handleDatabaseOperation() {
    // 实现代码
}
"""

BROWSER_TEMPLATE = """
// 浏览器操作相关的实现模板
async function handleBrowserOperation() {
    // 实现代码
}
"""

MCP_FRAMEWORK_TEMPLATE = """
import { Server } from "@microsoft/mcp";
import { StdioServerTransport } from "@microsoft/mcp";

const server = new Server(
    {
        name: "mcp-demo-server",
        version: "1.0.0"
    },
    {
        capabilities: {
            tools: {}
        }
    }
);

// 这里插入实现代码

const transport = new StdioServerTransport();
server.connect(transport);
"""

# 构建工作流图
agent = StateGraph(AgentState)

# 添加节点
agent.add_node("analyze", analyze_requirement)
agent.add_node("implement", implement_code)
agent.add_node("generate", generate_mcp_code)
agent.add_node("test", test_code)
agent.add_node("respond", generate_response)

# 设置入口点
agent.set_entry_point("analyze")

# 添加边
agent.add_edge("analyze", "implement")
agent.add_edge("implement", "generate")
agent.add_edge("generate", "test")
agent.add_edge("test", "respond")
agent.add_edge("respond", END)

# 编译 agent
mcp_generate_agent = agent.compile(
    checkpointer=MemorySaver(),
)
