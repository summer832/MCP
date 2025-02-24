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

### supervisor
1. 控制代码生成流程
2. 根据用户输入判断是否进入下一步

### analysis agent
1. 利用ReAct机制, 将需求分析任务拆分,分为需求分析,分析增强, 分析检查3个部分
2. 只实现了线性逻辑, 没有反馈环节

### generate agent
1. browser-code:  
操作浏览器的MCP服务很多,效果比生成的好, 如果提出了关于浏览器的MCP服务需求,直接返回你一个固定的MCP服务
2. database-code:

## compose agent
1. 代码检查-代码修正循环调用
2. 完成package.json, tsconfig.json, README.MD
