# mcp_generate_agent.py 的代码可视化

import os
import sys

# 添加 src 目录到 Python 路径
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(src_path)

# 现在可以从 src 开始导入
from agents.mcp_generate_agent.mcp_generate_agent import mcp_generate_agent
from agents.mcp_generate_agent.database import database_chain
from agents.mcp_generate_agent.browser import browser_chain


def save_workflow_diagram(filename='mcp_agent_workflow'):
    # 获取当前文件所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 构建完整的文件路径
    file_path = os.path.join(current_dir, filename)

    # 保存为 Mermaid 格式
    with open(f"{file_path}_main.md", "w", encoding="utf-8") as f:
        f.write(mcp_generate_agent.get_graph().draw_mermaid())
    with open(f"{file_path}_database.md", "w", encoding="utf-8") as f:
        f.write(database_chain.get_graph().draw_mermaid())
    with open(f"{file_path}_browser.md", "w", encoding="utf-8") as f:
        f.write(browser_chain.get_graph().draw_mermaid())

    # 保存为 PNG 格式
    mcp_generate_agent.get_graph().draw_mermaid_png(output_file_path=f"{file_path}_main.png")
    database_chain.get_graph().draw_mermaid_png(output_file_path=f"{file_path}_database.png")
    browser_chain.get_graph().draw_mermaid_png(output_file_path=f"{file_path}_browser.png")

    print(f"文件已保存在: {current_dir}")
    print(f"生成的文件:")
    print(f"- {filename}_main.md (主流程图 Mermaid)")
    print(f"- {filename}_database.md (数据库实现流程图 Mermaid)")
    print(f"- {filename}_browser.md (浏览器实现流程图 Mermaid)")
    print(f"- {filename}_main.png (主流程图 PNG)")
    print(f"- {filename}_database.png (数据库实现流程图 PNG)")
    print(f"- {filename}_browser.png (浏览器实现流程图 PNG)")

if __name__ == "__main__":
    save_workflow_diagram()
