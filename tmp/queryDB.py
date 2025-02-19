import openai
import sqlite3
from openai import OpenAI  # 确保正确导入 OpenAI 类

# 设置OpenAI API密钥
openai.api_key = 'your_openai_api_key'
import mysql.connector
from mysql.connector import Error


# 创建 MySQL 数据库连接
def create_connection(host_name, user_name, user_password, db_name):
	conn = None
	try:
		conn = mysql.connector.connect(
			host=host_name,
			user=user_name,
			password=user_password,
			database=db_name
		)
		print("MySQL Database connection successful")
	except Error as e:
		print(f"数据库连接错误: {e}")
	return conn


# 将自然语言转换为SQL语句
def natural_language_to_sql(natural_language_query):
	client = OpenAI(
		api_key="sk-plGxjDmsvzQZAHZeA06flzwdlhdFsLZORvvhNKeJ2M9e65Ls",  # 替换为你的实际 API Key
		base_url="https://api.moonshot.cn/v1"  # 修正了 URL 格式
	)

	completion = client.chat.completions.create(
		model="moonshot-v1-8k",
		messages=[
			{
				"role": "user",
				"content": f"将以下自然语言查询转换为SQL语句，除了sql语言外不要其他描述，我要用你的返回直接查询数据库，不需要任何额外的内容: {natural_language_query}"
			}
		],
		temperature=0.3,
	)
	sql_query = completion.choices[0].message.content.strip()  # 修正了变量名错误
	return sql_query


# 清理生成的 SQL 语句
def clean_sql_query(sql_query):
	# 去除多余的文本和格式问题
	sql_query = sql_query.strip()
	if sql_query.startswith("```sql") and sql_query.endswith("```"):
		sql_query = sql_query[6:-3].strip()
	return sql_query


# 执行 SQL 查询并获取结果
def execute_sql_query(conn, sql_query):
	try:
		cur = conn.cursor()
		cur.execute(sql_query)
		rows = cur.fetchall()
		return rows
	except Error as e:
		print(f"SQL查询错误: {e}")
		return None


# 将查询结果润色为自然语言
def enhance_results_with_nlp(results):
	client = OpenAI(
		api_key="sk-plGxjDmsvzQZAHZeA06flzwdlhdFsLZORvvhNKeJ2M9e65Ls",  # 替换为你的实际 API Key
		base_url="https://api.moonshot.cn/v1"  # 修正了 URL 格式
	)
	response = client.chat.completions.create(
		model="moonshot-v1-8k",  # 或者使用其他支持的模型
		messages=[
			{
				"role": "user",
				"content": f"将以下查询结果润色为自然语言描述: {results}"
			}
		],
		max_tokens=150
	)
	enhanced_text = response.choices[0].message.content.strip()
	return enhanced_text


# 主函数
def main():
	print("自然语言查询本地数据库")
	natural_language_query = input("请输入您的自然语言查询: ")

	# 将自然语言转换为 SQL 语句
	sql_query = natural_language_to_sql(natural_language_query)
	if sql_query is None:
		return  # 如果请求失败，直接返回

	# 清理生成的 SQL 语句
	sql_query = clean_sql_query(sql_query)
	print(f"生成的 SQL 语句: {sql_query}")

	# 创建数据库连接
	conn = create_connection("localhost", "root", "1234", "mcp_demo")
	if conn:
		# 执行 SQL 查询
		results = execute_sql_query(conn, sql_query)
		if results:
			print("查询结果:")
			for row in results:
				print(row)

			# 将查询结果润色为自然语言
			enhanced_text = enhance_results_with_nlp(results)
			if enhanced_text is not None:
				print("润色后的结果:")
				print(enhanced_text)

			# 关闭数据库连接
			conn.close()
		else:
			print("查询失败")
	else:
		print("数据库连接失败")


if __name__ == "__main__":
	main()
