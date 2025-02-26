"""Define a custom multi-step Reasoning and Action agent with ReAct-like structure.

Works with a chat model with tool calling support.
"""
import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Literal, cast
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph

from agent.configuration import Configuration, WorkflowNode
from agent.state import InputState, State, update_next_step
from agent.utils import load_chat_model, get_json, extract_content

from agent.analysis_agent import graph as AnalysisGraph
from agent.analysis_agent.state import InputState as AnalysisInputState
from agent.analysis_agent.configuration import Configuration as AnalysisConfiguration

from agent.generate_agent import graph as CodegenGraph
from agent.generate_agent.state import InputState as CodegenInputState
from agent.generate_agent.configuration import Configuration as CodegenConfiguration

from agent.compose_agent import graph as ComposeGraph
from agent.compose_agent.state import InputState as ComposeInputState
from agent.compose_agent.configuration import Configuration as ComposeConfiguration


# Define the function that calls the model


# 初始化supervisor
async def call_supervisor(
		state: State, config: RunnableConfig
) -> Dict[str, List[AIMessage]]:
	"""Call the LLM powering our "agent".

    This function prepares the prompt, initializes the model, and processes the response.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message.
    """
	configuration = Configuration.from_runnable_config(config)

	# Initialize the model with tool binding. Change the model or add more tools here.
	model = load_chat_model(configuration.model)
	if not configuration.workflow:
		configuration.workflow = [
			WorkflowNode(
				name="__start__",
				description="负责初始化,初始化MCP代码生成Team配置"
			),
			WorkflowNode(
				name="analyse_agent",
				description="负责需求分析,输入笼统的需求str,输出为可以用代码实现的具体需求分析json"
			),
			WorkflowNode(
				name="codegen_agent",
				description="负责代码生成,输入可以用代码实现的具体需求json,输出对应代码实现list"
			),
			WorkflowNode(
				name="compose_agent",
				description="负责代码整合,输入代码片段list,输出Typescript实现的完整MCP代码"
			)
		]
	if not state.current_step:
		state.current_step = configuration.workflow[0].name

	# Format the system prompt. Customize this to change the agent's behavior.
	system_message = configuration.system_prompt.format(
		members="\n".join([f"- {node.name}: {node.description}" for node in configuration.workflow]),
		next_step=update_next_step(state, configuration)
	)

	# 将prompt嵌入到最后一条消息前
	tmp_message = []
	tmp_message.extend(state.messages[:-1])
	tmp_message.append({"role": "system", "content": system_message})
	tmp_message.append(state.messages[-1])
	try:
		response = cast(
			AIMessage,
			await model.ainvoke(
				tmp_message, config
			),
		)
	except Exception as e:
		print(f"Error type: {type(e).__name__}")
		print(f"Error message: {str(e)}")
		# Instead of exiting, return an error message that can be handled by the system
		return {
			"messages": [*state.messages, AIMessage(content=f"Error in supervisor: {str(e)}")],
			"members": state.members,
			"current_step": state.current_step
		}

	# 更新go_next_step
	if not response.content:
		go_next_step = True
	else:
		# Ensure the response is either "true" or "false", default to True for unexpected responses
		content = response.content.strip().lower()
		if content in ["true", "false"]:
			go_next_step = content == "true"
		else:
			print(f"Warning: Unexpected response from supervisor: {content}. Defaulting to False.")
			go_next_step = False

	# 更新current_step
	if go_next_step:
		next_step = update_next_step(state, configuration)
		
		# 检查是否需要跳过步骤
		if next_step == "compose_agent" and not hasattr(state, 'codegen_result'):
			print("Warning: Cannot proceed to compose_agent without code generation result. Staying at current step.")
			go_next_step = False
		elif next_step == "codegen_agent" and not hasattr(state, 'analyse_result'):
			print("Warning: Cannot proceed to codegen_agent without analysis result. Staying at current step.")
			go_next_step = False
		else:
			state.current_step = next_step
	
	print("goto ", state.current_step)
	# Handle the case when it's the last step and the model still wants to use a tool
	if state.is_last_step and response.tool_calls:
		return {
			"messages": [
				AIMessage(
					id=response.id,
					content="Sorry, I could not find an answer to your question in the specified number of steps.",
				)
			]
		}

	# agent完成后写入代码
	if state.current_step == "__end__":
		pass
		
	return {
		"messages": state.messages,
		"members": state.members,
		"current_step": state.current_step
	}


