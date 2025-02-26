# main.py
import os
import logging
from db import connect_to_database
from agent import create_agent
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from sql_tool import SQLGenerator
from schema import get_db_schema

# 配置日志记录
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 定义 API 请求体
class QueryRequest(BaseModel):
    query: str

# 定义 API 响应体
class QueryResponse(BaseModel):
    response: str

# 初始化数据库连接
db_connection = connect_to_database(
    host='127.0.0.1',
    database='mcp_demo',
    user='root',
    password='1234'
)

if not db_connection:
    raise Exception("无法连接到数据库")

# 设置 OpenAI API 密钥
api_key = 'sk-plGxjDmsvzQZAHZeA06flzwdlhdFsLZORvvhNKeJ2M9e65Ls'

# 初始化 FastAPI 应用
app = FastAPI()

@app.post("/query", response_model=QueryResponse)
def query_database(request: QueryRequest):
    user_query = request.query
    logger.info(f"user_query: {user_query}")
    try:
        # 调用 create_agent 函数处理查询
        result = create_agent(api_key, db_connection, user_query)
        logger.info(f"result: {result}")
        return QueryResponse(response=result)
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# 测试函数
def test_sql_generator():
    test_query = "查询学生表中的所有学生的年龄。"
    db_schema = get_db_schema(db_connection)
    sql_generator = SQLGenerator(api_key, db_schema)  # 初始化 SQLGenerator
    try:
        sql = sql_generator.generate_sql(test_query)
        print(f"Generated SQL: {sql}")
    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    # 运行测试函数
    # test_sql_generator()

    # # 启动 FastAPI 应用
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)