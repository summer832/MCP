"""Utility & helper functions."""
import re

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# 获取.env
current_dir = Path(__file__).resolve().parent
env_path = current_dir.parent.parent.parent / '.env'
if not env_path.exists():
	raise FileNotFoundError(f"Environment file not found at {env_path}")
load_dotenv(dotenv_path=env_path)

anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY")


def get_json(string: str) -> str:
	"""提取字符串的json"""
	string = string.replace('\\n', '')
	try:
		json.loads(string)
		return string
	except json.JSONDecodeError:
		return re.search(r'\{.*\}', string, re.DOTALL).group()


def extract_content(response) -> str:
	"""统一处理不同格式的response content，转换为字符串"""
	content = response.content

	# 如果content是字符串，直接返回
	if isinstance(content, str):
		return content

	# 如果content是列表
	if isinstance(content, list):
		# 提取所有text字段并拼接
		texts = []
		for item in content:
			# 如果是字典且包含text字段
			if isinstance(item, dict) and "text" in item:
				texts.append(item["text"])
			# 如果是字符串
			elif isinstance(item, str):
				texts.append(item)
		return " ".join(texts)

	# 如果是其他类型，转换为字符串
	return str(content)
def get_message_text(msg: BaseMessage) -> str:
	"""Get the text content of a message."""
	content = msg.content
	if isinstance(content, str):
		return content
	elif isinstance(content, dict):
		return content.get("text", "")
	else:
		txts = [c if isinstance(c, str) else (c.get("text") or "") for c in content]
		return "".join(txts).strip()


def load_chat_model(fully_specified_name: str) -> BaseChatModel:
	"""Load a chat model from a fully specified name.

    Args:
        fully_specified_name (str): String in the format 'provider/model'.
    """
	provider, model = fully_specified_name.split("/", maxsplit=1)
	if provider == "anthropic":
		return init_chat_model(
			model,
			model_provider="anthropic",
			base_url="https://api.openai-proxy.org/anthropic",
			api_key=anthropic_api_key
		)
	return init_chat_model(model, model_provider=provider)