# Define a new graph

builder = StateGraph(State, input=InputState, config_schema=Configuration)

# Define the two nodes we will cycle between
builder.add_node("call_supervisor", call_supervisor)

# Set the entrypoint as `call_model`
# This means that this node is the first one called
builder.add_edge("__start__", "call_supervisor")


def route_model_output(state: State) -> Literal[
	"call_supervisor", "analyse_agent", "codegen_agent", "compose_agent", "__end__"
]:
	"""
	根据supervisor的判断决定是否进入相应流程
	修改configuration.workflow时,请修改此处
	"""
	if state.current_step == "__start__":
		return "call_supervisor"
	
	# Validate that current_step is a valid step
	valid_steps = ["call_supervisor", "analyse_agent", "codegen_agent", "compose_agent", "__end__"]
	if state.current_step not in valid_steps:
		print(f"Warning: Invalid step '{state.current_step}'. Defaulting to 'call_supervisor'.")
		return "call_supervisor"
	
	return state.current_step


# Add a conditional edge to determine the next step after `call_model`
builder.add_conditional_edges(
	"call_supervisor",
	# After call_model finishes running, the next node(s) are scheduled
	# based on the output from route_model_output
	route_model_output,
)


# TODO 将analyse_history,last_human_message打包到input_message
async def call_analyse(
		state: State, config: RunnableConfig
) -> Dict[str, List[AIMessage]]:
	"""需求分析Team, 实现在 ./analysis_agent"""
	print("call_analyse...")
	last_human_message = state.messages[-1]
	print(last_human_message)
	if not isinstance(last_human_message, HumanMessage):
		raise ValueError(
			f"Expected AIMessage in output edges, but got {type(last_human_message).__name__}"
		)
	input_message = AnalysisInputState(messages=last_human_message)
	analysis_cfg_obj = AnalysisConfiguration()
	analysis_runconfig = RunnableConfig(
		configurable={
			"system_prompt": analysis_cfg_obj.system_prompt,
			"model": analysis_cfg_obj.model,
			"max_search_results": analysis_cfg_obj.max_search_results,
		}
	)
	try:
		response = await AnalysisGraph.ainvoke(input=input_message, config=analysis_runconfig)

		analysis_messages = response["messages"]
		last_message = analysis_messages[-1]
		
		# Try to extract state information from the last message
		try:
			# Check if the last message contains state data in JSON format
			state_data = json.loads(last_message.content)
			if isinstance(state_data, dict) and "analyse_result" in state_data:
				# Extract the analysis result from the state data
				analysis_result = json.loads(state_data["analyse_result"]) if isinstance(state_data["analyse_result"], str) else state_data["analyse_result"]
				analysis_result["original_requirement"] = last_human_message.content
				print("Extracted analyse result from state data")
			else:
				# If the last message doesn't contain state data, parse it as the analysis result
				analysis_result = json.loads(get_json(extract_content(last_message)))
				analysis_result["original_requirement"] = last_human_message.content
				print("analyse result: ", last_message)
		except (json.JSONDecodeError, AttributeError, KeyError) as e:
			print(f"Error parsing analysis result: {str(e)}")
			# Create a default analysis result if parsing fails
			analysis_result = {
				"original_requirement": last_human_message.content,
				"error": f"Failed to parse analysis result: {str(e)}",
				"requirements": [{"description": "Please try again with a clearer requirement"}]
			}
	except Exception as e:
		print(f"Error in analysis agent: {str(e)}")
		return {
			"messages": [*state.messages, AIMessage(content=f"Error in analysis agent: {str(e)}")],
			"requirement": last_human_message,
			"analyse_history": [],
			"analyse_result": HumanMessage(content=json.dumps({"error": str(e)}, ensure_ascii=False)),
		}

	# TODO 当前不支持多轮访问analysis agent(覆盖历史记录)
	return {
		"messages": [*state.messages, analysis_messages[-1]],
		"requirement": last_human_message,
		"analyse_history": [analysis_messages],
		"analyse_result": HumanMessage(content=json.dumps(analysis_result, ensure_ascii=False)),
	}


