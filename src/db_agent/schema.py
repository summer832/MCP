import mysql.connector
from mysql.connector import Error

def get_db_schema(connection):
    """
    获取数据库的模式，包括所有表和列
    """
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE()")
        rows = cursor.fetchall()
        schema = {}
        for table, column, data_type in rows:
            if table not in schema:
                schema[table] = []
            schema[table].append(f"{column} {data_type}")
        schema_str = ""
        for table, columns in schema.items():
            schema_str += f"表 `{table}` ("
            schema_str += ", ".join(columns)
            schema_str += ")\n"
        return schema_str
    except Error as e:
        print(f"获取模式错误: {e}")
        return ""
    finally:
        cursor.close()