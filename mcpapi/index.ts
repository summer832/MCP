import { Server, ListToolsRequestSchema, CallToolRequestSchema } from "@microsoft/mcp";

interface AgentResponse {
  status: string;
  error_message?: string;
  content?: string | { type: "human" | "ai" | "tool" | "custom"; content: string; };
  run_id?: string;
}

interface InvokeResponse extends AgentResponse {
  type: "human" | "ai" | "tool" | "custom";
  tool_calls?: Array<{
    name: string;
    args: any;
    id?: string;
  }>;
}

interface StreamResponse extends AgentResponse {
  type: "message" | "token";
  content: string | {
    type: "human" | "ai" | "tool" | "custom";
    content: string;
  };
}

const AGENT_TOOLS = [
    {
        name: "agent_invoke",
        description: "调用Agent进行对话",
        inputSchema: {
        type: "object",
        properties: {
            message: {
            type: "string",
            description: "用户输入消息"
            },
            model: {
            type: "string",
            description: "可选的模型名称"
            },
            thread_id: {
            type: "string",
            description: "可选的会话ID"
            }
        },
        required: ["message"]
        }
    },
    {
        name: "agent_stream", 
        description: "流式调用Agent对话",
        inputSchema: {
        type: "object",
        properties: {
            message: {
            type: "string",
            description: "用户输入消息"
            },
            model: {
            type: "string",
            description: "可选的模型名称"
            },
            thread_id: {
            type: "string",
            description: "可选的会话ID" 
            },
            stream_tokens: {
            type: "boolean",
            description: "是否流式返回token"
            }
        },
        required: ["message"]
        }
    }
] as const;

// 命令行参数解析
const args = process.argv.slice(2);
if (args.length === 0) {
    console.error("Usage: mcp-server-agent <agent-base-url>");
    process.exit(1);
}

// 获取并验证 agent base url
const agentBaseUrl = args[0];
try {
    new URL(agentBaseUrl); // 验证 URL 格式是否有效
} catch (error) {
    console.error(`Error: Invalid agent base URL: ${agentBaseUrl}`);
    process.exit(1);
}

async function handleAgentInvoke(message: string, model?: string, thread_id?: string) {
    const url = new URL(`${agentBaseUrl}/invoke`);
    const response = await fetch(url.toString(), {
        method: 'POST',
        headers: {
        'Content-Type': 'application/json'
        },
        body: JSON.stringify({
        message,
        model,
        thread_id
        })
    });

    const data = await response.json() as InvokeResponse;

    if (data.status !== "OK") {
        return {
        content: [{
            type: "text", 
            text: `Agent调用失败: ${data.error_message || data.status}`
        }],
        isError: true
        };
    }

    return {
        content: [{
        type: "text",
        text: JSON.stringify(data)
        }],
        isError: false
    };
}
  
async function* handleAgentStream(
    message: string,
    model?: string,
    thread_id?: string,
    stream_tokens: boolean = true
) {
    const url = new URL(`${agentBaseUrl}/stream`);
    const response = await fetch(url.toString(), {
        method: 'POST',
        headers: {
        'Content-Type': 'application/json'
        },
        body: JSON.stringify({
        message,
        model,
        thread_id,
        stream_tokens
        })
    });

    // 处理SSE流式响应
    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    while(reader) {
        const {value, done} = await reader.read();
        if(done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        
        for(const line of lines) {
        if(line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(5)) as StreamResponse;
            // 处理流式数据
            yield {
            content: [{
                type: "text",
                text: JSON.stringify(data)
            }],
            isError: false
            };
        }
        }
    }
}

const server = new Server(
    {
        name: "mcp-server/agent",
        version: "0.1.0",
    },
    {
        capabilities: {
        tools: {},
        },
    }
);
  
server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: AGENT_TOOLS,
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
    try {
        switch (request.params.name) {
        case "agent_invoke": {
            const { message, model, thread_id } = request.params.arguments as {
            message: string;
            model?: string;
            thread_id?: string;
            };
            return await handleAgentInvoke(message, model, thread_id);
        }

        case "agent_stream": {
            const { message, model, thread_id, stream_tokens } = request.params.arguments as {
            message: string;
            model?: string;
            thread_id?: string;
            stream_tokens?: boolean;
            };
            return await handleAgentStream(message, model, thread_id, stream_tokens);
        }

        default:
            return {
            content: [{
                type: "text",
                text: `未知工具: ${request.params.name}`
            }],
            isError: true
            };
        }
    } catch (error) {
        return {
        content: [{
            type: "text",
            text: `错误: ${error instanceof Error ? error.message : String(error)}`
        }],
        isError: true
        };
    }
});