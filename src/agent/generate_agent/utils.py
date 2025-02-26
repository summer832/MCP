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
	if not string or string.strip() == "":
		return json.dumps({"error": "Empty input string"})

	# Remove newlines and common formatting that might interfere with JSON parsing
	string = string.replace('\\n', '')

	# First try: direct parsing
	try:
		json.loads(string)
		return string
	except json.JSONDecodeError:
		pass

	# Second try: find the first occurrence of '{' and the last occurrence of '}'
	# This handles cases where there's descriptive text before and after the JSON
	try:
		start_idx = string.find('{')
		end_idx = string.rfind('}')

		if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
			json_str = string[start_idx:end_idx + 1]
			# Validate that the extracted string is valid JSON
			json.loads(json_str)
			return json_str
	except json.JSONDecodeError:
		pass

	# Third try: extract JSON using regex - more aggressive pattern matching
	try:
		# This pattern looks for the largest JSON-like structure in the string
		json_str = re.search(r'\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\}))*\}))*\}', string, re.DOTALL)
		if json_str:
			json_str = json_str.group()
			# Validate that the extracted string is valid JSON
			json.loads(json_str)
			return json_str
	except (AttributeError, json.JSONDecodeError):
		pass

	# Fourth try: handle potentially truncated JSON
	try:
		# Count opening and closing braces
		open_braces = string.count('{')
		close_braces = string.count('}')

		# If there are more opening braces than closing, the JSON might be truncated
		if open_braces > close_braces:
			# Find the first opening brace
			start_idx = string.find('{')
			if start_idx != -1:
				# Extract from the first opening brace to the end
				partial_json = string[start_idx:]
				# Add missing closing braces
				missing_braces = open_braces - close_braces
				fixed_string = partial_json + ('}' * missing_braces)

				# Try to parse the fixed string
				json.loads(fixed_string)
				print(f"Fixed truncated JSON by adding {missing_braces} closing braces")
				return fixed_string
	except json.JSONDecodeError:
		pass

	# If all attempts fail, return a valid JSON error object
	print(f"Error extracting JSON from string: {string[:100]}..." if len(string) > 100 else string)
	return json.dumps({
		"error": "Failed to extract valid JSON",
		"original": string[:500] + "..." if len(string) > 500 else string
	})


def extract_content(response) -> str:
	"""统一处理不同格式的response content，转换为字符串"""
	if response is None:
		return ""
		
	try:
		content = response.content
	except AttributeError:
		# If response doesn't have a content attribute, try to use it directly
		content = response
		
	# 如果content是None，返回空字符串
	if content is None:
		return ""

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
			# 如果是其他类型，尝试转换为字符串
			else:
				try:
					texts.append(str(item))
				except:
					pass
		return " ".join(texts)
		
	# 如果content是字典
	if isinstance(content, dict):
		# 如果包含text字段，返回text
		if "text" in content:
			return content["text"]
		# 如果包含content字段，递归处理
		elif "content" in content:
			return extract_content(content["content"])
		# 否则转换整个字典为字符串
		else:
			try:
				return json.dumps(content)
			except:
				return str(content)

	# 如果是其他类型，转换为字符串
	try:
		return str(content)
	except:
		return "Error: Could not extract content"
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
		try:
			return init_chat_model(
				model,
				model_provider="anthropic",
				base_url="https://api.openai-proxy.org/anthropic",
				api_key=anthropic_api_key
			)
		except Exception as e:
			print(f"Error initializing Anthropic model: {str(e)}")
			# Try without thread_id if that's causing issues
			if "thread_id" in str(e):
				print("Trying to initialize model without thread_id...")
				return init_chat_model(
					model,
					model_provider="anthropic",
					base_url="https://api.openai-proxy.org/anthropic",
					api_key=anthropic_api_key,
					thread_id=None
				)
			raise e
	return init_chat_model(model, model_provider=provider)
