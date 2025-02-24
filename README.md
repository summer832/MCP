# 环境配置
使用langgraph studio   
https://langchain-ai.github.io/langgraph/tutorials/langgraph-platform/local-server/  
```commandline
pip install --upgrade "langgraph-cli[inmem]"  
langgraph new path/to/your/app --template react-agent-python 
pip install -e .
```
```
# 启动
```commandline
python run.py
```

# 介绍
1. 基于langgraph的MCP服务代码生成多智能体, 采用supervisor-tool结构
2. 通过analyse-generate-compose来进行代码生成,暂时没有代码测试环节
3. 每个环节由单个智能体实现,相应对话记忆保存在supervisor中,暂不支持tool多轮对话