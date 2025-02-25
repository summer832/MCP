"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""
import json
from datetime import datetime, timezone
from typing import Dict, List, Literal, cast

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from agent.generate_agent.configuration import Configuration
from agent.generate_agent.state import InputState, State
from agent.generate_agent.tools import TOOLS
from agent.generate_agent.utils import load_chat_model, get_json, extract_content
from agent.generate_agent.prompts import CHECK_PROMPT, REVISE_PROMPT, DATABASE_PROMPT, SYSTEM_PROMPT, BROWSER_PROMPT
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential, wait_fixed, wait_combine


@retry(
	stop=stop_after_attempt(3),
	wait=wait_combine(
		wait_fixed(2),
		wait_exponential(multiplier=1, min=4, max=10)  # 指数增长等待
	)
)
async def call_model_with_retry(model, messages, config):
	return await model.ainvoke(messages, config)


# Define the function that calls the model
async def call_model(
		state: State, config: RunnableConfig
) -> Dict[str, List[AIMessage]]:
	"""generate the code"""
	# get config
	configuration = Configuration.from_runnable_config(config)
	model = load_chat_model(configuration.model)
	state.requirement = state.messages[0].content
	# choose prompt
	print(get_json(state.requirement))
	info = json.loads(get_json(state.requirement))
	if info["requirement_type"] == "database":
		system_prompt = DATABASE_PROMPT
	elif info["requirement_type"] == "browser":
		system_prompt = BROWSER_PROMPT
	else:
		system_prompt = SYSTEM_PROMPT
	# get code
	while True:
		response = cast(
			AIMessage,
			await call_model_with_retry(model, [{"role": "system", "content": system_prompt}, *state.messages], config),
		)
		response.content = extract_content(response)
		if response.content.replace("\\n", "") != "<<HUMAN_CONVERSATION_END>>":
			break
	print("generate the code:", response)

	return {
		"messages": [*state.messages, response],
		"requirement": state.requirement,
		"code": response.content
	}


# Define a new graph
builder = StateGraph(State, input=InputState, config_schema=Configuration)
# Define the two nodes we will cycle between
builder.add_node(call_model)
# Set the entrypoint as `call_model`
# This means that this node is the first one called
builder.add_edge("__start__", "call_model")


# Add a normal edge from `tools` to `call_model`

# builder.add_node("tools", ToolNode(TOOLS))
# This creates a cycle: after using tools, we always return to the model
# builder.add_edge("tools", "call_model")

# 编纂check用记忆, 把revise和code变为HumanMessage
def make_check_history(state: State) -> List[BaseMessage]:
	history = [
		HumanMessage(content=json.dumps({"requirement": state.requirement, "code": state.code},
		                                ensure_ascii=False))]

	# 如果存在check_history和revise_history
	if hasattr(state, 'check_history') and hasattr(state, 'revise_history'):
		# 获取两个历史记录的最大长度
		max_len = max(
			len(state.check_history) if state.check_history else 0,
			len(state.revise_history) if state.revise_history else 0
		)

		# 交替添加check和revise历史
		for i in range(max_len):
			# 添加check历史
			if state.check_history and i < len(state.check_history):
				history.append(AIMessage(content=state.check_history[i].content))

			# 添加revise历史，将其转换为HumanMessage
			if state.revise_history and i < len(state.revise_history):
				history.append(HumanMessage(content=state.revise_history[i].content))
	# print("history:", history)
	return history


async def call_check(
		state: State, config: RunnableConfig
) -> Dict[str, List[AIMessage]]:
	configuration = Configuration.from_runnable_config(config)

	# TODO暂不支持tool
	# model = load_chat_model(configuration.model).bind_tools(TOOLS)
	model = load_chat_model(configuration.model)
	# Format the system prompt. Customize this to change the agent's behavior.
	system_message = CHECK_PROMPT

	tmp_message = [{"role": "system", "content": system_message}]
	tmp_message.extend(make_check_history(state))
	response = cast(
		AIMessage,
		await call_model_with_retry(model, tmp_message, config),
	)
	print("check result:", response)
	res = json.loads(get_json(extract_content(response)))

	return {
		"messages": [*state.messages, AIMessage(content=json.dumps(res, ensure_ascii=False))],
		"check_history": [*state.check_history, AIMessage(content=extract_content(response))],
		"is_valid": res["isValid"]

	}


builder.add_node(call_check)
builder.add_edge("call_model", "call_check")


# 编纂revise用记忆, 把check变为HumanMessage
def make_revise_history(state: State) -> List[BaseMessage]:
	history = [HumanMessage(content=state.requirement)]

	# 添加初始代码作为第一条消息
	if hasattr(state, 'code'):
		history.append(AIMessage(content=state.code))

	# 如果存在check_history和revise_history
	if hasattr(state, 'check_history') and hasattr(state, 'revise_history'):
		# 获取两个历史记录的最大长度
		max_len = max(
			len(state.check_history) if state.check_history else 0,
			len(state.revise_history) if state.revise_history else 0
		)

		# 交替添加check和revise历史
		for i in range(max_len):
			# 添加check历史
			if state.check_history and i < len(state.check_history):
				history.append(HumanMessage(content=state.check_history[i].content))

			# 添加revise历史，将其转换为HumanMessage
			if state.revise_history and i < len(state.revise_history):
				history.append(AIMessage(content=state.revise_history[i].content))
	return history


async def call_revise(
		state: State, config: RunnableConfig
) -> Dict[str, List[AIMessage]]:
	configuration = Configuration.from_runnable_config(config)

	# TODO暂不支持tool
	# model = load_chat_model(configuration.model).bind_tools(TOOLS)
	model = load_chat_model(configuration.model)
	# Format the system prompt. Customize this to change the agent's behavior.
	system_message = REVISE_PROMPT

	tmp_message = [{"role": "system", "content": system_message}]
	tmp_message.extend(make_revise_history(state))
	response = cast(
		AIMessage,
		await call_model_with_retry(model, tmp_message, config),
	)

	print("revise result:", response)
	res = get_json(extract_content(response))

	return {
		"messages": [*state.messages, AIMessage(content=res)],
		"revise_history": [*state.revise_history, AIMessage(content=extract_content(response))],
		"conversation_turn": state.conversation_turn + 1
	}


builder.add_node(call_revise)
builder.add_edge("call_revise", "call_check")


def route_model_output(state: State) -> Literal["__end__", "call_revise"]:
	last_message = state.messages[-1]
	if not isinstance(last_message, AIMessage):
		raise ValueError(
			f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
		)
	# If there is no tool call, then we finish
	# if last_message.tool_calls:
	# 	return "tools"
	if state.conversation_turn > 3 or state.is_valid:
		return "__end__"
	# Otherwise we execute the requested actions
	return "call_revise"


# Add a conditional edge to determine the next step after `call_model`
builder.add_conditional_edges(
	"call_check",
	# After call_model finishes running, the next node(s) are scheduled
	# based on the output from route_model_output
	route_model_output,
)

# Compile the builder into an executable graph
# You can customize this by adding interrupt points for state updates
graph = builder.compile(
	interrupt_before=[],  # Add node names here to update state before they're called
	interrupt_after=[],  # Add node names here to update state after they're called
)
graph.name = "Codegen Agent"  # This customizes the name in LangSmith
