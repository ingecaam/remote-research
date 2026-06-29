from contextlib import AsyncExitStack
import json

from dotenv import load_dotenv
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from typing import Dict, List, TypedDict
import asyncio
import nest_asyncio

nest_asyncio.apply()

load_dotenv()
# To allow connect to remote MCP servers
class ToolDefinition(TypedDict):
    name: str
    description: str
    input_schema: dict
    
class MCP_ChatBot:

    def __init__(self):
        # Initialize session and client objects
        # self.session: ClientSession = None  Works with only the MCP server built
        # To allow connect to remote MCP servers
        self.sessions: List[ClientSession] = [] # new
        self.exit_stack = AsyncExitStack() # new
        self.anthropic = Anthropic()
        # self.available_tools: List[dict] = [] Works with only the MCP server built
        # To allow connect to remote MCP servers
        self.available_tools: List[ToolDefinition] = [] # new
        self.tool_to_session: Dict[str, ClientSession] = {} # new

    async def process_query(self, query):
        messages = [{'role':'user', 'content':query}]
        response = self.anthropic.messages.create(max_tokens = 2024,
                                      #model = 'claude-3-7-sonnet-20250219', #deprecated model
                                      model = 'claude-sonnet-4-6',
                                      tools = self.available_tools, # tools exposed to the LLM
                                      messages = messages)
        process_query = True
        while process_query:
            assistant_content = []
            tool_results = []  # ← acumula TODOS los resultados aquí
            for content in response.content:
                if content.type =='text':
                    print(content.text)
                    assistant_content.append(content)
                    if(len(response.content) == 1):
                        process_query= False
                elif content.type == 'tool_use':
                    assistant_content.append(content)
                    tool_id = content.id
                    tool_args = content.input
                    tool_name = content.name
    
                    print(f"Calling tool {tool_name} with args {tool_args}")
                    
                    # Call a tool
                    #result = execute_tool(tool_name, tool_args): not anymore needed
                    # tool invocation through the client session
                    # result = await self.session.call_tool(tool_name, arguments=tool_args) Works with only the MCP server built
                    # To allow connect to remote MCP servers
                    session = self.tool_to_session[tool_name] # new
                    result = await session.call_tool(tool_name, arguments=tool_args) # new 
                    tool_results.append({       # ← acumula, no envíes todavía
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result.content
                    })
            messages.append({'role':'assistant', 'content':assistant_content})
            if tool_results:
                # Un solo mensaje con TODOS los tool_results juntos
                messages.append({"role": "user", "content": tool_results})
                response = self.anthropic.messages.create(max_tokens = 2024,
                                    #model = 'claude-3-7-sonnet-20250219', #deprecated model
                                    model = 'claude-sonnet-4-6', 
                                    tools = self.available_tools,
                                    messages = messages) 
            else:
                process_query= False

    
    
    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Chatbot Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
        
                if query.lower() == 'quit':
                    break
                    
                await self.process_query(query)
                print("\n")
                    
            except Exception as e:
                print(f"\nError: {str(e)}")
    
    # works only with the MCP server built
    # async def connect_to_server_and_run(self):
    #     # Create server parameters for stdio connection
    #     server_params = StdioServerParameters(
    #         command="uv",  # Executable
    #         args=["run", "research_server.py"],  # Optional command line arguments
    #         env=None,  # Optional environment variables
    #     )
    #     async with stdio_client(server_params) as (read, write):
    #         async with ClientSession(read, write) as session:
    #             self.session = session
    #             # Initialize the connection
    #             await session.initialize()
    
    #             # List available tools
    #             response = await session.list_tools()
                
    #             tools = response.tools
    #             print("\nConnected to server with tools:", [tool.name for tool in tools])
                
    #             self.available_tools = [{
    #                 "name": tool.name,
    #                 "description": tool.description,
    #                 "input_schema": tool.inputSchema
    #             } for tool in response.tools]
    
    #             await self.chat_loop()

# To allow connect to remote MCP servers
###################################################################################
    async def cleanup(self): # new
        """Cleanly close all resources using AsyncExitStack."""
        await self.exit_stack.aclose()
    async def connect_to_server(self, server_name: str, server_config: dict) -> None:
        """Connect to a single MCP server."""
        try:
            server_params = StdioServerParameters(**server_config)
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            ) # new
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            ) # new
            await session.initialize()
            self.sessions.append(session)
            
            # List available tools for this session
            response = await session.list_tools()
            tools = response.tools
            print(f"\nConnected to {server_name} with tools:", [t.name for t in tools])
            
            for tool in tools: # new
                self.tool_to_session[tool.name] = session
                self.available_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                })
        except Exception as e:
            print(f"Failed to connect to {server_name}: {e}")

    async def connect_to_servers(self): # new
        """Connect to all configured MCP servers."""
        try:
            with open("server_config.json", "r") as file:
                data = json.load(file)
            
            servers = data.get("mcpServers", {})
            
            for server_name, server_config in servers.items():
                await self.connect_to_server(server_name, server_config)
        except Exception as e:
            print(f"Error loading server configuration: {e}")
            raise    
#############################################################

async def main():
    chatbot = MCP_ChatBot()
    #await chatbot.connect_to_server_and_run()   works only with the MCP server built
    # To allow connect to remote MCP servers
    try:
        # the mcp clients and sessions are not initialized using "with"
        # like in the previous lesson
        # so the cleanup should be manually handled
        await chatbot.connect_to_servers() # new! 
        await chatbot.chat_loop()
    finally:
        await chatbot.cleanup() #new! 

if __name__ == "__main__":
    asyncio.run(main())