builder.add_node("analyse_agent", call_analyse)
builder.add_edge("analyse_agent", "call_supervisor")


async def call_codegen(
		state: State, config: RunnableConfig
) -> Dict[str, List[AIMessage]]:
	"""代码生成Team, 实现在 ./generate_agent"""
	# 打包需求分析结果作为输入
	input_message = CodegenInputState(messages=state.analyse_result)
	codegen_cfg_obj = CodegenConfiguration()
	codegen_runconfig = RunnableConfig(
		configurable={
			"system_prompt": codegen_cfg_obj.system_prompt,
			"model": codegen_cfg_obj.model,
			"max_search_results": codegen_cfg_obj.max_search_results,
		}
	)
	try:
		response = await CodegenGraph.ainvoke(input=input_message, config=codegen_runconfig)
		print("codegen result:", response)
		
		# Try to extract state information from the last message
		if "messages" in response and response["messages"]:
			last_message = response["messages"][-1]
			try:
				# Check if the last message contains state data in JSON format
				state_data = json.loads(last_message.content)
				if isinstance(state_data, dict) and "code" in state_data:
					# Extract the code from the state data
					code_result = state_data["code"]
					print("Extracted code from state data")
				else:
					# If the last message doesn't contain state data, use it as the code result
					code_result = last_message.content
			except (json.JSONDecodeError, AttributeError) as e:
				print(f"Error parsing codegen result: {str(e)}")
				# Fallback to checking the state
				if "state" in response and hasattr(response["state"], "code"):
					code_result = response["state"].code
				elif isinstance(response, dict) and "state" in response and isinstance(response["state"], dict) and "code" in response["state"]:
					code_result = response["state"]["code"]
				else:
					print("Warning: Unexpected response structure from codegen agent")
					code_result = "// Error: Could not generate code properly. Please check the requirements and try again."
		else:
			# Fallback to checking the state
			if "state" in response and hasattr(response["state"], "code"):
				code_result = response["state"].code
			elif isinstance(response, dict) and "state" in response and isinstance(response["state"], dict) and "code" in response["state"]:
				code_result = response["state"]["code"]
			else:
				print("Warning: Unexpected response structure from codegen agent")
				code_result = "// Error: Could not generate code properly. Please check the requirements and try again."

		return {
			"messages": [*state.messages, AIMessage(content=code_result)],
			"codegen_history": [response.get("messages", [])],
			"codegen_result": HumanMessage(content=code_result),
		}
	except Exception as e:
		error_message = f"Error in code generation: {str(e)}"
		print(error_message)
		return {
			"messages": [*state.messages, AIMessage(content=error_message)],
			"codegen_history": [],
			"codegen_result": HumanMessage(content="// " + error_message),
		}


builder.add_node("codegen_agent", call_codegen)
builder.add_edge("codegen_agent", "call_supervisor")


