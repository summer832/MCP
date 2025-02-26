"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Literal, cast
from pathlib import Path

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

# Import from cline4py package
from agent.cline4py.cline4py import ClineClient, FolderManager

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
	"""Generate code using Cline instead of direct prompts"""
	# Get config
	configuration = Configuration.from_runnable_config(config)
	state.requirement = state.messages[0].content

	# Parse requirement info
	print("Starting code generation with Cline:", state.messages)
	info = json.loads(get_json(state.requirement))

	# Initialize Cline client
	client = ClineClient()
	folder_manager = FolderManager()

	# Create result folder if it doesn't exist
	result_folder = os.path.abspath("result")
	os.makedirs(result_folder, exist_ok=True)

	# Open the result folder in Cline
	try:
		folder_manager.open_folder_in_vscode(result_folder)
		print(f"Opened folder in VSCode: {result_folder}")
	except Exception as e:
		print(f"Warning: Could not open folder in VSCode: {str(e)}")

	# Prepare the prompt for Cline based on requirement type
	if info["requirement_type"] == "database":
		prompt_type = "database"
	elif info["requirement_type"] == "browser":
		prompt_type = "browser"
	else:
		prompt_type = "general"

	# Create a message for Cline with the requirement and instructions
	cline_message = f"""
	I need you to generate an index.ts file based on the following requirements:
	
	Requirement Type: {prompt_type}
	
	Requirements:
	{info.get('requirement', '')}
	
	Please create a complete and well-structured index.ts file that implements these requirements.
	Save the file as index.ts in the current folder.
	"""

	try:
		# Send the request to Cline
		response = client.process_message(cline_message)
		print("Cline response received")

		# Wait for Cline to generate the file
		# Read the generated file
		file_path = os.path.join(result_folder, "index.ts")
		if os.path.exists(file_path):
			with open(file_path, "r", encoding="utf-8") as f:
				complete_code = f.read()
		else:
			# If file doesn't exist, use a fallback message
			complete_code = "// Error: Cline did not generate the index.ts file. Please check the requirements and try again."
			print(f"Warning: File not found at {file_path}")
	except Exception as e:
		print(f"Error in Cline code generation: {str(e)}")
		complete_code = f"// Error: Failed to generate code with Cline: {str(e)}"

	print("Generated code:", complete_code[:100] + "..." if len(complete_code) > 100 else complete_code)

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
	"""Check code using Cline instead of direct prompts"""
	configuration = Configuration.from_runnable_config(config)

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
		# Initialize Cline client
		client = ClineClient()
		folder_manager = FolderManager()

		# Make sure the result folder is open in Cline
		result_folder = os.path.abspath("result")
		try:
			folder_manager.open_folder_in_vscode(result_folder)
			print(f"Opened folder in VSCode for code checking: {result_folder}")
		except Exception as e:
			print(f"Warning: Could not open folder in VSCode: {str(e)}")

		# Create a message for Cline with the code checking instructions
		check_message = f"""
		I need you to check the code in the index.ts file in the current folder.
		
		Requirements:
		{state.requirement}
		
		Please analyze the code and provide a detailed assessment in JSON format with the following structure:
		
		```json
		{{
			"isValid": true/false,
			"checkResults": {{
				"baseProtocol": {{"passed": true/false, "issues": ["issue1", "issue2"]}},
				"serverSetup": {{"passed": true/false, "issues": ["issue1", "issue2"]}},
				"handlers": {{"passed": true/false, "issues": ["issue1", "issue2"]}},
				"tools": {{"passed": true/false, "issues": ["issue1", "issue2"]}}
			}},
			"summary": {{
				"errors": ["error1", "error2"],
				"warnings": ["warning1", "warning2"]
			}}
		}}
		```
		
		The code should be checked against the following criteria:
		1. Does it implement the requirements correctly?
		2. Is it well-structured and follows best practices?
		3. Are there any potential bugs or issues?
		4. Is the code complete and functional?
		
		Please provide your assessment in the JSON format described above.
		"""

		# Send the request to Cline
		response = client.process_message(check_message)
		print("Cline check response received")

		# Extract the JSON from the response
		# We'll look for a JSON structure in the response
		content = response.get("response", "")
		extracted_content = extract_content(content) if content else content

		# Try to parse the JSON from the response
		try:
			res = json.loads(get_json(extracted_content))
		except Exception as e:
			print(f"Error parsing JSON from Cline response: {str(e)}")
			# Create a default response if we can't parse the JSON
			res = {
				"isValid": False,
				"checkResults": {
					"baseProtocol": {"passed": False, "issues": ["Could not parse check results"]},
					"serverSetup": {"passed": False, "issues": ["Could not parse check results"]},
					"handlers": {"passed": False, "issues": ["Could not parse check results"]},
					"tools": {"passed": False, "issues": ["Could not parse check results"]}
				},
				"summary": {
					"errors": ["Could not parse check results from Cline"],
					"warnings": ["Please check the requirements and try again"]
				}
			}

		print("Check result:", res)

		return {
			"messages": [*state.messages, AIMessage(content=json.dumps(res, ensure_ascii=False))],
			"check_history": [*state.check_history, AIMessage(content=extracted_content)],
			"is_valid": res.get("isValid", False)
		}
	except Exception as e:
		print(f"Error in code checking with Cline: {str(e)}")
		default_result = {
			"isValid": False,
			"checkResults": {
				"baseProtocol": {"passed": False, "issues": ["Error during code checking"]},
				"serverSetup": {"passed": False, "issues": ["Error during code checking"]},
				"handlers": {"passed": False, "issues": ["Error during code checking"]},
				"tools": {"passed": False, "issues": ["Error during code checking"]}
			},
			"summary": {
				"errors": [f"Error during code checking with Cline: {str(e)}"],
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
	"""Revise code using Cline instead of direct prompts"""
	configuration = Configuration.from_runnable_config(config)

	try:
		# Initialize Cline client
		client = ClineClient()
		folder_manager = FolderManager()

		# Make sure the result folder is open in Cline
		result_folder = os.path.abspath("result")
		try:
			folder_manager.open_folder_in_vscode(result_folder)
			print(f"Opened folder in VSCode for code revision: {result_folder}")
		except Exception as e:
			print(f"Warning: Could not open folder in VSCode: {str(e)}")

		# Get the check results to include in the revision request
		check_results = ""
		if hasattr(state, 'check_history') and state.check_history:
			last_check = state.check_history[-1].content if hasattr(state.check_history[-1], 'content') else str(
				state.check_history[-1])
			check_results = last_check

		# Create a message for Cline with the code revision instructions
		revise_message = f"""
		I need you to revise the code in the index.ts file in the current folder based on the following requirements and check results.
		
		Requirements:
		{state.requirement}
		
		Check Results:
		{check_results}
		
		Please improve the code to address the issues identified in the check results and ensure it meets all requirements.
		After making your improvements, please provide a summary of the changes you made in JSON format with the following structure:
		
		```json
		{{
			"changes": [
				"Description of change 1",
				"Description of change 2"
			],
			"improvedCode": "The full improved code here"
		}}
		```
		
		Please make sure to save your changes to the index.ts file in the current folder.
		"""

		# Send the request to Cline
		response = client.process_message(revise_message)
		print("Cline revision response received")

		# Extract the JSON from the response
		content = response.get("response", "")
		extracted_content = extract_content(content) if content else content

		# Read the revised file
		file_path = os.path.join(result_folder, "index.ts")
		if os.path.exists(file_path):
			with open(file_path, "r", encoding="utf-8") as f:
				final_improved_code = f.read()
		else:
			# If file doesn't exist, use a fallback message
			final_improved_code = state.code  # Use original code as fallback
			print(f"Warning: Revised file not found at {file_path}, using original code")

		# Try to parse the JSON from the response to get the changes
		try:
			res_json = get_json(extracted_content)
			res = json.loads(res_json)

			# If the response doesn't include the improved code, add it
			if "improvedCode" not in res or not res["improvedCode"]:
				res["improvedCode"] = final_improved_code

			res_json = json.dumps(res)
		except Exception as e:
			print(f"Error parsing JSON from Cline revision response: {str(e)}")
			# Create a default response with the improved code
			res = {
				"changes": ["Code was revised but change details could not be parsed"],
				"improvedCode": final_improved_code
			}
			res_json = json.dumps(res)

		print("Revision result:", res)

		return {
			"messages": [*state.messages, AIMessage(content=res_json)],
			"revise_history": [*state.revise_history, AIMessage(content=extracted_content)],
			"conversation_turn": state.conversation_turn + 1,
			"code": final_improved_code
		}
	except Exception as e:
		# Handle any errors during the revision process
		print(f"Error in code revision with Cline: {str(e)}")
		print(f"Using original code as fallback")

		# Create a fallback response that preserves the original code
		fallback_code = state.code
		if fallback_code.startswith("// Error:"):
			fallback_code = "// Error: Could not generate code properly. Please check the requirements and try again."

		error_json = json.dumps({
			"error": f"Failed during code revision with Cline: {str(e)}",
			"improvedCode": fallback_code
		})

		return {
			"messages": [*state.messages, AIMessage(content=error_json)],
			"revise_history": [*state.revise_history, AIMessage(content=error_json)],
			"conversation_turn": state.conversation_turn + 1,
			"code": fallback_code  # Preserve the original code instead of losing it
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
			"check_history": [msg.content if hasattr(msg, "content") else str(msg) for msg in
			                  state.check_history] if hasattr(state, "check_history") and state.check_history else [],
			"revise_history": [msg.content if hasattr(msg, "content") else str(msg) for msg in
			                   state.revise_history] if hasattr(state,
			                                                    "revise_history") and state.revise_history else []
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
