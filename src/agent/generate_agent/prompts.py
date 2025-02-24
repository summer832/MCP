"""Default prompts used by the agent."""

SYSTEM_PROMPT = """You are a helpful AI assistant.

System time: {system_time}"""

DATABASE_EXAMPLE = """import { createConnection } from 'typeorm';
import { Student } from './entity/Student'; // 假设你有一个名为Student的实体

async function insertStudent() {
  const connection = await createConnection(); // 创建数据库连接

  const student = new Student(); // 创建一个新的学生实体
  student.name = 'jack'; // 设置学生的名字
  student.age = 18; // 设置学生的年龄

  await connection.manager.save(student); // 保存学生到数据库

  console.log('Student inserted successfully!');
  await connection.close(); // 关闭数据库连接
}

insertStudent().catch(error => console.error(error));"""

COMPOSE_PROMPT = """
MCP service is a fixed-format communication protocol:https://spec.modelcontextprotocol.io/specification/2024-11-05/basic/
The basic MCP service code format is as follows:
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ToolSchema,
} from "@modelcontextprotocol/sdk/types.js";

// Server setup
const server = new Server(
  {
    name: "xxx-server",
    version: "0.1.0",
  },
  {
    capabilities: {
      tools: {},
    },
  },
);

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      // 工具列表
    ]
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {  
// 工具调用处理逻辑
});

async function runServer() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

runServer().catch((error) => {
  console.error("Fatal error running server:", error);
  process.exit(1);
});
Please check the code content and analyze:

Overall validation result (isValid)
Detailed check items (checks)
Dependency check
Server configuration check
Request handler check
Response format check
Transport layer check
Preliminarily determine whether it complies with MCP specifications. 
Return JSON structure, example as follows:
{
  "isValid": true|false,
  "checkResults": {
    "baseProtocol": {
      "passed": true|false,
      "issues": []
    },
    "serverSetup": {
      "passed": true|false, 
      "issues": []
    },
    "handlers": {
      "passed": true|false,
      "issues": []
    },
    "tools": {
      "passed": true|false,
      "issues": []
    }
  },
  "summary": {
    "errors": [],
    "warnings": []
  }
}
If the code does not comply with the specification, such as missing some necessary components, 
the corresponding passed field in JSON will be set to false, 
and specific problem descriptions will be added to the warnings or errors array.
"""

REVISE_PROMPT = """
Based on the previous analysis results, please:
1. Review the validation results and identify any issues
2. Propose specific code modifications to address:
3. Failed checks (where passed = false)
4. Any warnings
5. Any errors
Generate the improved code version
Explain the key changes made
Here is a correct example mcp server code(please just concentrate on format):
{example_code}
Your response should follow this JSON structure:
<RESPONSE_FORMAT>
{
  "analysis": {
    "issues": [
      "List identified issues from previous results"
    ],
    "requiredChanges": [
      "List specific changes needed"
    ]
  },
  "improvedCode": "Complete corrected code",
  "changeSummary": "Brief explanation of modifications"
}
</RESPONSE_FORMAT>
"""
