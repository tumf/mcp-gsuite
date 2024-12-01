from apiclient.discovery import build 
from . import gauth
import logging
import base64
import traceback

class GmailService():
    def __init__(self):
        credentials = gauth.get_stored_credentials()
        if not credentials:
            raise RuntimeError("No Oauth2 credentials stored")
        self.service = build('gmail', 'v1', credentials=credentials)

    def _parse_message(self, txt) -> dict | None:
        try:
            payload = txt['payload']
            headers = payload['headers']

            subject = ""
            sender = ""
            for d in headers:
                if d['name'] == 'Subject':
                    subject = d['value']
                if d['name'] == 'From':
                    sender = d['value']

            parts = payload.get('parts')
            #parts = payload.get('parts')[0]
            ##data = parts['body']['data']
            ##data = data.replace("-","+").replace("_","/")
            #decoded_data = base64.b64decode(data)

            #soup = BeautifulSoup(decoded_data , "lxml")
            #body = soup.body()

            return {
                "subject": subject,
                "sender": sender,
                #"message": str(parts),
            }
        except Exception as e:
            tb = traceback.format_exc()
            logging.error(tb)
            logging.error(str(e))
            return None

    def read_emails(self, query=None, max_results=100):
        """
        Fetch and parse emails from Gmail based on a search query.
        
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
                parsed_message = self._parse_message(txt=txt)
                if parsed_message:
                    parsed.append(parsed_message)
                    
            return parsed
            
        except Exception as e:
            print(f"Error reading emails: {str(e)}")
            return []