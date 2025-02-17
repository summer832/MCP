# MCP Server Agent

这是一个基于 MCP (Microsoft Chat Protocol) 的 Agent 服务器实现。

## 功能特性

- 支持同步对话调用 (agent_invoke)
- 支持流式对话调用 (agent_stream)
- 支持自定义模型选择
- 支持会话上下文管理

## 使用方法

1. 启动服务器:

```bash
npm start <agent-base-url>
```

其中 `agent-base-url` 是您的 Agent 服务的基础 URL。

2. 调用示例:

```typescript
// 同步调用
const response = await handleAgentInvoke("你好", "gpt-4", "thread-123");

// 流式调用
for await (const chunk of handleAgentStream("你好", "gpt-4", "thread-123")) {
  console.log(chunk);
}
```

## API 说明

### agent_invoke

同步调用 Agent 进行对话。

参数:
- message: string - 用户输入消息
- model?: string - 可选的模型名称
- thread_id?: string - 可选的会话ID

### agent_stream

流式调用 Agent 对话。

参数:
- message: string - 用户输入消息
- model?: string - 可选的模型名称
- thread_id?: string - 可选的会话ID
- stream_tokens?: boolean - 是否流式返回token

## 安装

### Docker
将以下配置添加到 `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcp-agent": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "mcp/agent",
        "https://your-agent-base-url"
      ]
    }
  }
}
```

### NPX

```json
{
  "mcpServers": {
    "mcp-agent": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-agent",
        "https://127.0.0.1:8080"
      ]
    }
  }
}
```

其中 `https://127.0.0.1:8080` 需要替换为您的 Agent 服务的基础 URL。
