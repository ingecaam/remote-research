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
        self.exit_stack = AsyncExitStack() 
        self.anthropic = Anthropic()
        self.available_tools= []
        self.available_prompts= []
        self.sessions = {} 


    async def process_query(self, query):
        messages = [{'role':'user', 'content':query}]

        while True:
            response = self.anthropic.messages.create(max_tokens = 2024,
                #model = 'claude-3-7-sonnet-20250219', #deprecated model
                model = 'claude-sonnet-4-6',
                tools = self.available_tools, # tools exposed to the LLM
                messages = messages)
            assistant_content = []
            has_tool_use = False
            tool_results = []  # ← acumula TODOS los resultados aquí
            for content in response.content:
                if content.type =='text':
                    print(content.text)
                    assistant_content.append(content)
                elif content.type == 'tool_use':
                    has_tool_use = True
                    assistant_content.append(content)
                    tool_id = content.id
                    tool_args = content.input
                    tool_name = content.name
    
                    session = self.sessions.get(tool_name)
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
            #Exit the loop if no tool was used in this iteration    
            if not has_tool_use:
                break

    async def get_resource(self, resource_uri):
        session = self.sessions.get(resource_uri)
        #Fallback for papers URIs - try any papers resource session
        if not session and resource_uri.startswith("papers://"):
            for uri, sess in self.sessions.items():
                if uri.startswith("papers://"):
                    session = sess
                    break
        if not session:
            print(f"Resource {resource_uri} not found.")
        try:
            result = await session.read_resource(uri=resource_uri)
            if(result and result.contents):
                print(f"Resource {resource_uri}")
                print("Content:")
                print(result.contents[0].text)
            else:
                print("No content available.")
        except Exception as e:
            print(f"Error : {e}")

    async def list_prompts(self):
        """List all available prompts"""
        if not self.available_prompts:
            print("No prompts available.")
            return
        print("\nAvailable Prompts:")
        for prompt in self.available_prompts:
            # Soporta tanto objeto como dict
            name = prompt.name if hasattr(prompt, 'name') else prompt.get('name', '')
            description = prompt.description if hasattr(prompt, 'description') else prompt.get('description', '')
            arguments = prompt.arguments if hasattr(prompt, 'arguments') else prompt.get('arguments', [])

            print(f"- {name}: {description}")
            if arguments:
                print("  Arguments:")
                for arg in arguments:
                    arg_name = arg.name if hasattr(arg, 'name') else arg.get('name', '')
                    print(f"    - {arg_name}")

    async def execute_prompt(self, prompt_name, args):
        """Execute a specific prompt with given arguments"""
        session = self.sessions.get(prompt_name)
        if not session:
            print(f"Prompt {prompt_name} not found.")
            return
        try:
            result = await session.get_prompt(prompt_name, arguments=args)
            if(result and result.messages):
                prompt_content = result.messages[0].content
                # Extract text from the prompt content (handle different formats)
                if isinstance(prompt_content, str):
                    text = prompt_content
                elif hasattr(prompt_content, 'text'):
                    text = prompt_content.text
                else:
                    #Handle list of content items
                    text = " ".join(item.text if hasattr(item, 'text') else str(item) for item in prompt_content)
                print(f"\nExecuting prompt {prompt_name}...")
                await self.process_query(text)
        except Exception as e:
            print(f"Error : {e}")

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Chatbot Started!")
        print("Type your queries or 'quit' to exit.")
        print("Use @folders to see available topics")
        print("Use @<topic> to search papers in that topic")
        print("Use /prompts to list available prompts")
        print("Use /prompt <name> <arg1=value1> to execute a prompt")
        while True:
            try:
                query = input("\nQuery: ").strip()

                if not query:
                    continue  
        
                if query.lower() == 'quit':
                    break

                # Check for @resource syntax first
                if query.startswith("@"):
                    topic = query[1:]  # Remove the '@' prefix
                    if topic == "folders":
                        resource_uri = "papers://folders"
                    else:
                        resource_uri = f"papers://{topic}"
                    await self.get_resource(resource_uri)
                    continue

                # Check for /prompts syntax
                if(query.startswith("/")):
                    parts = query.split()
                    command = parts[0].lower()
                    if command == "/prompts":
                        await self.list_prompts()
                    elif command == "/prompt":
                        if len(parts) < 2:
                            print("Usage: /prompt <name> <arg1=value1> <arg2=value2>")
                            continue
                        prompt_name = parts[1]
                        args = {}
                        #parse arguments
                        for arg in parts[2:]:
                            if '=' in arg:
                                key, value = arg.split('=', 1)
                                args[key] = value

                        await self.execute_prompt(prompt_name, args)  
                    else:
                        print(f"Unknown command {command}")
                        continue 
                await self.process_query(query)
                    
            except Exception as e:
                print(f"\nError: {str(e)}")

# To allow connect to remote MCP servers
###################################################################################
    async def cleanup(self): # new
        """Cleanly close all resources using AsyncExitStack."""
        await self.exit_stack.aclose()

    async def connect_to_server(self, server_name, server_config) -> None:
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

            try:
                # List available tools for this session
                response = await session.list_tools()
                for tool in response.tools: # new
                    self.sessions[tool.name] = session
                    self.available_tools.append({
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.inputSchema
                    })
                # List available prompts
                prompts_response = await session.list_prompts()
                if prompts_response and prompts_response.prompts:
                    for prompt in prompts_response.prompts: 
                        self.sessions[prompt.name] = session
                        self.available_prompts.append({
                            "name": prompt.name,
                            "description": prompt.description,
                            "input_schema": prompt.arguments
                        })
                # List available resources
                resources_response = await session.list_resources()
                if resources_response and resources_response.resources:
                    for resource in resources_response.resources:
                        resource_uri = str(resource.uri)
                        self.sessions[resource_uri] = session

            except Exception as e:
                print(f"Error {e}")
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
    try:
        await chatbot.connect_to_servers() 
        await chatbot.chat_loop()
    finally:
        await chatbot.cleanup() 

if __name__ == "__main__":
    asyncio.run(main())