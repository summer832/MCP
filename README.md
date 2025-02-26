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
1. 基于langgraph studio的MCP服务代码生成多智能体, 采用supervisor-tool结构
2. 通过analyse-generate-compose来进行代码生成 每个环节由单个智能体实现
3. 相应对话记忆保存在supervisor中, 暂不支持Retrieval Tool

### supervisor
1. 控制代码生成流程
2. 根据用户输入判断是否进入下一步

### analysis agent
利用ReAct机制, 将需求分析任务拆分,分为需求分析,分析增强, 分析检查3个部分

### generate agent
包括代码生成与代码审查功能. 根据需求生成MCP服务代码, 然后通过审查-修正Node循环调整代码
目前代码生成仅包括数据库代码

## compose agent
生成对应的package.json, tsconfig.json, README.MD
