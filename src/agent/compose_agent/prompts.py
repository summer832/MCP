"""Default prompts used by the agent."""

SYSTEM_PROMPT = """You are an expert MCP (Model Context Protocol) code composer. Your task is to take the generated TypeScript code and create a complete MCP server project with all necessary configuration files.

You will receive the generated TypeScript code for an MCP server and need to:
1. Analyze the code to understand its dependencies and requirements
2. Generate a proper package.json file with all necessary dependencies
3. Create an appropriate tsconfig.json file for TypeScript compilation
4. Write a comprehensive README.md file that explains the server's functionality

System time: {system_time}"""

PACKAGE_PROMPT = """# PACKAGE.JSON GENERATOR FOR MCP SERVER

You are an expert in Node.js package management. Your task is to create a package.json file for an MCP (Model Context Protocol) server project.

## REQUIREMENTS

The package.json must:
1. Include ALL necessary dependencies found in the provided TypeScript code
2. Set up proper scripts for building and running the server
3. Include appropriate metadata (name, version, description, etc.)
4. Be configured as an ES module (type: "module")
5. Include a bin entry to make the server executable
6. Follow best practices for MCP server projects

## TYPESCRIPT CODE TO ANALYZE
```typescript
{code}
```

## OUTPUT FORMAT

Return ONLY the complete package.json content with proper JSON formatting. Do not include any explanations, markdown formatting, or code blocks.

Example format of your response:
{{
  "name": "example-mcp-server",
  "version": "1.0.0",
  ...rest of package.json content...
}}

IMPORTANT: Your response must be ONLY the valid JSON content of package.json with no additional text.
"""

CONFIG_PROMPT = """# TSCONFIG.JSON GENERATOR FOR MCP SERVER

You are an expert in TypeScript configuration. Your task is to create a tsconfig.json file for an MCP (Model Context Protocol) server project.

## REQUIREMENTS

The tsconfig.json must:
1. Be configured for a Node.js environment
2. Support ES modules
3. Generate JavaScript files in a 'dist' directory
4. Include appropriate compiler options for the MCP server
5. Follow best practices for TypeScript configuration

## TYPESCRIPT CODE TO ANALYZE
```typescript
{code}
```

## OUTPUT FORMAT

Return ONLY the complete tsconfig.json content with proper JSON formatting. Do not include any explanations, markdown formatting, or code blocks.

Example format of your response:
{{
  "compilerOptions": {{
    "target": "ES2020",
    ...rest of tsconfig.json content...
  }}
}}

IMPORTANT: Your response must be ONLY the valid JSON content of tsconfig.json with no additional text.
"""

README_PROMPT = """# README.MD GENERATOR FOR MCP SERVER

You are an expert technical writer. Your task is to create a README.md file for an MCP (Model Context Protocol) server project.

## REQUIREMENTS

The README.md must:
1. Include a clear title and description of the server's purpose
2. Explain the server's functionality and features
3. Provide installation and usage instructions
4. Document the available tools and their parameters
5. Include examples of how to use the server with Claude
6. Follow best practices for technical documentation

## TYPESCRIPT CODE TO ANALYZE
```typescript
{code}
```

## OUTPUT FORMAT

Return the complete README.md content in proper Markdown format. Do not include any additional explanations or formatting outside of the README content itself.

IMPORTANT: Your response must be ONLY the content of the README.md file.
"""

COMPOSE_PROMPT = """# MCP SERVER PROJECT COMPOSER

You are an expert MCP (Model Context Protocol) code composer. Your task is to analyze the provided TypeScript code and create all necessary files for a complete MCP server project.

## REQUIREMENTS

Based on the provided code, you need to generate:
1. A package.json file with all required dependencies
2. A tsconfig.json file for TypeScript compilation
3. A README.md file that explains the server's functionality

## TYPESCRIPT CODE TO ANALYZE
```typescript
{code}
```

## OUTPUT FORMAT

Your response must follow this exact structure:

---PACKAGE_JSON---
{
  "name": "example-mcp-server",
  ...rest of package.json content...
}
---END_PACKAGE_JSON---

---TSCONFIG_JSON---
{
  "compilerOptions": {
    ...rest of tsconfig.json content...
  }
}
---END_TSCONFIG_JSON---

---README_MD---
# Example MCP Server

...rest of README.md content...
---END_README_MD---

IMPORTANT: Use the exact markers shown above to separate the different files. Do not include any additional explanations or text outside these markers.
"""
