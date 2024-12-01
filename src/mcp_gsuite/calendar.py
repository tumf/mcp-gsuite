from apiclient.discovery import build 
from . import gauth
import logging
import base64
import traceback
from email.mime.text import MIMEText


class CalendarService():
    def __init__(self):
        credentials = gauth.get_stored_credentials()
        if not credentials:
            raise RuntimeError("No Oauth2 credentials stored")
        self.service = build('calendar', 'v1', credentials=credentials)