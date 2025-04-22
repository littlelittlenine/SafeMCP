# await 是 Python 中用于异步编程的关键字，其核心作用是​​暂停当前协程的执行，等待异步操作完成
import asyncio
import sys
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        # MCP会话对象
        # MCP会话对象（ClientSession）是MCP（Model Context Protocol）协议中的核心组件:用于管理客户端与服务器之间的通信会话。
        # MCP会话对象是客户端（如AI应用）与MCP服务器之间建立的​​双向通信通道​​，负责：

        # 协议握手初始化（版本协商、能力交换）
        # 工具/资源的动态调用（如API请求、文件读取）
        # 会话状态维护（连接保持、错误恢复）
        self.session: Optional[ClientSession] = None
        self.stdio = None
        self.write = None
        # 异步资源管理器[9](@ref)
        # 集中管理多个异步资源​​的高级工具
        self.exit_stack = AsyncExitStack()
        # Claude客户端实例化
        self.anthropic = Anthropic()
    # async是编程语言中用于声明异步函数的关键字符号,服务器连接方法
    # 异步函数
    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server
        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        # 检测服务器脚本路径是否为.py或.js文件，否则抛出异常, 确保服务器脚本可以被正确的执行.
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")
        # 根据脚本类型选择解释器（Python用python，JS用node），构建服务器启动参数
        # StdioServerParameters封装了子进程启动参数：
        # command：解释器路径
        # args：脚本路径作为参数
        # env：环境变量（None表示继承当前环境）
        command = "python" if is_python else "node"
        print('server init')
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )
        print('server Done')
        # ​​建立通信管道
        # 建立标准的IO连接,通过stdio_client创建子进程并建立双向通信管道（stdin/stdout），使用AsyncExitStack管理资源生命周期
        # stdio_client(server_params)
        # 创建基于子进程的标准IO通信客户端，参数包含：
        # command：解释器路径（python/node）
        # args：服务器脚本路径
        # 返回一个​​异步上下文管理器​​，管理子进程的生命周期

        # self.exit_stack
        # AsyncExitStack实例，用于集中管理多个异步资源（如这里的stdio管道和后续的会话）
        # enter_async_context:资源注册

        # 在MCP协议中，stdio_client和ClientSession的初始化顺序是严格要求的，这由协议的生命周期设计决定:
        # 必须先通过stdio_client建立标准IO管道（self.stdio和self.write），才能为后续的ClientSession提供通信基础。MCP协议要求所有会话通信必须通过已建立的传输通道进行。
        # MCP连接分为明确的三个阶段：​​传输层建立​​（对应stdio_client）,​协议层初始化​​（对应ClientSession.initialize()）,​​正式通信​
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        print('YES1')
        self.stdio, self.write = stdio_transport
        print('YES2')
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        print('YES3')
        # ​​核心功能​​,​协议握手​​：完成客户端与服务器的首次交互，协商协议版本（如2024-11-05）,​能力交换​​：双方声明支持的功能（如tools工具调用、logging日志等）,​会话准备​​：建立通信上下文，为后续操作（如call_tool()）奠定基础
        await self.session.initialize()
        print('YES4')
        # List available tools
        # 向 MCP 服务器发送请求，获取当前可用的工具列表。
        response = await self.session.list_tools()
        print('YES5')
        # 从响应中提取工具列表数据。
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])
    # MCP（Model Context Protocol）客户端中处理用户查询的核心方法，其功能是通过 Claude 模型和 MCP 服务器提供的工具动态处理用户请求
    # 结合 Claude 模型的能力和 MCP 服务器的工具，实现动态工具调用与结果整合。支持工具调用后的后续交互，将工具结果返回给 Claude 生成最终响应。是不是相当于是外部知识检索增强
    # 工作流程: 1.将用户查询 query 包装为消息格式（role: user） 
    #          2.发送用户消息和工具列表给 Claude: 文本回复​​（content.type == 'text'）：直接加入最终结果。​工具调用请求​​（content.type == 'tool_use'）：进入工具处理流程。
    #          3.利用
    # 请问Claude模型是什么
    async def process_query(self, query: str) -> str:
        """Process a query using Claude and available tools"""
        messages = [
            {
                "role": "user",
                "content": query
            }
        ]

        response = await self.session.list_tools()
        available_tools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]
        # Initial Claude API call
        response = self.anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=messages,
            tools=available_tools
        )
        # Process response and handle tool calls
        final_text = []
        assistant_message_content = []
        for content in response.content:
            if content.type == 'text':
                final_text.append(content.text)
                assistant_message_content.append(content)
            elif content.type == 'tool_use':
                tool_name = content.name
                tool_args = content.input

                # Execute tool call
                result = await self.session.call_tool(tool_name, tool_args)
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")

                assistant_message_content.append(content)
                messages.append({
                    "role": "assistant",
                    "content": assistant_message_content
                })
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": content.id,
                            "content": result.content
                        }
                    ]
                })

                # Get next response from Claude
                response = self.anthropic.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1000,
                    messages=messages,
                    tools=available_tools
                )

                final_text.append(response.content[0].text)

        return "\n".join(final_text)
    # 运行交互式聊天循环，持续接收用户输入并处理。
    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        # 通过while True循环持续监听用户输入：
        while True:
            try:
                query = input("\nQuery: ").strip()
                # 用户输入quit时退出循环
                if query.lower() == 'quit':
                    break
                # 调用process_query(query)处理用户查询（异步等待结果）。
                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")
    # 清理异步资源（如关闭与MCP服务器的连接）。
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()
# 程序入口，初始化MCP客户端并启动聊天循环。
async def main():
    # 检查命令行参数，确保提供了服务器脚本路径。
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)
        
    client = MCPClient()
    print('client Done')
    try:
        print(sys.argv[1])
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()
# python client.py <path_to_server_script>
if __name__ == "__main__":
    asyncio.run(main())