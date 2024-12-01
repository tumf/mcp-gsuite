from collections.abc import Sequence
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel,
)
from . import gauth
from . import gmail
import json

class ToolHandler():
    def __init__(self, tool_name: str):
        self.name = tool_name

    def get_tool_description(self) -> Tool:
        raise NotImplementedError()

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        raise NotImplementedError()
    

class GetUserInfoToolHandler(ToolHandler):
    def __init__(self):
        super().__init__("get_gmail_user_info")

    def get_tool_description(self) -> Tool:
        return Tool(
           name=self.name,
           description="""Returns the gmail user info.""",
           inputSchema={
               "type": "object",
               "properties": {},
               "required": []
           }
       )

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        credentials = gauth.get_stored_credentials()
        user_info = gauth.get_user_info(credentials=credentials)
        return [
            TextContent(
                type="text",
                text=json.dumps(user_info, indent=2)
            )
        ]
    
class QueryEmailsToolHandler(ToolHandler):
    def __init__(self):
        super().__init__("query_gmail_emails")

    def get_tool_description(self) -> Tool:
        return Tool(
            name=self.name,
            description="Query Gmail emails based on an optional search query. Returns emails in reverse chronological order (newest first).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": """Gmail search query (optional). Examples:
                            - a $string: Search email body, subject, and sender information for $string
                            - 'is:unread' for unread emails
                            - 'from:example@gmail.com' for emails from a specific sender
                            - 'newer_than:2d' for emails from last 2 days
                            - 'has:attachment' for emails with attachments
                            If not provided, returns recent emails without filtering.""",
                        "required": False
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of emails to retrieve (1-500)",
                        "minimum": 1,
                        "maximum": 500,
                        "default": 100
                    }
                },
                "required": []
            }
        )

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        gmail_service = gmail.GmailService()
        query = args.get('query')
        max_results = args.get('max_results', 100)
        emails = gmail_service.query_emails(query=query, max_results=max_results)

        return [
            TextContent(
                type="text",
                text=json.dumps(emails, indent=2)
            )
        ]
    
class GetEmailByIdToolHandler(ToolHandler):
    def __init__(self):
        super().__init__("get_gmail_email")

    def get_tool_description(self) -> Tool:
        return Tool(
            name=self.name,
            description="Retrieves a complete Gmail email message by its ID, including the full message body.",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "The ID of the Gmail message to retrieve"
                    }
                },
                "required": ["email_id"]
            }
        )

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        if "email_id" not in args:
            raise RuntimeError("Missing required argument: email_id")

        gmail_service = gmail.GmailService()
        email = gmail_service.get_email_by_id(args["email_id"])

        if email is None:
            return [
                TextContent(
                    type="text",
                    text=f"Failed to retrieve email with ID: {args['email_id']}"
                )
            ]

        return [
            TextContent(
                type="text",
                text=json.dumps(email, indent=2)
            )
        ]
    

class CreateDraftToolHandler(ToolHandler):
    def __init__(self):
        super().__init__("create_gmail_draft")

    def get_tool_description(self) -> Tool:
        return Tool(
            name=self.name,
            description="Creates a draft email message in Gmail with specified recipient, subject, body, and optional CC recipients.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Email address of the recipient"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Subject line of the email"
                    },
                    "body": {
                        "type": "string",
                        "description": "Body content of the email"
                    },
                    "cc": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Optional list of email addresses to CC"
                    }
                },
                "required": ["to", "subject", "body"]
            }
        )

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        required = ["to", "subject", "body"]
        if not all(key in args for key in required):
            raise RuntimeError(f"Missing required arguments: {', '.join(required)}")

        gmail_service = gmail.GmailService()
        draft = gmail_service.create_draft(
            to=args["to"],
            subject=args["subject"],
            body=args["body"],
            cc=args.get("cc")
        )

        if draft is None:
            return [
                TextContent(
                    type="text",
                    text="Failed to create draft email"
                )
            ]

        return [
            TextContent(
                type="text",
                text=json.dumps(draft, indent=2)
            )
        ]