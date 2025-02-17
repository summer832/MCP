#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ToolSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";
import { zodToJsonSchema } from "zod-to-json-schema";

// 解析命令行参数（若需要允许目录或其他配置，可在此处处理）
const args = process.argv.slice(2);

// MCP Server 实例创建
const server = new Server(
  {
    name: "generic-mcp-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      // 此处可填充工具相关的配置信息、或其他扩展功能
      tools: {},
    },
  },
);

/**
 * 在此可编写验证路径、扩展家目录、文件或其他通用逻辑。
 * 若不需要，可删除。 
 * 如需安全限制可在此增添安全校验、路径规范化等。
 */
function validateSomething(data: unknown) {
  // 示例：空函数，用于演示可能的安全校验或其他逻辑
  return data;
}

/**
 * ToolHandlers （工具处理器）通常处理具体的读写、编辑等操作。
 * 在此留空，以示范一个最小化的 MCP Server 框架。
 */

// 列出可用的 Tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      // 此处可以返回多个工具描述，但目前留空
      // {
      //   name: "example_tool",
      //   description: "An example tool that does nothing yet",
      //   inputSchema: { ... },
      // },
    ],
  };
});

// 处理具体的工具调用
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  try {
    const { name, arguments: toolArgs } = request.params;

    switch (name) {
      // 在这里根据 name 区分不同工具
      // case "example_tool":
      //   // 处理逻辑
      //   return { content: [{ type: "text", text: "Example tool result" }] };

      default:
        throw new Error(`Unknown tool name: ${name}`);
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    return {
      content: [{ type: "text", text: `Error: ${errorMessage}` }],
      isError: true,
    };
  }
});

/**
 * 启动服务器，并通过 stdio 侦听 MCP 请求。
 * 若需要其他传输方式，也可自行扩展。
 */
async function runServer() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Generic MCP Server running on stdio");
  // 若有额外配置信息可在此输出日志
}

// 启动
runServer().catch((error) => {
  console.error("Fatal error running server:", error);
  process.exit(1);
});