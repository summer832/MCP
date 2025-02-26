"""Utility & helper functions."""
import json
import re

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

import os
from pathlib import Path
from dotenv import load_dotenv

# 获取.env
current_dir = Path(__file__).resolve().parent
env_path = current_dir.parent.parent / '.env'
if not env_path.exists():
	raise FileNotFoundError(f"Environment file not found at {env_path}")
load_dotenv(dotenv_path=env_path)

anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY")
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
from langchain.chat_models import init_chat_model

if __name__ == '__main__':
	configure = init_chat_model(
			"deepseek-reasoner",
			model_provider="deepseek",
			base_url="https://api.deepseek.com",
			api_key=deepseek_api_key
		)

	print("Claude: " + configure.invoke("What's your name?").content)
