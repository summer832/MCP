"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __await = (this && this.__await) || function (v) { return this instanceof __await ? (this.v = v, this) : new __await(v); }
var __asyncGenerator = (this && this.__asyncGenerator) || function (thisArg, _arguments, generator) {
    if (!Symbol.asyncIterator) throw new TypeError("Symbol.asyncIterator is not defined.");
    var g = generator.apply(thisArg, _arguments || []), i, q = [];
    return i = Object.create((typeof AsyncIterator === "function" ? AsyncIterator : Object).prototype), verb("next"), verb("throw"), verb("return", awaitReturn), i[Symbol.asyncIterator] = function () { return this; }, i;
    function awaitReturn(f) { return function (v) { return Promise.resolve(v).then(f, reject); }; }
    function verb(n, f) { if (g[n]) { i[n] = function (v) { return new Promise(function (a, b) { q.push([n, v, a, b]) > 1 || resume(n, v); }); }; if (f) i[n] = f(i[n]); } }
    function resume(n, v) { try { step(g[n](v)); } catch (e) { settle(q[0][3], e); } }
    function step(r) { r.value instanceof __await ? Promise.resolve(r.value.v).then(fulfill, reject) : settle(q[0][2], r); }
    function fulfill(value) { resume("next", value); }
    function reject(value) { resume("throw", value); }
    function settle(f, v) { if (f(v), q.shift(), q.length) resume(q[0][0], q[0][1]); }
};
Object.defineProperty(exports, "__esModule", { value: true });
const mcp_1 = require("@microsoft/mcp");
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
];
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
}
catch (error) {
    console.error(`Error: Invalid agent base URL: ${agentBaseUrl}`);
    process.exit(1);
}
function handleAgentInvoke(message, model, thread_id) {
    return __awaiter(this, void 0, void 0, function* () {
        const url = new URL(`${agentBaseUrl}/invoke`);
        const response = yield fetch(url.toString(), {
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
        const data = yield response.json();
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
    });
}
function handleAgentStream(message_1, model_1, thread_id_1) {
    return __asyncGenerator(this, arguments, function* handleAgentStream_1(message, model, thread_id, stream_tokens = true) {
        var _a;
        const url = new URL(`${agentBaseUrl}/stream`);
        const response = yield __await(fetch(url.toString(), {
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
        }));
        // 处理SSE流式响应
        const reader = (_a = response.body) === null || _a === void 0 ? void 0 : _a.getReader();
        const decoder = new TextDecoder();
        while (reader) {
            const { value, done } = yield __await(reader.read());
            if (done)
                break;
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.slice(5));
                    // 处理流式数据
                    yield yield __await({
                        content: [{
                                type: "text",
                                text: JSON.stringify(data)
                            }],
                        isError: false
                    });
                }
            }
        }
    });
}
const server = new mcp_1.Server({
    name: "mcp-server/agent",
    version: "0.1.0",
}, {
    capabilities: {
        tools: {},
    },
});
server.setRequestHandler(mcp_1.ListToolsRequestSchema, () => __awaiter(void 0, void 0, void 0, function* () {
    return ({
        tools: AGENT_TOOLS,
    });
}));
server.setRequestHandler(mcp_1.CallToolRequestSchema, (request) => __awaiter(void 0, void 0, void 0, function* () {
    try {
        switch (request.params.name) {
            case "agent_invoke": {
                const { message, model, thread_id } = request.params.arguments;
                return yield handleAgentInvoke(message, model, thread_id);
            }
            case "agent_stream": {
                const { message, model, thread_id, stream_tokens } = request.params.arguments;
                return yield handleAgentStream(message, model, thread_id, stream_tokens);
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
    }
    catch (error) {
        return {
            content: [{
                    type: "text",
                    text: `错误: ${error instanceof Error ? error.message : String(error)}`
                }],
            isError: true
        };
    }
}));
