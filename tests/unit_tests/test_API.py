from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

if __name__ == '__main__':
	configure = init_chat_model(
		"claude-3-opus-20240229",
		model_provider="anthropic",
		base_url="https://api.openai-proxy.org/anthropic",
		api_key="sk-fRrCJNlvVyT3xLKcLWws6kF8nZOyLGpx258b9O7R1rsszKc1"
	)

	print("Claude: " + configure.invoke("What's your name?").content)
