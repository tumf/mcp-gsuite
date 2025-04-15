import logging
from collections.abc import Sequence
from functools import lru_cache
import subprocess
from typing import Any
import traceback
from dotenv import load_dotenv
from mcp.server import Server
import threading
import sys
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    Resource,
)
import json
from . import gauth
from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.parse import (
    urlparse,
    parse_qs,
)

class OauthListener(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path != "/code":
            self.send_response(404)
            self.end_headers()
            return

        query = parse_qs(url.query)
        if "code" not in query:
            self.send_response(400)
            self.end_headers()
            return
        
        self.send_response(200)
        self.end_headers()
        self.wfile.write("Auth successful! You can close the tab!".encode("utf-8"))
        self.wfile.flush()

        storage = {}
        creds = gauth.get_credentials(authorization_code=query["code"][0], state=storage)

        t = threading.Thread(target = self.server.shutdown)
        t.daemon = True
        t.start()

        

load_dotenv()

from . import tools_gmail
from . import tools_calendar
from . import toolhandler


# Load environment variables

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-gsuite")

def start_auth_flow(user_id: str):
    auth_url = gauth.get_authorization_url(user_id, state={})
    if sys.platform == "darwin" or sys.platform.startswith("linux"):
        subprocess.Popen(['open', auth_url])
    else:
        import webbrowser
        webbrowser.open(auth_url)

    # start server for code callback
    server_address = ('', 4100)
    server = HTTPServer(server_address, OauthListener)
    server.serve_forever()


def setup_oauth2(user_id: str):
    accounts = gauth.get_account_info()
    if len(accounts) == 0:
        raise RuntimeError("No accounts specified in .gauth.json")
    if user_id not in [a.email for a in accounts]:
        raise RuntimeError(f"Account for email: {user_id} not specified in .gauth.json")

    credentials = gauth.get_stored_credentials(user_id=user_id)
    if not credentials:
        start_auth_flow(user_id=user_id)
    else:
        if credentials.access_token_expired:
            logger.error("credentials expired. try refresh")

        # this call refreshes access token
        user_info = gauth.get_user_info(credentials=credentials)
        #logging.error(f"User info: {json.dumps(user_info)}")
        gauth.store_credentials(credentials=credentials, user_id=user_id)


# 最初にカスタムサーバークラスを定義
class GsuiteServer(Server):
    def __init__(self, name: str):
        super().__init__(name)
        self.tool_handlers = {}
        
    def add_tool_handler(self, tool_class: toolhandler.ToolHandler):
        self.tool_handlers[tool_class.name] = tool_class
        
    def get_tool_handler(self, name: str) -> toolhandler.ToolHandler | None:
        if name not in self.tool_handlers:
            return None
        return self.tool_handlers[name]
        
    async def handle_method(self, method: str, params: dict) -> Any:
        logging.info(f"Handling method: {method}")
        if method == "tools/list":
            logging.info("tools/list method called")
            return {"tools": [vars(th.get_tool_description()) for th in self.tool_handlers.values()]}
        return await super().handle_method(method, params)

# Serverインスタンスを作成
app = GsuiteServer("mcp-gsuite")

# ツールハンドラーの登録
app.add_tool_handler(tools_gmail.QueryEmailsToolHandler())
app.add_tool_handler(tools_gmail.GetEmailByIdToolHandler())
app.add_tool_handler(tools_gmail.CreateDraftToolHandler())
app.add_tool_handler(tools_gmail.DeleteDraftToolHandler())
app.add_tool_handler(tools_gmail.ReplyEmailToolHandler())
app.add_tool_handler(tools_gmail.GetAttachmentToolHandler())
app.add_tool_handler(tools_gmail.BulkGetEmailsByIdsToolHandler())
app.add_tool_handler(tools_gmail.BulkSaveAttachmentsToolHandler())

app.add_tool_handler(tools_calendar.ListCalendarsToolHandler())
app.add_tool_handler(tools_calendar.GetCalendarEventsToolHandler())
app.add_tool_handler(tools_calendar.CreateCalendarEventToolHandler())
app.add_tool_handler(tools_calendar.DeleteCalendarEventToolHandler())

@app.list_resources()
async def list_resources() -> list[Resource]:
    """List available tools."""
    logging.info("resources/list method called")
    tools = [th.get_tool_description() for th in app.tool_handlers.values()]
    # Toolオブジェクトを辞書に変換し、Resourceとして返す
    resources = []
    for tool in tools:
        resource_dict = {
            "id": tool.name,
            "type": "tool",
            "name": tool.name,
            "uri": f"mcp://tool/{tool.name}",
            "description": tool.description,
            "metadata": {
                "inputSchema": tool.inputSchema
            }
        }
        resources.append(Resource(**resource_dict))
    return resources

@app.list_prompts()
async def list_prompts() -> list[dict]:
    """List available prompts."""
    logging.info("prompts/list method called")
    return []  # このMCPサーバーではプロンプトを提供しない

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    logging.info(f"call_tool method called with name: {name}")
    try:        
        if not isinstance(arguments, dict):
            raise RuntimeError("arguments must be dictionary")
        
        if toolhandler.USER_ID_ARG not in arguments:
            raise RuntimeError("user_id argument is missing in dictionary.")

        setup_oauth2(user_id=arguments.get(toolhandler.USER_ID_ARG, ""))

        tool_handler = app.get_tool_handler(name)
        if not tool_handler:
            raise ValueError(f"Unknown tool: {name}")

        return tool_handler.run_tool(arguments)
    except Exception as e:
        logging.error(traceback.format_exc())
        logging.error(f"Error during call_tool: str(e)")
        raise RuntimeError(f"Caught Exception. Error: {str(e)}")

async def main():
    logging.info(f"Platform: {sys.platform}")
    try:
        # Check configuration files
        gauth_file = gauth.get_gauth_file()
        accounts_file = gauth.get_accounts_file()
        logging.info(f"Using gauth file: {gauth_file}")
        logging.info(f"Using accounts file: {accounts_file}")

        accounts = gauth.get_account_info()
        logging.info(f"Found {len(accounts)} account(s)")
        for account in accounts:
            creds = gauth.get_stored_credentials(user_id=account.email)
            if creds:
                logging.info(f"Found credentials for {account.email}")

        from mcp.server.stdio import stdio_server
        
        logging.info("Starting MCP server...")
        async with stdio_server() as (read_stream, write_stream):
            logging.info("MCP server initialized, running main loop...")
            logging.info(f"Available methods: resources/list, prompts/list, tools/list, call_tool")
            
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
    except Exception as e:
        logging.error(f"Error in main: {str(e)}")
        logging.error(traceback.format_exc())
        raise