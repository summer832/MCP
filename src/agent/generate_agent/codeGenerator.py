import openai
from openai import OpenAI
from typing import List

openai.api_key = 'sk-plGxjDmsvzQZAHZeA06flzwdlhdFsLZORvvhNKeJ2M9e65Ls'


class CodeGenerationInput:
	def __init__(self, queries: List[str]):
		self.queries = queries


class CodeGenerationOutput:
	def __init__(self, code: str):
		self.code = code


def generate_code(input: CodeGenerationInput) -> CodeGenerationOutput:
	queries = list(set(input.queries))  # 去除重复的查询
	generated_code = []

	for query in queries:
		code = generate_typescript_code(query)
		generated_code.append(code)

	# 合并生成的代码，并过滤掉多余的部分
	combined_code = '\n\n'.join(generated_code)
	filtered_code = filter_generated_code(combined_code)

	return CodeGenerationOutput(code=filtered_code)


def generate_typescript_code(query: str) -> str:
	client = OpenAI(
		api_key="sk-plGxjDmsvzQZAHZeA06flzwdlhdFsLZORvvhNKeJ2M9e65Ls",  # 替换为你的实际 API Key
		base_url="https://api.moonshot.cn/v1"  # 修正了 URL 格式
	)
	response = client.chat.completions.create(
		model="moonshot-v1-8k",  # 或者使用其他支持的模型
		messages=[
			{
				"role": "user",
				"content": f"根据以下查询生成TypeScript代码,能在本地数据库中执行对应的操作,除了代码外不需要任何其他内容！除了代码不生成任何其他内容：\n\n查询: {query}\n\n代码:"
			}
		],
		max_tokens=500
	)
	code = response.choices[0].message.content.strip()
	return code


def filter_generated_code(code: str) -> str:
	# 过滤掉多余的部分，例如多余的```typescript
	lines = code.split('\n')
	filtered_lines = [line for line in lines if not line.startswith('```')]
	return '\n'.join(filtered_lines)


# Example usage
input_data = CodeGenerationInput(queries=[
	'像学生表中插入一条数据，名字jack，年龄18',
	# '插入新的使用记录',
	# 可以添加更多查询
])
output = generate_code(input_data)
print(output.code)

