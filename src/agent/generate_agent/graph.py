"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""
import json
from datetime import datetime, timezone
from typing import Dict, List, Literal, cast

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
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
	print("start generate:", state.messages)
	info = json.loads(get_json(state.requirement))
	if info["requirement_type"] == "database":
		system_prompt = DATABASE_PROMPT
	elif info["requirement_type"] == "browser":
		system_prompt = BROWSER_PROMPT
	else:
		system_prompt = SYSTEM_PROMPT

	# get code - with handling for potentially truncated responses
	max_attempts = 3
	attempt = 0
	complete_code = ""
	partial_code = ""

	# Hard limit on attempts to prevent infinite loops
	absolute_max_attempts = 10

	while attempt < max_attempts and absolute_max_attempts > 0:
		absolute_max_attempts -= 1
		try:
			# If we have partial code from a previous attempt, include it in the messages
			messages = [{"role": "system", "content": system_prompt}]
			messages.extend(state.messages)

			if partial_code and attempt > 0:
				# Add a message indicating that the previous attempt was incomplete
				messages.append(HumanMessage(
					content=f"The previous code generation was incomplete. Please continue from where it left off and complete the code. Here's what was generated so far:\n\n{partial_code}"))

			response = cast(
				AIMessage,
				await model.ainvoke(messages, config),
			)
			response.content = extract_content(response)
			print(f"code result {attempt} times:", response.content)

			if response.content.replace("\\n", "") == "<<HUMAN_CONVERSATION_END>>":
				attempt += 1
				continue

			code_content = response.content

			# If we have partial code from a previous attempt, try to combine them intelligently
			if partial_code and attempt > 0:
				# Check if the new content seems to be a continuation or a completely new response
				if not code_content.strip().startswith("{") and partial_code.strip().endswith("{"):
					# Looks like a continuation, append it
					code_content = partial_code + "\n" + code_content
				elif code_content.count('{') > code_content.count('}'):
					# New content has unbalanced braces, might be a fresh start
					# Use the one with more content or the new one if they're similar in size
					if len(code_content) > len(partial_code) * 1.2:  # 20% longer
						partial_code = code_content
					else:
						# Try to merge them intelligently
						code_content = partial_code + "\n" + code_content
				else:
					# Use the new content if it seems more complete
					if code_content.count('{') == code_content.count('}') and code_content.strip().endswith('}'):
						partial_code = code_content
					else:
						# Use the longer one
						if len(code_content) > len(partial_code):
							partial_code = code_content

			else:
				# First attempt, just store the code
				partial_code = code_content

			# Check if the code appears complete (has closing braces matching opening ones)
			if partial_code.count('{') == partial_code.count('}') and partial_code.strip().endswith('}'):
				complete_code = partial_code
				break
			else:
				# If we're on the last attempt and code still seems incomplete, 
				# try to complete it by adding missing closing braces
				# TODO 这里可以考虑使用cline4py
				if attempt == max_attempts - 1:
					missing_braces = partial_code.count('{') - partial_code.count('}')
					if missing_braces > 0:
						complete_code = partial_code + '\n' + ('}' * missing_braces)
					else:
						complete_code = partial_code
				else:
					# Store the partial code for the next attempt
					attempt += 1
					continue
		except Exception as e:
			print(f"Error in code generation attempt {attempt + 1}: {str(e)}")
			attempt += 1

	if not complete_code:
		complete_code = "// Error: Could not generate complete code after multiple attempts"

	print("generate the code:", complete_code[:100] + "..." if len(complete_code) > 100 else complete_code)

	return {
		"messages": [*state.messages, AIMessage(content=complete_code)],
		"requirement": state.requirement,
		"code": complete_code
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

	# Ensure code is not empty or invalid before checking
	if not state.code or state.code.strip() == "" or state.code.startswith("// Error:"):
		print("Warning: Invalid or empty code detected, skipping check")
		default_result = {
			"isValid": False,
			"checkResults": {
				"baseProtocol": {"passed": False, "issues": ["Code is empty or invalid"]},
				"serverSetup": {"passed": False, "issues": ["Code is empty or invalid"]},
				"handlers": {"passed": False, "issues": ["Code is empty or invalid"]},
				"tools": {"passed": False, "issues": ["Code is empty or invalid"]}
			},
			"summary": {
				"errors": ["Code is empty or invalid"],
				"warnings": ["Please check the requirements and try again"]
			}
		}

		return {
			"messages": [*state.messages, AIMessage(content=json.dumps(default_result, ensure_ascii=False))],
			"check_history": [*state.check_history, AIMessage(content=json.dumps(default_result, ensure_ascii=False))],
			"is_valid": False
		}

	try:
		tmp_message = [{"role": "system", "content": system_message}]
		tmp_message.extend(make_check_history(state))
		response = cast(
			AIMessage,
			await model.ainvoke(tmp_message, config),
		)

		extracted_content = extract_content(response)
		res = json.loads(get_json(extracted_content))
		print("check result:", res)

		return {
			"messages": [*state.messages, AIMessage(content=json.dumps(res, ensure_ascii=False))],
			"check_history": [*state.check_history, AIMessage(content=extracted_content)],
			"is_valid": res["isValid"]
		}
	except Exception as e:
		print(f"Error in code checking: {str(e)}")
		default_result = {
			"isValid": False,
			"checkResults": {
				"baseProtocol": {"passed": False, "issues": ["Error during code checking"]},
				"serverSetup": {"passed": False, "issues": ["Error during code checking"]},
				"handlers": {"passed": False, "issues": ["Error during code checking"]},
				"tools": {"passed": False, "issues": ["Error during code checking"]}
			},
			"summary": {
				"errors": [f"Error during code checking: {str(e)}"],
				"warnings": ["Please check the requirements and try again"]
			}
		}

		return {
			"messages": [*state.messages, AIMessage(content=json.dumps(default_result, ensure_ascii=False))],
			"check_history": [*state.check_history, AIMessage(content=json.dumps(default_result, ensure_ascii=False))],
			"is_valid": False
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

	# Add retry mechanism for revise similar to code generation
	max_attempts = 3
	attempt = 0
	final_improved_code = ""
	partial_improved_code = ""

	# Hard limit on attempts to prevent infinite loops
	absolute_max_attempts = 10

	while attempt < max_attempts and not final_improved_code and absolute_max_attempts>0:
		absolute_max_attempts -= 1
		try:
			# Prepare messages for the model
			tmp_message = [{"role": "system", "content": system_message}]
			base_history = make_revise_history(state)
			tmp_message.extend(base_history)

			# If we have partial improved code from a previous attempt, include it
			if partial_improved_code and attempt > 0:
				tmp_message.append(HumanMessage(
					content=f"The previous revision was incomplete. Please continue from where it left off and complete the improved code. Here's what was generated so far:\n\n{partial_improved_code}"))

			response = cast(
				AIMessage,
				await call_model_with_retry(model, tmp_message, config),
			)

			print(f"revise result attempt {attempt}:", response)
			content = extract_content(response)

			# Try to parse the response as JSON
			res = get_json(content)
			# Validate that the result is valid JSON
			tmp = json.loads(res)

			# Verify that improvedCode exists and is not empty
			if "improvedCode" not in tmp or not tmp["improvedCode"] or tmp["improvedCode"].strip() == "":
				if attempt < max_attempts - 1:
					attempt += 1
					continue
				else:
					raise ValueError("improvedCode field is missing or empty after multiple attempts")

			improved_code = tmp["improvedCode"]

			# If we have partial improved code from a previous attempt, try to combine them
			if partial_improved_code and attempt > 0:
				# Check if the new content seems to be a continuation
				if not improved_code.strip().startswith("{") and partial_improved_code.strip().endswith("{"):
					# Looks like a continuation, append it
					improved_code = partial_improved_code + "\n" + improved_code
				elif improved_code.count('{') > improved_code.count('}'):
					# New content has unbalanced braces, might be a fresh start
					# Use the one with more content or the new one if they're similar in size
					if len(improved_code) > len(partial_improved_code) * 1.2:  # 20% longer
						partial_improved_code = improved_code
					else:
						# Try to merge them intelligently
						improved_code = partial_improved_code + "\n" + improved_code
				else:
					# Use the new content if it seems more complete
					if improved_code.count('{') == improved_code.count('}') and improved_code.strip().endswith('}'):
						partial_improved_code = improved_code
					else:
						# Use the longer one
						if len(improved_code) > len(partial_improved_code):
							partial_improved_code = improved_code
			else:
				# First attempt, just store the code
				partial_improved_code = improved_code

			# Check if the improved code appears complete
			if partial_improved_code.count('{') == partial_improved_code.count(
					'}') and partial_improved_code.strip().endswith('}'):
				final_improved_code = partial_improved_code
				tmp["improvedCode"] = final_improved_code
				res = json.dumps(tmp)  # Update the JSON string with fixed code
				break
			else:
				# If we're on the last attempt and code still seems incomplete, 
				# try to complete it by adding missing closing braces
				if attempt == max_attempts - 1:
					missing_braces = partial_improved_code.count('{') - partial_improved_code.count('}')
					if missing_braces > 0:
						final_improved_code = partial_improved_code + '\n' + ('}' * missing_braces)
						tmp["improvedCode"] = final_improved_code
						res = json.dumps(tmp)  # Update the JSON string with fixed code
					else:
						final_improved_code = partial_improved_code
						tmp["improvedCode"] = final_improved_code
						res = json.dumps(tmp)  # Update the JSON string with fixed code
				else:
					# Store the partial code for the next attempt
					attempt += 1
					continue
		except Exception as e:
			# Handle any errors during the revision process
			print(f"Error in code revision: {str(e)}")
			print(f"Using original code as fallback")

			# Create a fallback response that preserves the original code
			fallback_code = state.code
			if fallback_code.startswith("// Error:"):
				fallback_code = "// Error: Could not generate code properly. Please check the requirements and try again."

			error_json = json.dumps({
				"error": f"Failed during code revision: {str(e)}",
				"improvedCode": fallback_code
			})

			return {
				"messages": [*state.messages, AIMessage(content=error_json)],
				"revise_history": [*state.revise_history, AIMessage(content=error_json)],
				"conversation_turn": state.conversation_turn + 1,
				"code": fallback_code  # Preserve the original code instead of losing it
			}

	# Return the final result after all attempts
	return {
		"messages": [*state.messages, AIMessage(content=res)],
		"revise_history": [*state.revise_history, AIMessage(content=content)],
		"conversation_turn": state.conversation_turn + 1,
		"code": final_improved_code
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

	# Hard limit on conversation turns to prevent infinite loops
	max_conversation_turns = 3

	# Log the current turn for debugging
	print(f"Current conversation turn: {state.conversation_turn}")

	if state.conversation_turn >= max_conversation_turns or state.is_valid:
		print(f"Ending generation after {state.conversation_turn} turns")
		
		# Before ending, store state information in a new message
		# This ensures that state data is preserved without relying on MemorySaver
		state_data = {
			"requirement": state.requirement if hasattr(state, "requirement") else "",
			"code": state.code if hasattr(state, "code") else "",
			"is_valid": state.is_valid if hasattr(state, "is_valid") else False,
			"conversation_turn": state.conversation_turn if hasattr(state, "conversation_turn") else 0,
			"check_history": [msg.content if hasattr(msg, "content") else str(msg) for msg in state.check_history] if hasattr(state, "check_history") and state.check_history else [],
			"revise_history": [msg.content if hasattr(msg, "content") else str(msg) for msg in state.revise_history] if hasattr(state, "revise_history") and state.revise_history else []
		}
		
		# Add the state data as the last message
		state.messages.append(AIMessage(content=json.dumps(state_data, ensure_ascii=False)))
		
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
