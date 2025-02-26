# sql_tool.py
from openai import OpenAI
from typing import Dict, Any

class SQLGenerator:
    def __init__(self, openai_api_key: str, db_schema: Dict[str, Any]):
        """
        初始化 SQL 生成器
        """
        self.openai_api_key = openai_api_key
        self.db_schema = db_schema
        self.client = OpenAI(api_key=openai_api_key, base_url="https://api.moonshot.cn/v1")

    def generate_sql(self, query: str) -> str:
        """
        根据用户查询生成SQL语句
        """
        try:
            response = self.client.chat.completions.create(
                model="moonshot-v1-8k",
                messages=[
                    {
                        "role": "user",
                        "content": f"根据以下数据库模式和用户查询生成SQL语句：\n\n数据库模式：{self.db_schema}\n\n用户查询：{query}\n\nSQL语句："
                    }
                ],
                max_tokens=500,
                timeout=60  # 增加超时时间
            )
            sql = response.choices[0].message.content.strip()  # 获取生成的 SQL 语句
            return sql
        except Exception as e:
            print(f"生成 SQL 语句错误: {e}")
            return ""