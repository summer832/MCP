"""Define a custom Reasoning and Action agent for composing MCP server files.

Works with a chat model to generate package.json, tsconfig.json, and README.md files.
"""
import json
import re
from typing import Dict, List, Literal, cast

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from agent.compose_agent.configuration import Configuration
from agent.compose_agent.state import InputState, State
from agent.compose_agent.tools import TOOLS
from pathlib import Path

from agent.compose_agent.utils import load_chat_model, is_valid_json
from agent.compose_agent.prompts import PACKAGE_PROMPT, CONFIG_PROMPT, README_PROMPT, COMPOSE_PROMPT, SYSTEM_PROMPT

from tenacity import retry, stop_after_attempt, wait_exponential, wait_fixed, wait_combine


# 重试机制,防止API不稳定
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
    """Call the LLM to analyze the code and prepare for file generation.

    This function prepares the prompt, initializes the model, and processes the response.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message.
    """
    configuration = Configuration.from_runnable_config(config)

    # Initialize the model with tool binding
    model = load_chat_model(configuration.model).bind_tools(TOOLS)

    # Get the code from the input message
    code_content = state.messages[0].content

    # Format the system prompt with the compose prompt
    system_message = COMPOSE_PROMPT.format(code=code_content)
    
    # Get the model's response
    response = cast(
        AIMessage,
        await call_model_with_retry(
            model,
            [{"role": "system", "content": system_message}, 
             HumanMessage(content="Please analyze this code and generate package.json, tsconfig.json, and README.md files.")],
            config
        ),
    )

    # Handle the case when it's the last step and the model still wants to use a tool
    if state.is_last_step and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not generate the required files in the specified number of steps.",
                )
            ]
        }

    # Store the code for later use
    return {
        "messages": [*state.messages, response],
        "code": code_content
    }


async def generate_package_json(
        state: State, config: RunnableConfig
) -> Dict[str, List[AIMessage]]:
    """Generate the package.json file for the MCP server.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message.
    """
    configuration = Configuration.from_runnable_config(config)

    # Initialize the model
    model = load_chat_model(configuration.model)

    # Format the package prompt with the code
    package_prompt = PACKAGE_PROMPT.format(code=state.code)
    
    # Get the model's response
    response = cast(
        AIMessage,
        await call_model_with_retry(
            model,
            [{"role": "system", "content": package_prompt}],
            config
        ),
    )

    # Extract the package.json content
    package_json = extract_code_block(response.content, "json")
    
    return {
        "messages": [*state.messages, response],
        "package_json": package_json
    }


async def generate_tsconfig_json(
        state: State, config: RunnableConfig
) -> Dict[str, List[AIMessage]]:
    """Generate the tsconfig.json file for the MCP server.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message.
    """
    configuration = Configuration.from_runnable_config(config)

    # Initialize the model
    model = load_chat_model(configuration.model)

    # Format the config prompt with the code
    config_prompt = CONFIG_PROMPT.format(code=state.code)
    
    # Get the model's response
    response = cast(
        AIMessage,
        await call_model_with_retry(
            model,
            [{"role": "system", "content": config_prompt}],
            config
        ),
    )

    # Extract the tsconfig.json content
    tsconfig_json = extract_code_block(response.content, "json")
    
    return {
        "messages": [*state.messages, response],
        "tsconfig_json": tsconfig_json
    }


async def generate_readme_md(
        state: State, config: RunnableConfig
) -> Dict[str, List[AIMessage]]:
    """Generate the README.md file for the MCP server.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message.
    """
    configuration = Configuration.from_runnable_config(config)

    # Initialize the model
    model = load_chat_model(configuration.model)

    # Format the readme prompt with the code
    readme_prompt = README_PROMPT.format(code=state.code)
    
    # Get the model's response
    response = cast(
        AIMessage,
        await call_model_with_retry(
            model,
            [{"role": "system", "content": readme_prompt}],
            config
        ),
    )

    # Extract the README.md content (no need for code block extraction as it's markdown)
    readme_md = response.content
    
    return {
        "messages": [*state.messages, response],
        "readme_md": readme_md
    }