async def call_compose(
		state: State, config: RunnableConfig
) -> Dict[str, List[AIMessage]]:
	"""Compose agent for generating package.json, tsconfig.json, and README.md files.
	
	This function takes the code generated by the codegen agent and passes it to the compose agent,
	which generates the necessary configuration files and saves them to the result directory.
	"""
	print("call_compose...")
	input_message = ComposeInputState(messages=state.codegen_result)
	compose_cfg_obj = ComposeConfiguration()
	compose_runconfig = RunnableConfig(
		configurable={
			"system_prompt": compose_cfg_obj.system_prompt,
			"model": compose_cfg_obj.model,
			"max_search_results": compose_cfg_obj.max_search_results,
		}
	)
	
	try:
		response = await ComposeGraph.ainvoke(input=input_message, config=compose_runconfig)

		if "messages" not in response:
			print("Warning: No messages in compose agent response")
			compose_messages = []
		else:
			compose_messages = response["messages"]
			print("compose result:", compose_messages[-1] if compose_messages else "No messages")
		
		# Try to extract state information from the last message
		package_json = ""
		tsconfig_json = ""
		readme_md = ""
		
		if compose_messages and len(compose_messages) > 0:
			last_message = compose_messages[-1]
			try:
				# Check if the last message contains state data in JSON format
				state_data = json.loads(last_message.content)
				if isinstance(state_data, dict):
					if "package_json" in state_data:
						package_json = state_data["package_json"]
						print("Extracted package.json from state data")
					if "tsconfig_json" in state_data:
						tsconfig_json = state_data["tsconfig_json"]
						print("Extracted tsconfig.json from state data")
					if "readme_md" in state_data:
						readme_md = state_data["readme_md"]
						print("Extracted README.md from state data")
			except (json.JSONDecodeError, AttributeError) as e:
				print(f"Error parsing compose result: {str(e)}")
				# Fallback to checking the response object
				if isinstance(response, dict) and "package_json" in response:
					package_json = response["package_json"]
				elif hasattr(response, "package_json") and response.package_json:
					package_json = response.package_json
					
				if isinstance(response, dict) and "tsconfig_json" in response:
					tsconfig_json = response["tsconfig_json"]
				elif hasattr(response, "tsconfig_json") and response.tsconfig_json:
					tsconfig_json = response.tsconfig_json
					
				if isinstance(response, dict) and "readme_md" in response:
					readme_md = response["readme_md"]
				elif hasattr(response, "readme_md") and response.readme_md:
					readme_md = response.readme_md
		else:
			# Fallback to checking the response object
			if isinstance(response, dict) and "package_json" in response:
				package_json = response["package_json"]
			elif hasattr(response, "package_json") and response.package_json:
				package_json = response.package_json
				
			if isinstance(response, dict) and "tsconfig_json" in response:
				tsconfig_json = response["tsconfig_json"]
			elif hasattr(response, "tsconfig_json") and response.tsconfig_json:
				tsconfig_json = response.tsconfig_json
				
			if isinstance(response, dict) and "readme_md" in response:
				readme_md = response["readme_md"]
			elif hasattr(response, "readme_md") and response.readme_md:
				readme_md = response.readme_md
		
		# Create result directory if it doesn't exist
		result_dir = Path("result")
		result_dir.mkdir(exist_ok=True)
		
		try:
			# Save the index.ts file from the codegen result
			with open(result_dir / "index.ts", "w", encoding="utf-8") as f:
				f.write(state.codegen_result.content)
			
			# Save the package.json file if it exists
			if package_json:
				with open(result_dir / "package.json", "w", encoding="utf-8") as f:
					f.write(package_json)
			
			# Save the tsconfig.json file if it exists
			if tsconfig_json:
				with open(result_dir / "tsconfig.json", "w", encoding="utf-8") as f:
					f.write(tsconfig_json)
			
			# Save the README.md file if it exists
			if readme_md:
				with open(result_dir / "README.md", "w", encoding="utf-8") as f:
					f.write(readme_md)
		except Exception as e:
			print(f"Error saving files: {str(e)}")
			
		# Create a summary message
		summary = f"""Successfully generated MCP server files:
- index.ts: Main server implementation
- package.json: Project configuration with dependencies
- tsconfig.json: TypeScript configuration
- README.md: Documentation

All files have been saved to the 'result' directory.
"""
		
		final_message = AIMessage(content=summary)
		
		return {
			"messages": [*state.messages, final_message],
			"code": state.codegen_result.content,
			"compose_history": [compose_messages],
		}
		
	except Exception as e:
		error_message = f"Error in compose agent: {str(e)}"
		print(error_message)
		return {
			"messages": [*state.messages, AIMessage(content=error_message)],
			"compose_history": [],
		}


builder.add_node("compose_agent", call_compose)
builder.add_edge("compose_agent", "call_supervisor")

# Compile the builder into an executable graph
# You can customize this by adding interrupt points for state updates
graph = builder.compile(
	interrupt_before=[],  # Add node names here to update state before they're called
	interrupt_after=[],  # Add node names here to update state after they're called
)
graph.name = "Supervisor"  # This customizes the name in LangSmith
