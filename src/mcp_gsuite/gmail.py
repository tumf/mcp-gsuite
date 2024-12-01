from apiclient.discovery import build 
from . import gauth
import logging
import base64
import traceback
from email.mime.text import MIMEText


class GmailService():
    def __init__(self):
        credentials = gauth.get_stored_credentials()
        if not credentials:
            raise RuntimeError("No Oauth2 credentials stored")
        self.service = build('gmail', 'v1', credentials=credentials)

    def _parse_message(self, txt, parse_body=False) -> dict | None:
        """
        Parse a Gmail message into a structured format.
        
        Args:
            txt (dict): Raw message from Gmail API
            parse_body (bool): Whether to parse and include the message body (default: False)
        
        Returns:
            dict: Parsed message containing id, subject, sender, and optionally body
            None: If parsing fails
        """
        try:
            #logging.error("----------------")
            #import json
            #logging.error(json.dumps(txt))
            #logging.error("----------------")
            message_id = txt.get('id')
            payload = txt.get('payload', {})
            headers = payload.get('headers', [])

            # Extract headers
            subject = ""
            sender = ""
            date = ""
            cc = ""
            for header in headers:
                name = header.get('name', '')
                if name == 'Subject':
                    subject = header.get('value', '')
                elif name == 'From':
                    sender = header.get('value', '')
                if name == 'Date':
                    date = header.get('value', '')
                if name == 'Cc':
                    cc = header.get('value', '')

            result = {
                "id": message_id,
                "date": date,
                "subject": subject,
                "from": sender,
                "ccs": cc,
                "labels": txt.get('labelIds'),
                "snippet": txt.get('snippet'),
            }

            # Parse body if requested
            if parse_body:
                body = self._extract_body(payload)
                if body:
                    result["body"] = body

            return result

        except Exception as e:
            logging.error(f"Error parsing message: {str(e)}")
            logging.error(traceback.format_exc())
            return None

    def _extract_body(self, payload) -> str | None:
        """
        Extract the email body from the payload.
        Handles both multipart and single part messages.
        """
        try:
            if payload.get('mimeType') == 'text/plain':
                data = payload.get('body', {}).get('data')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8')
                
            elif payload.get('mimeType') == 'multipart/alternative':
                parts = payload.get('parts', [])
                # Try to find text/plain part first
                for part in parts:
                    if part.get('mimeType') == 'text/plain':
                        data = part.get('body', {}).get('data')
                        if data:
                            return base64.urlsafe_b64decode(data).decode('utf-8')
                            
                # Fall back to first part if no text/plain found
                if parts and 'body' in parts[0] and 'data' in parts[0]['body']:
                    data = parts[0]['body']['data']
                    return base64.urlsafe_b64decode(data).decode('utf-8')

            return None

        except Exception as e:
            logging.error(f"Error extracting body: {str(e)}")
            return None

    def query_emails(self, query=None, max_results=100):
        """
        Query emails from Gmail based on a search query.
        
        Args:
            query (str, optional): Gmail search query (e.g., 'is:unread', 'from:example@gmail.com')
                                If None, returns all emails
            max_results (int): Maximum number of emails to retrieve (1-500, default: 100)
        
        Returns:
            list: List of parsed email messages, newest first
        """
        try:
            # Ensure max_results is within API limits
            max_results = min(max(1, max_results), 500)
            
            # Get the list of messages
            result = self.service.users().messages().list(
                userId='me',
                maxResults=max_results,
                q=query if query else ''
            ).execute()

            messages = result.get('messages', [])
            parsed = []

            # Fetch full message details for each message
            for msg in messages:
                txt = self.service.users().messages().get(
                    userId='me', 
                    id=msg['id']
                ).execute()
                parsed_message = self._parse_message(txt=txt, parse_body=False)
                if parsed_message:
                    parsed.append(parsed_message)
                    
            return parsed
            
        except Exception as e:
            print(f"Error reading emails: {str(e)}")
            return []
        
    def get_email_by_id(self, email_id: str) -> dict | None:
        """
        Fetch and parse a complete email message by its ID.
        
        Args:
            email_id (str): The Gmail message ID to retrieve
        
        Returns:
            dict: Complete parsed email message including body
            None: If retrieval or parsing fails
        """
        try:
            # Fetch the complete message by ID
            message = self.service.users().messages().get(
                userId='me',
                id=email_id
            ).execute()
            
            # Parse the message with body included
            return self._parse_message(txt=message, parse_body=True)
            
        except Exception as e:
            logging.error(f"Error retrieving email {email_id}: {str(e)}")
            logging.error(traceback.format_exc())
            return None
        
    def create_draft(self, to: str, subject: str, body: str, cc: list[str] = None) -> dict | None:
        """
        Create a draft email message.
        
        Args:
            to (str): Email address of the recipient
            subject (str): Subject line of the email
            body (str): Body content of the email
            cc (list[str], optional): List of email addresses to CC
            
        Returns:
            dict: Draft message data including the draft ID if successful
            None: If creation fails
        """
        try:
            # Create message body
            message = {
                'to': to,
                'subject': subject,
                'text': body,
            }
            if cc:
                message['cc'] = ','.join(cc)
                
            # Create the message in MIME format
            mime_message = MIMEText(body)
            mime_message['to'] = to
            mime_message['subject'] = subject
            if cc:
                mime_message['cc'] = ','.join(cc)
                
            # Encode the message
            raw_message = base64.urlsafe_b64encode(mime_message.as_bytes()).decode('utf-8')
            
            # Create the draft
            draft = self.service.users().drafts().create(
                userId='me',
                body={
                    'message': {
                        'raw': raw_message
                    }
                }
            ).execute()
            
            return draft
            
        except Exception as e:
            logging.error(f"Error creating draft: {str(e)}")
            logging.error(traceback.format_exc())
            return None
        
    def delete_draft(self, draft_id: str) -> bool:
        """
        Delete a draft email message.
        
        Args:
            draft_id (str): The ID of the draft to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            self.service.users().drafts().delete(
                userId='me',
                id=draft_id
            ).execute()
            return True
            
        except Exception as e:
            logging.error(f"Error deleting draft {draft_id}: {str(e)}")
            logging.error(traceback.format_exc())
            return False