# agent.py
from langchain.agents import Tool, create_openai_functions_agent, AgentExecutor
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.agents import AgentOutputParser
import re
from pydantic import BaseModel
from typing import Any, Dict
from sql_tool import SQLGenerator
from db import execute_query
from schema import get_db_schema
from tabulate import tabulate

class SQLOutputParser(AgentOutputParser):
    def parse(self, llm_output):
        # 提取 SQL 语句
        pattern = re.compile(r"```sql\s*(.*?)\s*```", re.DOTALL)
        match = pattern.search(llm_output)
        if match:
            return {"sql": match.group(1).strip()}
        return {"sql": llm_output.strip()}

class ExecuteSQLArgs(BaseModel):
    query: str

def execute_sql_tool(args: ExecuteSQLArgs, sql_generator: SQLGenerator, db_connection) -> str:
    query = args.query
    sql = sql_generator.generate_sql(query)
    print(f"生成的 SQL 语句:\n{sql}")  # 调试输出
    # 执行 SQL 查询
    columns, result = execute_query(db_connection, sql)
    if columns and result:
        # 将结果格式化为表格字符串
        table = tabulate(result, headers=columns, tablefmt="grid")
        return f"查询结果:\n{table}"
    return "查询失败或无结果。"

def create_agent(openai_api_key, db_connection, user_input):
    # 获取数据库模式
    db_schema = get_db_schema(db_connection)

    # 初始化 SQL 生成工具
    sql_generator = SQLGenerator(openai_api_key, db_schema)

    # 定义工具
    def execute_sql_function(query: str) -> str:
        sql = sql_generator.generate_sql(query)
        columns, result = execute_query(db_connection, sql)
        if columns and result:
            # 将结果格式化为表格字符串
            table = tabulate(result, headers=columns, tablefmt="grid")
            return f"查询结果:\n{table}"
        return "查询失败或无结果。"

    execute_sql_tool_instance = Tool(
        name="execute_sql",
        func=execute_sql_function,
        description="执行给定的SQL查询，并返回结果。用户提供的查询将被转化为SQL语句。",
        args_schema=ExecuteSQLArgs
    )

    tools = [execute_sql_tool_instance]

    # 定义 PromptTemplate
    prompt_template = PromptTemplate(
        input_variables=["input"],
        template="""
    你是一个智能的数据分析助手。你将根据用户的自然语言查询生成相应的SQL语句，并执行查询以获取所需的信息。

    使用以下工具来完成任务：
    {tools}

    用户查询: {input}

    请根据用户的需求，选择合适的工具并返回结果。如果需要返回数据库查询的结果，将以表格的形式展现。
    {agent_scratchpad}
    """
    )

    # 初始化 LangChain 的 LLM 对象
    llm = ChatOpenAI(
        api_key=openai_api_key,
        base_url="https://api.moonshot.cn/v1",
        model="moonshot-v1-8k"
    )

    # 创建代理
    agent = create_openai_functions_agent(
        llm=llm,
        tools=tools,
        prompt=prompt_template,
        # verbose=True
    )

    # 创建代理执行器
    agent_executor = AgentExecutor(agent=agent, tools=tools)
    response = agent_executor.invoke({"input": user_input, "agent_scratchpad": [], "tools": tools})

    # 提取生成的 SQL 语句并执行
    sql_output = SQLOutputParser().parse(response["output"])
    sql = sql_output.get("sql")
    if sql:
        columns, result = execute_query(db_connection, sql)
        if columns and result:
            table = tabulate(result, headers=columns, tablefmt="grid")
            return f"查询结果:\n{table}"
        return "查询失败或无结果。"
    return "未生成有效的 SQL 语句。"