"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""
import json
from datetime import datetime, timezone
from typing import Dict, List, Literal, cast

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from agent.generate_agent.configuration import Configuration
from agent.generate_agent.state import InputState, State
from agent.generate_agent.tools import TOOLS
from agent.generate_agent.prompts import COMPOSE_PROMPT,REVISE_PROMPT,DATABASE_EXAMPLE
from pathlib import Path


# Define the function that calls the model

# TODO 代码检查-代码修正循环调用
async def call_model(
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
	# TODO 这里应该访问代码生成模块,目前用example填补
	return {
		"messages": [*state.messages, AIMessage(content=DATABASE_EXAMPLE)],
	}


# Define a new graph

builder = StateGraph(State, input=InputState, config_schema=Configuration)

# Define the two nodes we will cycle between
builder.add_node(call_model)
builder.add_node("tools", ToolNode(TOOLS))

# Set the entrypoint as `call_model`
# This means that this node is the first one called
builder.add_edge("__start__", "call_model")


def route_model_output(state: State) -> Literal["__end__", "tools"]:
	"""Determine the next node based on the model's output.

    This function checks if the model's last message contains tool calls.

    Args:
        state (State): The current state of the conversation.

    Returns:
        str: The name of the next node to call ("__end__" or "tools").
    """
	last_message = state.messages[-1]
	if not isinstance(last_message, AIMessage):
		raise ValueError(
			f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
		)
	# If there is no tool call, then we finish
	if not last_message.tool_calls:
		return "__end__"
		# Otherwise we execute the requested actions
	return "tools"


# Add a conditional edge to determine the next step after `call_model`
builder.add_conditional_edges(
	"call_model",
	# After call_model finishes running, the next node(s) are scheduled
	# based on the output from route_model_output
	route_model_output,
)

# Add a normal edge from `tools` to `call_model`
# This creates a cycle: after using tools, we always return to the model
builder.add_edge("tools", "call_model")

# Compile the builder into an executable graph
# You can customize this by adding interrupt points for state updates
graph = builder.compile(
	interrupt_before=[],  # Add node names here to update state before they're called
	interrupt_after=[],  # Add node names here to update state after they're called
)
graph.name = "Codegen Agent"  # This customizes the name in LangSmith
