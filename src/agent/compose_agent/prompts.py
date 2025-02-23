"""Default prompts used by the agent."""

SYSTEM_PROMPT = """You are a helpful AI assistant.

System time: {system_time}"""

# TODO 首先需要对照MCP服务模板,检验代码完整性,不完整的需要嵌入代码.
COMPOSE_PROMPT = """
MCP服务是一种固定格式的通信协议. 
"""