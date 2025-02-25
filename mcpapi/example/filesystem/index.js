#!/usr/bin/env node
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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const index_js_1 = require("@modelcontextprotocol/sdk/server/index.js");
const stdio_js_1 = require("@modelcontextprotocol/sdk/server/stdio.js");
const types_js_1 = require("@modelcontextprotocol/sdk/types.js");
const promises_1 = __importDefault(require("fs/promises"));
const path_1 = __importDefault(require("path"));
const os_1 = __importDefault(require("os"));
const zod_1 = require("zod");
const zod_to_json_schema_1 = require("zod-to-json-schema");
const diff_1 = require("diff");
const minimatch_1 = require("minimatch");
// Command line argument parsing
const args = process.argv.slice(2);
if (args.length === 0) {
    console.error("Usage: mcp-server-filesystem <allowed-directory> [additional-directories...]");
    process.exit(1);
}
// Normalize all paths consistently
function normalizePath(p) {
    return path_1.default.normalize(p);
}
function expandHome(filepath) {
    if (filepath.startsWith('~/') || filepath === '~') {
        return path_1.default.join(os_1.default.homedir(), filepath.slice(1));
    }
    return filepath;
}
// Store allowed directories in normalized form
const allowedDirectories = args.map(dir => normalizePath(path_1.default.resolve(expandHome(dir))));
// Validate that all directories exist and are accessible
await Promise.all(args.map((dir) => __awaiter(void 0, void 0, void 0, function* () {
    try {
        const stats = yield promises_1.default.stat(dir);
        if (!stats.isDirectory()) {
            console.error(`Error: ${dir} is not a directory`);
            process.exit(1);
        }
    }
    catch (error) {
        console.error(`Error accessing directory ${dir}:`, error);
        process.exit(1);
    }
})));
// Security utilities
function validatePath(requestedPath) {
    return __awaiter(this, void 0, void 0, function* () {
        const expandedPath = expandHome(requestedPath);
        const absolute = path_1.default.isAbsolute(expandedPath)
            ? path_1.default.resolve(expandedPath)
            : path_1.default.resolve(process.cwd(), expandedPath);
        const normalizedRequested = normalizePath(absolute);
        // Check if path is within allowed directories
        const isAllowed = allowedDirectories.some(dir => normalizedRequested.startsWith(dir));
        if (!isAllowed) {
            throw new Error(`Access denied - path outside allowed directories: ${absolute} not in ${allowedDirectories.join(', ')}`);
        }
        // Handle symlinks by checking their real path
        try {
            const realPath = yield promises_1.default.realpath(absolute);
            const normalizedReal = normalizePath(realPath);
            const isRealPathAllowed = allowedDirectories.some(dir => normalizedReal.startsWith(dir));
            if (!isRealPathAllowed) {
                throw new Error("Access denied - symlink target outside allowed directories");
            }
            return realPath;
        }
        catch (error) {
            // For new files that don't exist yet, verify parent directory
            const parentDir = path_1.default.dirname(absolute);
            try {
                const realParentPath = yield promises_1.default.realpath(parentDir);
                const normalizedParent = normalizePath(realParentPath);
                const isParentAllowed = allowedDirectories.some(dir => normalizedParent.startsWith(dir));
                if (!isParentAllowed) {
                    throw new Error("Access denied - parent directory outside allowed directories");
                }
                return absolute;
            }
            catch (_a) {
                throw new Error(`Parent directory does not exist: ${parentDir}`);
            }
        }
    });
}
// Schema definitions
const ReadFileArgsSchema = zod_1.z.object({
    path: zod_1.z.string(),
});
const ReadMultipleFilesArgsSchema = zod_1.z.object({
    paths: zod_1.z.array(zod_1.z.string()),
});
const WriteFileArgsSchema = zod_1.z.object({
    path: zod_1.z.string(),
    content: zod_1.z.string(),
});
const EditOperation = zod_1.z.object({
    oldText: zod_1.z.string().describe('Text to search for - must match exactly'),
    newText: zod_1.z.string().describe('Text to replace with')
});
const EditFileArgsSchema = zod_1.z.object({
    path: zod_1.z.string(),
    edits: zod_1.z.array(EditOperation),
    dryRun: zod_1.z.boolean().default(false).describe('Preview changes using git-style diff format')
});
const CreateDirectoryArgsSchema = zod_1.z.object({
    path: zod_1.z.string(),
});
const ListDirectoryArgsSchema = zod_1.z.object({
    path: zod_1.z.string(),
});
const DirectoryTreeArgsSchema = zod_1.z.object({
    path: zod_1.z.string(),
});
const MoveFileArgsSchema = zod_1.z.object({
    source: zod_1.z.string(),
    destination: zod_1.z.string(),
});
const SearchFilesArgsSchema = zod_1.z.object({
    path: zod_1.z.string(),
    pattern: zod_1.z.string(),
    excludePatterns: zod_1.z.array(zod_1.z.string()).optional().default([])
});
const GetFileInfoArgsSchema = zod_1.z.object({
    path: zod_1.z.string(),
});
const ToolInputSchema = types_js_1.ToolSchema.shape.inputSchema;
// Server setup
const server = new index_js_1.Server({
    name: "secure-filesystem-server",
    version: "0.2.0",
}, {
    capabilities: {
        tools: {},
    },
});
// Tool implementations
function getFileStats(filePath) {
    return __awaiter(this, void 0, void 0, function* () {
        const stats = yield promises_1.default.stat(filePath);
        return {
            size: stats.size,
            created: stats.birthtime,
            modified: stats.mtime,
            accessed: stats.atime,
            isDirectory: stats.isDirectory(),
            isFile: stats.isFile(),
            permissions: stats.mode.toString(8).slice(-3),
        };
    });
}
function searchFiles(rootPath_1, pattern_1) {
    return __awaiter(this, arguments, void 0, function* (rootPath, pattern, excludePatterns = []) {
        const results = [];
        function search(currentPath) {
            return __awaiter(this, void 0, void 0, function* () {
                const entries = yield promises_1.default.readdir(currentPath, { withFileTypes: true });
                for (const entry of entries) {
                    const fullPath = path_1.default.join(currentPath, entry.name);
                    try {
                        // Validate each path before processing
                        yield validatePath(fullPath);
                        // Check if path matches any exclude pattern
                        const relativePath = path_1.default.relative(rootPath, fullPath);
                        const shouldExclude = excludePatterns.some(pattern => {
                            const globPattern = pattern.includes('*') ? pattern : `**/${pattern}/**`;
                            return (0, minimatch_1.minimatch)(relativePath, globPattern, { dot: true });
                        });
                        if (shouldExclude) {
                            continue;
                        }
                        if (entry.name.toLowerCase().includes(pattern.toLowerCase())) {
                            results.push(fullPath);
                        }
                        if (entry.isDirectory()) {
                            yield search(fullPath);
                        }
                    }
                    catch (error) {
                        // Skip invalid paths during search
                        continue;
                    }
                }
            });
        }
        yield search(rootPath);
        return results;
    });
}
// file editing and diffing utilities
function normalizeLineEndings(text) {
    return text.replace(/\r\n/g, '\n');
}
function createUnifiedDiff(originalContent, newContent, filepath = 'file') {
    // Ensure consistent line endings for diff
    const normalizedOriginal = normalizeLineEndings(originalContent);
    const normalizedNew = normalizeLineEndings(newContent);
    return (0, diff_1.createTwoFilesPatch)(filepath, filepath, normalizedOriginal, normalizedNew, 'original', 'modified');
}
function applyFileEdits(filePath_1, edits_1) {
    return __awaiter(this, arguments, void 0, function* (filePath, edits, dryRun = false) {
        var _a;
        // Read file content and normalize line endings
        const content = normalizeLineEndings(yield promises_1.default.readFile(filePath, 'utf-8'));
        // Apply edits sequentially
        let modifiedContent = content;
        for (const edit of edits) {
            const normalizedOld = normalizeLineEndings(edit.oldText);
            const normalizedNew = normalizeLineEndings(edit.newText);
            // If exact match exists, use it
            if (modifiedContent.includes(normalizedOld)) {
                modifiedContent = modifiedContent.replace(normalizedOld, normalizedNew);
                continue;
            }
            // Otherwise, try line-by-line matching with flexibility for whitespace
            const oldLines = normalizedOld.split('\n');
            const contentLines = modifiedContent.split('\n');
            let matchFound = false;
            for (let i = 0; i <= contentLines.length - oldLines.length; i++) {
                const potentialMatch = contentLines.slice(i, i + oldLines.length);
                // Compare lines with normalized whitespace
                const isMatch = oldLines.every((oldLine, j) => {
                    const contentLine = potentialMatch[j];
                    return oldLine.trim() === contentLine.trim();
                });
                if (isMatch) {
                    // Preserve original indentation of first line
                    const originalIndent = ((_a = contentLines[i].match(/^\s*/)) === null || _a === void 0 ? void 0 : _a[0]) || '';
                    const newLines = normalizedNew.split('\n').map((line, j) => {
                        var _a, _b, _c;
                        if (j === 0)
                            return originalIndent + line.trimStart();
                        // For subsequent lines, try to preserve relative indentation
                        const oldIndent = ((_b = (_a = oldLines[j]) === null || _a === void 0 ? void 0 : _a.match(/^\s*/)) === null || _b === void 0 ? void 0 : _b[0]) || '';
                        const newIndent = ((_c = line.match(/^\s*/)) === null || _c === void 0 ? void 0 : _c[0]) || '';
                        if (oldIndent && newIndent) {
                            const relativeIndent = newIndent.length - oldIndent.length;
                            return originalIndent + ' '.repeat(Math.max(0, relativeIndent)) + line.trimStart();
                        }
                        return line;
                    });
                    contentLines.splice(i, oldLines.length, ...newLines);
                    modifiedContent = contentLines.join('\n');
                    matchFound = true;
                    break;
                }
            }
            if (!matchFound) {
                throw new Error(`Could not find exact match for edit:\n${edit.oldText}`);
            }
        }
        // Create unified diff
        const diff = createUnifiedDiff(content, modifiedContent, filePath);
        // Format diff with appropriate number of backticks
        let numBackticks = 3;
        while (diff.includes('`'.repeat(numBackticks))) {
            numBackticks++;
        }
        const formattedDiff = `${'`'.repeat(numBackticks)}diff\n${diff}${'`'.repeat(numBackticks)}\n\n`;
        if (!dryRun) {
            yield promises_1.default.writeFile(filePath, modifiedContent, 'utf-8');
        }
        return formattedDiff;
    });
}
// Tool handlers
server.setRequestHandler(types_js_1.ListToolsRequestSchema, () => __awaiter(void 0, void 0, void 0, function* () {
    return {
        tools: [
            {
                name: "read_file",
                description: "Read the complete contents of a file from the file system. " +
                    "Handles various text encodings and provides detailed error messages " +
                    "if the file cannot be read. Use this tool when you need to examine " +
                    "the contents of a single file. Only works within allowed directories.",
                inputSchema: (0, zod_to_json_schema_1.zodToJsonSchema)(ReadFileArgsSchema),
            },
            {
                name: "read_multiple_files",
                description: "Read the contents of multiple files simultaneously. This is more " +
                    "efficient than reading files one by one when you need to analyze " +
                    "or compare multiple files. Each file's content is returned with its " +
                    "path as a reference. Failed reads for individual files won't stop " +
                    "the entire operation. Only works within allowed directories.",
                inputSchema: (0, zod_to_json_schema_1.zodToJsonSchema)(ReadMultipleFilesArgsSchema),
            },
            {
                name: "write_file",
                description: "Create a new file or completely overwrite an existing file with new content. " +
                    "Use with caution as it will overwrite existing files without warning. " +
                    "Handles text content with proper encoding. Only works within allowed directories.",
                inputSchema: (0, zod_to_json_schema_1.zodToJsonSchema)(WriteFileArgsSchema),
            },
            {
                name: "edit_file",
                description: "Make line-based edits to a text file. Each edit replaces exact line sequences " +
                    "with new content. Returns a git-style diff showing the changes made. " +
                    "Only works within allowed directories.",
                inputSchema: (0, zod_to_json_schema_1.zodToJsonSchema)(EditFileArgsSchema),
            },
            {
                name: "create_directory",
                description: "Create a new directory or ensure a directory exists. Can create multiple " +
                    "nested directories in one operation. If the directory already exists, " +
                    "this operation will succeed silently. Perfect for setting up directory " +
                    "structures for projects or ensuring required paths exist. Only works within allowed directories.",
                inputSchema: (0, zod_to_json_schema_1.zodToJsonSchema)(CreateDirectoryArgsSchema),
            },
            {
                name: "list_directory",
                description: "Get a detailed listing of all files and directories in a specified path. " +
                    "Results clearly distinguish between files and directories with [FILE] and [DIR] " +
                    "prefixes. This tool is essential for understanding directory structure and " +
                    "finding specific files within a directory. Only works within allowed directories.",
                inputSchema: (0, zod_to_json_schema_1.zodToJsonSchema)(ListDirectoryArgsSchema),
            },
            {
                name: "directory_tree",
                description: "Get a recursive tree view of files and directories as a JSON structure. " +
                    "Each entry includes 'name', 'type' (file/directory), and 'children' for directories. " +
                    "Files have no children array, while directories always have a children array (which may be empty). " +
                    "The output is formatted with 2-space indentation for readability. Only works within allowed directories.",
                inputSchema: (0, zod_to_json_schema_1.zodToJsonSchema)(DirectoryTreeArgsSchema),
            },
            {
                name: "move_file",
                description: "Move or rename files and directories. Can move files between directories " +
                    "and rename them in a single operation. If the destination exists, the " +
                    "operation will fail. Works across different directories and can be used " +
                    "for simple renaming within the same directory. Both source and destination must be within allowed directories.",
                inputSchema: (0, zod_to_json_schema_1.zodToJsonSchema)(MoveFileArgsSchema),
            },
            {
                name: "search_files",
                description: "Recursively search for files and directories matching a pattern. " +
                    "Searches through all subdirectories from the starting path. The search " +
                    "is case-insensitive and matches partial names. Returns full paths to all " +
                    "matching items. Great for finding files when you don't know their exact location. " +
                    "Only searches within allowed directories.",
                inputSchema: (0, zod_to_json_schema_1.zodToJsonSchema)(SearchFilesArgsSchema),
            },
            {
                name: "get_file_info",
                description: "Retrieve detailed metadata about a file or directory. Returns comprehensive " +
                    "information including size, creation time, last modified time, permissions, " +
                    "and type. This tool is perfect for understanding file characteristics " +
                    "without reading the actual content. Only works within allowed directories.",
                inputSchema: (0, zod_to_json_schema_1.zodToJsonSchema)(GetFileInfoArgsSchema),
            },
            {
                name: "list_allowed_directories",
                description: "Returns the list of directories that this server is allowed to access. " +
                    "Use this to understand which directories are available before trying to access files.",
                inputSchema: {
                    type: "object",
                    properties: {},
                    required: [],
                },
            },
        ],
    };
}));
server.setRequestHandler(types_js_1.CallToolRequestSchema, (request) => __awaiter(void 0, void 0, void 0, function* () {
    try {
        const { name, arguments: args } = request.params;
        switch (name) {
            case "read_file": {
                const parsed = ReadFileArgsSchema.safeParse(args);
                if (!parsed.success) {
                    throw new Error(`Invalid arguments for read_file: ${parsed.error}`);
                }
                const validPath = yield validatePath(parsed.data.path);
                const content = yield promises_1.default.readFile(validPath, "utf-8");
                return {
                    content: [{ type: "text", text: content }],
                };
            }
            case "read_multiple_files": {
                const parsed = ReadMultipleFilesArgsSchema.safeParse(args);
                if (!parsed.success) {
                    throw new Error(`Invalid arguments for read_multiple_files: ${parsed.error}`);
                }
                const results = yield Promise.all(parsed.data.paths.map((filePath) => __awaiter(void 0, void 0, void 0, function* () {
                    try {
                        const validPath = yield validatePath(filePath);
                        const content = yield promises_1.default.readFile(validPath, "utf-8");
                        return `${filePath}:\n${content}\n`;
                    }
                    catch (error) {
                        const errorMessage = error instanceof Error ? error.message : String(error);
                        return `${filePath}: Error - ${errorMessage}`;
                    }
                })));
                return {
                    content: [{ type: "text", text: results.join("\n---\n") }],
                };
            }
            case "write_file": {
                const parsed = WriteFileArgsSchema.safeParse(args);
                if (!parsed.success) {
                    throw new Error(`Invalid arguments for write_file: ${parsed.error}`);
                }
                const validPath = yield validatePath(parsed.data.path);
                yield promises_1.default.writeFile(validPath, parsed.data.content, "utf-8");
                return {
                    content: [{ type: "text", text: `Successfully wrote to ${parsed.data.path}` }],
                };
            }
            case "edit_file": {
                const parsed = EditFileArgsSchema.safeParse(args);
                if (!parsed.success) {
                    throw new Error(`Invalid arguments for edit_file: ${parsed.error}`);
                }
                const validPath = yield validatePath(parsed.data.path);
                const result = yield applyFileEdits(validPath, parsed.data.edits, parsed.data.dryRun);
                return {
                    content: [{ type: "text", text: result }],
                };
            }
            case "create_directory": {
                const parsed = CreateDirectoryArgsSchema.safeParse(args);
                if (!parsed.success) {
                    throw new Error(`Invalid arguments for create_directory: ${parsed.error}`);
                }
                const validPath = yield validatePath(parsed.data.path);
                yield promises_1.default.mkdir(validPath, { recursive: true });
                return {
                    content: [{ type: "text", text: `Successfully created directory ${parsed.data.path}` }],
                };
            }
            case "list_directory": {
                const parsed = ListDirectoryArgsSchema.safeParse(args);
                if (!parsed.success) {
                    throw new Error(`Invalid arguments for list_directory: ${parsed.error}`);
                }
                const validPath = yield validatePath(parsed.data.path);
                const entries = yield promises_1.default.readdir(validPath, { withFileTypes: true });
                const formatted = entries
                    .map((entry) => `${entry.isDirectory() ? "[DIR]" : "[FILE]"} ${entry.name}`)
                    .join("\n");
                return {
                    content: [{ type: "text", text: formatted }],
                };
            }
            case "directory_tree": {
                const parsed = DirectoryTreeArgsSchema.safeParse(args);
                if (!parsed.success) {
                    throw new Error(`Invalid arguments for directory_tree: ${parsed.error}`);
                }
                function buildTree(currentPath) {
                    return __awaiter(this, void 0, void 0, function* () {
                        const validPath = yield validatePath(currentPath);
                        const entries = yield promises_1.default.readdir(validPath, { withFileTypes: true });
                        const result = [];
                        for (const entry of entries) {
                            const entryData = {
                                name: entry.name,
                                type: entry.isDirectory() ? 'directory' : 'file'
                            };
                            if (entry.isDirectory()) {
                                const subPath = path_1.default.join(currentPath, entry.name);
                                entryData.children = yield buildTree(subPath);
                            }
                            result.push(entryData);
                        }
                        return result;
                    });
                }
                const treeData = yield buildTree(parsed.data.path);
                return {
                    content: [{
                            type: "text",
                            text: JSON.stringify(treeData, null, 2)
                        }],
                };
            }
            case "move_file": {
                const parsed = MoveFileArgsSchema.safeParse(args);
                if (!parsed.success) {
                    throw new Error(`Invalid arguments for move_file: ${parsed.error}`);
                }
                const validSourcePath = yield validatePath(parsed.data.source);
                const validDestPath = yield validatePath(parsed.data.destination);
                yield promises_1.default.rename(validSourcePath, validDestPath);
                return {
                    content: [{ type: "text", text: `Successfully moved ${parsed.data.source} to ${parsed.data.destination}` }],
                };
            }
            case "search_files": {
                const parsed = SearchFilesArgsSchema.safeParse(args);
                if (!parsed.success) {
                    throw new Error(`Invalid arguments for search_files: ${parsed.error}`);
                }
                const validPath = yield validatePath(parsed.data.path);
                const results = yield searchFiles(validPath, parsed.data.pattern, parsed.data.excludePatterns);
                return {
                    content: [{ type: "text", text: results.length > 0 ? results.join("\n") : "No matches found" }],
                };
            }
            case "get_file_info": {
                const parsed = GetFileInfoArgsSchema.safeParse(args);
                if (!parsed.success) {
                    throw new Error(`Invalid arguments for get_file_info: ${parsed.error}`);
                }
                const validPath = yield validatePath(parsed.data.path);
                const info = yield getFileStats(validPath);
                return {
                    content: [{ type: "text", text: Object.entries(info)
                                .map(([key, value]) => `${key}: ${value}`)
                                .join("\n") }],
                };
            }
            case "list_allowed_directories": {
                return {
                    content: [{
                            type: "text",
                            text: `Allowed directories:\n${allowedDirectories.join('\n')}`
                        }],
                };
            }
            default:
                throw new Error(`Unknown tool: ${name}`);
        }
    }
    catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        return {
            content: [{ type: "text", text: `Error: ${errorMessage}` }],
            isError: true,
        };
    }
}));
// Start server
function runServer() {
    return __awaiter(this, void 0, void 0, function* () {
        const transport = new stdio_js_1.StdioServerTransport();
        yield server.connect(transport);
        console.error("Secure MCP Filesystem Server running on stdio");
        console.error("Allowed directories:", allowedDirectories);
    });
}
runServer().catch((error) => {
    console.error("Fatal error running server:", error);
    process.exit(1);
});
