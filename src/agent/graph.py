"""Define a custom multi-step Reasoning and Action agent with ReAct-like structure.

Works with a chat model with tool calling support.
"""
import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Literal, cast

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
		exit(0)

	# 更新go_next_step
	if not response.content:
		go_next_step = True
	else:
		go_next_step = response.content == "true"

	# 更新current_step
	if go_next_step:
		state.current_step = update_next_step(state, configuration)
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
	response = await AnalysisGraph.ainvoke(input=input_message, config=analysis_runconfig)

	analysis_messages = response["messages"]
	analysis_result = json.loads(get_json(extract_content(analysis_messages[-1])))
	analysis_result["original_requirement"] = last_human_message.content
	print("analyse result: ", analysis_messages[-1])

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
	response = await CodegenGraph.ainvoke(input=input_message, config=codegen_runconfig)
	code_result = response["state"].code
	print("codegen result:", code_result)
	return {
		"messages": [*state.messages, AIMessage(content=code_result)],
		"codegen_history": [response["messages"]],
		"codegen_result": HumanMessage(content=code_result),
	}


builder.add_node("codegen_agent", call_codegen)
builder.add_edge("codegen_agent", "call_supervisor")


# TODO 未完成, 生成package.json, tsconfig.json, README.MD
async def call_compose(
		state: State, config: RunnableConfig
) -> Dict[str, List[AIMessage]]:
	print("call_compose...")
	code_message = state.messages[-2]
	print(code_message)
	if not isinstance(code_message, AIMessage):
		raise ValueError(
			f"Expected AIMessage in output edges, but got {type(code_message).__name__}"
		)
	input_message = ComposeInputState(messages=code_message)
	compose_cfg_obj = ComposeConfiguration()
	compose_runconfig = RunnableConfig(
		configurable={
			"system_prompt": compose_cfg_obj.system_prompt,
			"model": compose_cfg_obj.model,
			"max_search_results": compose_cfg_obj.max_search_results,
		}
	)
	response = await ComposeGraph.ainvoke(input=input_message, config=compose_runconfig)

	compose_messages = response["messages"]
	print("analyse result:", compose_messages)
	final_code = compose_messages[-1]

	# TODO 当前不支持多轮访问compose agent(覆盖历史记录)
	return {
		"messages": [*state.messages, compose_messages],
		"code": final_code,
		"compose_history": [compose_messages],
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
