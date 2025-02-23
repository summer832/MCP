"""Default prompts used by the agent."""

SYSTEM_PROMPT = """You are a helpful AI assistant.

System time: {system_time}"""

SUPERVISOR_PROMPT = """
MCP服务是一种固定格式的通信协议.你是MCP代码生成服务的监督者, 你拥有一些工具, 你需要协调代码生成工作
你拥有以下工具: {members}. 
你当前需要进入{next_step}状态,请你根据当前的进度,判断下一条信息是否是{next_step}需要完成的工作?
如果当前的进度就是需要使用{next_step}来操作,请回答"true",否则"false".
无论User问你什么问题,你只能回答"true" or "false".
如果你认为不需要回答,请返回"true"
"""