async def compile_results(
        state: State, config: RunnableConfig
) -> Dict[str, List[AIMessage]]:
    """Compile all generated files into a final result.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the final result.
    """
    # Create a result directory if it doesn't exist
    result_dir = Path("result")
    result_dir.mkdir(exist_ok=True)
    
    # Write the index.ts file
    with open(result_dir / "index.ts", "w", encoding="utf-8") as f:
        f.write(state.code)
    
    # Write the package.json file
    with open(result_dir / "package.json", "w", encoding="utf-8") as f:
        f.write(state.package_json)
    
    # Write the tsconfig.json file
    with open(result_dir / "tsconfig.json", "w", encoding="utf-8") as f:
        f.write(state.tsconfig_json)
    
    # Write the README.md file
    with open(result_dir / "README.md", "w", encoding="utf-8") as f:
        f.write(state.readme_md)
    
    # Create a summary message
    summary = f"""Successfully generated MCP server files:
- index.ts: Main server implementation
- package.json: Project configuration with dependencies
- tsconfig.json: TypeScript configuration
- README.md: Documentation

All files have been saved to the 'result' directory.
"""
    
    # Store state information in a new message
    # This ensures that state data is preserved without relying on MemorySaver
    state_data = {
        "code": state.code if hasattr(state, "code") else "",
        "package_json": state.package_json if hasattr(state, "package_json") else "",
        "tsconfig_json": state.tsconfig_json if hasattr(state, "tsconfig_json") else "",
        "readme_md": state.readme_md if hasattr(state, "readme_md") else "",
        "final_result": summary
    }
    
    # Create a new response with state information embedded
    final_response = AIMessage(content=json.dumps(state_data, ensure_ascii=False))
    
    return {
        "messages": [*state.messages, final_response],
        "final_result": summary
    }


def extract_code_block(content, language=None):
    """Extract code block from markdown content.
    
    Args:
        content (str): The markdown content.
        language (str, optional): The language of the code block. Defaults to None.
        
    Returns:
        str: The extracted code block.
    """
    import re
    
    # Pattern to match code blocks with or without language specification
    if language:
        pattern = rf"```(?:{language})?\n(.*?)```"
    else:
        pattern = r"```(?:\w+)?\n(.*?)```"
    
    matches = re.findall(pattern, content, re.DOTALL)
    
    if matches:
        return matches[0].strip()
    
    # If no code block is found, return the content as is
    return content.strip()


# Define a new graph
builder = StateGraph(State, input=InputState, config_schema=Configuration)

# Define the nodes
builder.add_node("analyze_code", call_model)
builder.add_node("generate_package_json", generate_package_json)
builder.add_node("generate_tsconfig_json", generate_tsconfig_json)
builder.add_node("generate_readme_md", generate_readme_md)
builder.add_node("compile_results", compile_results)
builder.add_node("tools", ToolNode(TOOLS))

# Set the entrypoint
builder.add_edge("__start__", "analyze_code")

# Define the workflow
builder.add_edge("analyze_code", "generate_package_json")
builder.add_edge("generate_package_json", "generate_tsconfig_json")
builder.add_edge("generate_tsconfig_json", "generate_readme_md")
builder.add_edge("generate_readme_md", "compile_results")
builder.add_edge("compile_results", "__end__")

# Add tool handling
def route_model_output(state: State) -> Literal["__end__", "tools"]:
    """Determine if tools need to be called.

    Args:
        state (State): The current state of the conversation.

    Returns:
        str: The name of the next node to call.
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

# Add conditional edges for tool handling
builder.add_conditional_edges(
    "analyze_code",
    route_model_output,
)
builder.add_edge("tools", "analyze_code")

# Compile the builder into an executable graph
graph = builder.compile(
    interrupt_before=[],
    interrupt_after=[],
)
graph.name = "Compose Agent"
