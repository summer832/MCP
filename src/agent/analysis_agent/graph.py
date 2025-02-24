"""requirement analyse Team, used in MCP codegen multi-agent system
"""
import json
from datetime import datetime, timezone
from typing import Dict, List, Literal, cast

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from agent.analysis_agent.configuration import Configuration
from agent.analysis_agent.state import InputState, State
from agent.analysis_agent.tools import TOOLS
from agent.analysis_agent.utils import load_chat_model, is_valid_json
from agent.analysis_agent.prompts import ANALYSIS_SYSTEM_PROMPT, REFINEMENT_SYSTEM_PROMPT, FINAL_OUTPUT_SYSTEM_PROMPT
from pathlib import Path


# Define the function that calls the model
async def call_analyse(
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
	model = load_chat_model(configuration.model).bind_tools(TOOLS)

	# Format the system prompt. Customize this to change the agent's behavior.
	system_message = ANALYSIS_SYSTEM_PROMPT
	# Get the model's response
	response = cast(
		AIMessage,
		await model.ainvoke(
			[{"role": "system", "content": system_message}, *state.messages], config
		),
	)

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
	last_message = state.messages[-1]

	# Return the model's response as a list to be added to existing messages
	return {
		"messages": [*state.messages, response],
		"requirement": last_message
	}


# Define a new graph

builder = StateGraph(State, input=InputState, config_schema=Configuration)

# Define the two nodes we will cycle between
builder.add_node(call_analyse)
builder.add_edge("__start__", "call_analyse")


# builder.add_node("tools", ToolNode(TOOLS))
# builder.add_edge("tools", "call_analyse")


async def call_refine(
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
	model = load_chat_model(configuration.model).bind_tools(TOOLS)

	# Format the system prompt. Customize this to change the agent's behavior.
	system_message = REFINEMENT_SYSTEM_PROMPT
	# Get the model's response
	response = cast(
		AIMessage,
		await model.ainvoke(
			[*state.messages, {"role": "system", "content": system_message}], config
		),
	)

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

	# Return the model's response as a list to be added to existing messages
	return {"messages": [*state.messages, response]}


builder.add_node(call_refine)
builder.add_edge("call_analyse", "call_refine")


# builder.add_edge("tools", "call_refine")


async def call_output(
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
	model = load_chat_model(configuration.model).bind_tools(TOOLS)

	# Format the system prompt. Customize this to change the agent's behavior.
	system_message = FINAL_OUTPUT_SYSTEM_PROMPT
	# Get the model's response
	response = cast(
		AIMessage,
		await model.ainvoke(
			[*state.messages, {"role": "system", "content": system_message}], config
		),
	)

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
	# TODO 隐藏analysis agent的思考过程,保存agent的需求与结果
	# Return the model's response as a list to be added to existing messages
	return {"messages": [state.requirement, response]}


builder.add_node(call_output)
builder.add_edge("call_refine", "call_output")
builder.add_edge("call_output", "__end__")
# builder.add_edge("tools", "call_output")


# def route_model_output(state: State) -> Literal["__end__", "tools"]:
# 	"""Determine the next node based on the model's output.
#
#     This function checks if the model's last message contains tool calls.
#
#     Args:
#         state (State): The current state of the conversation.
#
#     Returns:
#         str: The name of the next node to call ("__end__" or "tools").
#     """
# 	last_message = state.messages[-1]
# 	if not isinstance(last_message, AIMessage):
# 		raise ValueError(
# 			f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
# 		)
# 	# If there is no tool call, then we finish
# 	if not last_message.tool_calls:
# 		return "__end__"
# 	# Otherwise we execute the requested actions
# 	return "tools"
#
#
# # Add a conditional edge to determine the next step after `call_model`
# builder.add_conditional_edges(
# 	"call_model",
# 	# After call_model finishes running, the next node(s) are scheduled
# 	# based on the output from route_model_output
# 	route_model_output,
# )

# Compile the builder into an executable graph
# You can customize this by adding interrupt points for state updates
graph = builder.compile(
	interrupt_before=[],  # Add node names here to update state before they're called
	interrupt_after=[],  # Add node names here to update state after they're called
)
graph.name = "Analyse Agent"  # This customizes the name in LangSmith
