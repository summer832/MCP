"""Utility & helper functions."""
import re
import os
import json
from pathlib import Path
from typing import Optional

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
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
	"""Extract JSON from a string.
	
	Args:
		string (str): The string that may contain JSON.
		
	Returns:
		str: The extracted JSON string.
		
	Raises:
		ValueError: If no valid JSON is found in the string.
	"""
	# Remove escaped newlines that might interfere with JSON parsing
	string = string.replace('\\n', '')
	
	# First, try to parse the entire string as JSON
	try:
		json.loads(string)
		return string
	except json.JSONDecodeError:
		# If that fails, try to find JSON objects using regex
		try:
			# Look for JSON objects (starting with { and ending with })
			json_match = re.search(r'\{.*\}', string, re.DOTALL)
			if json_match:
				json_str = json_match.group()
				# Validate that it's actually valid JSON
				json.loads(json_str)
				return json_str
			
			# If no JSON object is found, look for JSON arrays (starting with [ and ending with ])
			json_array_match = re.search(r'\[.*\]', string, re.DOTALL)
			if json_array_match:
				json_str = json_array_match.group()
				# Validate that it's actually valid JSON
				json.loads(json_str)
				return json_str
			
			# If we get here, no valid JSON was found
			raise ValueError("No valid JSON found in the string")
		except json.JSONDecodeError:
			# If the regex match isn't valid JSON, try a more conservative approach
			# by looking for properly formatted JSON with balanced braces
			depth = 0
			start_idx = -1
			
			for i, char in enumerate(string):
				if char == '{' and (start_idx == -1 or depth == 0):
					if start_idx == -1:
						start_idx = i
					depth += 1
				elif char == '{':
					depth += 1
				elif char == '}':
					depth -= 1
					if depth == 0 and start_idx != -1:
						# Found a potential JSON object
						potential_json = string[start_idx:i+1]
						try:
							json.loads(potential_json)
							return potential_json
						except json.JSONDecodeError:
							# Not valid JSON, continue searching
							pass
			
			# If we get here, no valid JSON was found
			raise ValueError("No valid JSON found in the string")


def is_valid_json(string: str) -> bool:
	"""Check if a string is valid JSON.
	
	Args:
		string (str): The string to check.
		
	Returns:
		bool: True if the string is valid JSON, False otherwise.
	"""
	if not string or not isinstance(string, str):
		return False
		
	# Remove escaped newlines that might interfere with JSON parsing
	string = string.replace('\\n', '')
	
	try:
		json.loads(string)
		return True
	except json.JSONDecodeError:
		# Try to extract JSON using get_json and see if that works
		try:
			get_json(string)
			return True
		except (ValueError, json.JSONDecodeError):
			return False


def get_message_text(msg: BaseMessage) -> str:
	"""Get the text content of a message.
	
	This function extracts the text content from a BaseMessage object, handling
	different content formats (string, dict, or list).
	
	Args:
		msg (BaseMessage): The message to extract text from.
		
	Returns:
		str: The extracted text content.
	"""
	if msg is None:
		return ""
		
	content = msg.content
	
	if isinstance(content, str):
		return content
	elif isinstance(content, dict):
		# If content is a dict, try to get the "text" field
		return content.get("text", "")
	elif isinstance(content, list):
		# If content is a list, concatenate all text parts
		txts = []
		for c in content:
			if isinstance(c, str):
				txts.append(c)
			elif isinstance(c, dict) and "text" in c:
				txts.append(c.get("text", ""))
		return "".join(txts).strip()
	else:
		# Fallback for any other type
		return str(content)


def load_chat_model(fully_specified_name: str) -> BaseChatModel:
	"""Load a chat model from a fully specified name.

    This function initializes a chat model based on the provider and model name.
    It handles different providers (e.g., anthropic, openai) with their specific
    initialization requirements.

    Args:
        fully_specified_name (str): String in the format 'provider/model'.
        
    Returns:
        BaseChatModel: The initialized chat model.
        
    Raises:
        ValueError: If the fully_specified_name is not in the correct format or
                   if the provider is not supported.
    """
	if not fully_specified_name or "/" not in fully_specified_name:
		raise ValueError(f"Invalid model name format: {fully_specified_name}. Expected format: 'provider/model'")
		
	try:
		provider, model = fully_specified_name.split("/", maxsplit=1)
		
		if provider == "anthropic":
			if not anthropic_api_key:
				raise ValueError("Anthropic API key is not set. Please set the ANTHROPIC_API_KEY environment variable.")
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
		elif provider == "openai":
			if not openai_api_key:
				raise ValueError("OpenAI API key is not set. Please set the OPENAI_API_KEY environment variable.")
			return init_chat_model(model, model_provider="openai", api_key=openai_api_key)
		else:
			# For other providers, use the default initialization
			return init_chat_model(model, model_provider=provider)
	except Exception as e:
		raise ValueError(f"Error initializing chat model: {str(e)}")
