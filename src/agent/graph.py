"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""
import re
from datetime import datetime, timezone
from typing import Dict, List, Literal, cast

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph

from agent.configuration import Configuration
from agent.state import InputState, State
from agent.utils import load_chat_model

from agent.analysis_agent import graph as AnalysisGraph
from agent.analysis_agent.state import InputState as AnalysisInputState
from agent.analysis_agent.configuration import Configuration as AnalysisConfiguration


# Define the function that calls the model


# 初始化supervisor的prompt,发送问候并
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

	# 初始化
	if not state.members:
		state.members = {
			"analyse_agent": "负责需求分析,输入笼统的需求str,输出为可以用代码实现的具体需求分析json",
			"codegen_agent": "负责代码生成,输入可以用代码实现的具体需求json,输出对应代码实现list",
			"compose_agent": "负责代码整合,输入代码片段list,输出Typescript实现的完整MCP代码"
		}
		state.next_step = "analyse_agent"

	# Format the system prompt. Customize this to change the agent's behavior.
	system_message = configuration.system_prompt.format(
		members=state.members,
		next_step=state.next_step
	)

	print("supervisor last message", state.messages[-1])
	# Get the model's response, 仅跟进当前进度, 不需要历史记录
	try:
		response = cast(
			AIMessage,
			await model.ainvoke(
				[{"role": "system", "content": system_message}, state.messages[-1]], config
			),
		)
	except Exception as e:
		print(f"Error type: {type(e).__name__}")
		print(f"Error message: {str(e)}")
		exit(0)

	# supervisor可能不回复,返回空串
	if not response.content:
		state.go_next_step = True
	else:
		state.go_next_step = response.content == "true"
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

	# supervisor的判断不显示给user
	return {
		"messages": [AIMessage(content=f"goto {state.next_step}: {response.content}")],
		"members": state.members,
		"go_next_step": state.go_next_step,
		"next_step": state.next_step
	}


# Define a new graph

builder = StateGraph(State, input=InputState, config_schema=Configuration)

# Define the two nodes we will cycle between
builder.add_node("call_supervisor", call_supervisor)

# Set the entrypoint as `call_model`
# This means that this node is the first one called
builder.add_edge("__start__", "call_supervisor")


def route_model_output(state: State) -> Literal[
	"__end__", "generate", "analyse", "compose"]:
	"""根据supervisor的判断决定是否进入相应流程"""
	if state.go_next_step == "false":
		print("processing error.")
		return "__end__"

	if state.next_step == "analyse_agent" and state.go_next_step:
		return "analyse"
	elif state.next_step == "codegen_agent" and state.go_next_step:
		state.next_step = "compose_agent"
		return "generate"
	elif state.next_step == "compose_agent" and state.go_next_step:
		state.next_step = "__end__"
		return "compose"

	return "__end__"


# Add a conditional edge to determine the next step after `call_model`
builder.add_conditional_edges(
	"call_supervisor",
	# After call_model finishes running, the next node(s) are scheduled
	# based on the output from route_model_output
	route_model_output,
)


async def call_analyse(
		state: State, config: RunnableConfig
) -> Dict[str, List[AIMessage]]:
	"""需求分析Team, 实现在 ./analysis_agent"""
	print("call_analyse...")
	last_human_message = state.messages[-2]
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
	print("analyse result:", analysis_messages)
	# 数据清洗
	last_analysis_message = analysis_messages[-1]
	last_analysis_message.content = re.search(r'\{.*\}', last_analysis_message.content[0]["text"], re.DOTALL).group()

	return {
		"messages": [last_analysis_message],
		"requirement": last_human_message,
		"analyse_history": [analysis_messages],
		"next_step": "codegen_agent"
	}


builder.add_node("analyse", call_analyse)
builder.add_edge("analyse", "call_supervisor")


async def call_codegen(
		state: State, config: RunnableConfig
) -> Dict[str, List[AIMessage]]:
	"""代码生成Team, 实现在 ./generate_agent"""
	return {"messages": [AIMessage("call_codegen")]}


builder.add_node("generate", call_codegen)
builder.add_edge("generate", "call_supervisor")


async def call_compose(
		state: State, config: RunnableConfig
) -> Dict[str, List[AIMessage]]:
	return {"messages": [AIMessage("call_compose")]}


builder.add_node("generate", call_codegen)
builder.add_edge("analyse", "call_supervisor")
builder.add_node("compose", call_compose)
builder.add_edge("analyse", "call_supervisor")

# Compile the builder into an executable graph
# You can customize this by adding interrupt points for state updates
graph = builder.compile(
	interrupt_before=[],  # Add node names here to update state before they're called
	interrupt_after=[],  # Add node names here to update state after they're called
)
graph.name = "Supervisor Agent"  # This customizes the name in LangSmith
