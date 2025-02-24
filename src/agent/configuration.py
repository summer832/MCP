"""Define the configurable parameters for the agent."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Annotated, Optional, List, Dict

from langchain_core.runnables import RunnableConfig, ensure_config

from agent import prompts


class WorkflowNode:
	name: str
	description: str


@dataclass(kw_only=True)
class Configuration:
	"""The configuration for the agent."""

	system_prompt: str = field(
		default=prompts.SUPERVISOR_PROMPT,
		metadata={
			"description": "The system prompt to use for the agent's interactions. "
			               "This prompt sets the context and behavior for the agent."
		},
	)

	model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = field(
		default="anthropic/claude-3-5-sonnet-20240620",
		metadata={
			"description": "The name of the language model to use for the agent's main interactions. "
			               "Should be in the form: provider/model-name."
		},
	)

	max_search_results: int = field(
		default=10,
		metadata={
			"description": "The maximum number of search results to return for each search query."
		},
	)

	# 决定了workflow步骤与顺序
	workflow: List[Dict[str, str]] = field(
		default_factory=lambda: [
			{
				"name": "__start__",
				"description": "负责初始化,初始化MCP代码生成Team配置"
			},
			{
				"name": "analyse_agent",
				"description": "负责需求分析,输入笼统的需求str,输出为可以用代码实现的具体需求分析json"
			},
			{
				"name": "codegen_agent",
				"description": "负责代码生成,输入可以用代码实现的具体需求json,输出对应代码实现list"
			},
			{
				"name": "compose_agent",
				"description": "负责代码整合,输入代码片段list,输出Typescript实现的完整MCP代码"
			}
		],
		metadata={
			"description": "工作流配置"
		}
	)

	@classmethod
	def from_runnable_config(
			cls, config: Optional[RunnableConfig] = None
	) -> Configuration:
		"""Create a Configuration instance from a RunnableConfig object."""
		config = ensure_config(config)
		configurable = config.get("configurable") or {}
		_fields = {f.name for f in fields(cls) if f.init}
		return cls(**{k: v for k, v in configurable.items() if k in _fields})
