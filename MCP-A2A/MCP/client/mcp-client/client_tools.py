import asyncio
import os
from openai import OpenAI
from dotenv import load_dotenv
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import json

# 加载 .env 文件
load_dotenv()

class MCPClient:
    def __init__(self):
        """初始化 MCP 客户端"""
        self.exit_stack = AsyncExitStack()
        self.api_key = os.getenv("API_KEY")  # 读取 OpenAI API Key
        self.base_url = os.getenv("BASE_URL")  # 读取 BASE URL
        self.model = os.getenv("MODEL")  # 读取 model
       
        if not self.api_key:
            raise ValueError("未找到 API KEY. 请在 .env 文件中配置 API_KEY")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.sessions = {}  # 存储多个服务端会话
        self.tools_map = {}  # 工具映射：工具名称 -> 服务端 ID

    async def connect_to_server(self, server_id: str, server_script_path: str):
        """
        连接到 MCP 服务器
        :param server_id: 服务端标识符
        :param server_script_path: 服务端脚本路径
        """
        if server_id in self.sessions:
            raise ValueError(f"服务端 {server_id} 已经连接")

        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("服务器脚本必须是 Python 或 JavaScript 文件")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(command=command,
                                              args=[server_script_path],
                                              env=None)

        # 启动 MCP 服务器并建立通信
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params))
        stdio, write = stdio_transport
        session = await self.exit_stack.enter_async_context(
            ClientSession(stdio, write))

        await session.initialize()
        self.sessions[server_id] = {"session": session, "stdio": stdio, "write": write}
        print(f"已连接到 MCP 服务器: {server_id}")

        # 更新工具映射
        response = await session.list_tools()
        for tool in response.tools:
            self.tools_map[tool.name] = server_id
   
    async def list_tools(self):
        """列出所有服务端的工具"""
        if not self.sessions:
            print("没有已连接的服务端")
            return

        print("已连接的服务端工具列表:")
        for tool_name, server_id in self.tools_map.items():
            print(f"工具: {tool_name}, 来源服务端: {server_id}")

    async def process_query(self, query: str) -> str:
        """
        调用大模型处理用户查询，并根据返回的 tools 列表调用对应工具。
        支持多次工具调用，直到所有工具调用完成。
        """
        messages = [{"role": "user", "content": query}]

        # 构建统一的工具列表
        available_tools = []
        for tool_name, server_id in self.tools_map.items():
            session = self.sessions[server_id]["session"]
            response = await session.list_tools()
            for tool in response.tools:
                if tool.name == tool_name:
                    available_tools.append({
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "input_schema": tool.inputSchema
                        }
                    })

        print('整合的服务端工具列表:', available_tools)

        # 循环处理工具调用
        while True:
            # 请求 OpenAI 模型处理
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=available_tools
            )

            # 处理返回的内容
            content = response.choices[0]
            if content.finish_reason == "tool_calls":
                # 执行工具调用
                for tool_call in content.message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

                    # 根据工具名称找到对应的服务端
                    server_id = self.tools_map.get(tool_name)
                    if not server_id:
                        raise ValueError(f"未找到工具 {tool_name} 对应的服务端")

                    session = self.sessions[server_id]["session"]
                    result = await session.call_tool(tool_name, tool_args)
                    print(f"\n\n[Calling tool {tool_name} on server {server_id} with args {tool_args}]\n\n")

                    # 将工具调用的结果添加到 messages 中
                    messages.append({
                        "role": "tool",
                        "content": result.content[0].text,
                        "tool_call_id": tool_call.id,
                    })

            else:
                # 如果没有工具调用，返回最终的回复
                return content.message.content
   
    async def chat_loop(self):
        """运行交互式聊天循环"""
        print("MCP 客户端已启动！输入 'exit' 退出")

        while True:
            try:
                query = input("问: ").strip()
                if query.lower() == 'exit':
                    break

                response = await self.process_query(query)
                print(f"AI回复: {response}")

            except Exception as e:
                print(f"发生错误: {str(e)}")

    async def clean(self):
        """清理所有资源"""
        await self.exit_stack.aclose()
        self.sessions.clear()
        self.tools_map.clear()

async def main():
    # 启动并初始化 MCP 客户端
    client = MCPClient()
    try:
        # 连接多个 MCP 服务器
        await client.connect_to_server("weather", '../../server/weather/weather.py')
        await client.connect_to_server("search", '../../server/search/search.py')
        await client.connect_to_server("webshop", '/root/wrp/MCP-A2A/MCP/server/webshop/webshop.py')
        # 列出 MCP 服务器上的工具
        # await client.connect_to_server("webshop", '../../server/webshop/webshop.py')
        await client.list_tools()
        # 运行交互式聊天循环，处理用户对话
        await client.chat_loop()
    finally:
        # 清理资源
        await client.clean()

if __name__ == "__main__":
    asyncio.run(main())
