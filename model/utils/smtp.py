from email.message import EmailMessage
from smtplib import SMTP_SSL

import os
import threading

__all__ = ['send_noreply']

SMTP_SERVER = os.environ.get('SMTP_SERVER')
SMTP_ADMIN = os.environ.get('SMTP_ADMIN')
SMTP_ADMIN_PASSWORD = os.environ.get('SMTP_PASSWORD')
SMTP_NOREPLY = os.environ.get('SMTP_NOREPLY')
SMTP_NOREPLY_PASSWORD = os.environ.get('SMTP_NOREPLY_PASSWORD')


def send(from_addr, password, to_addrs, subject, content):
    if SMTP_SERVER is None:
        return
    with SMTP_SSL(SMTP_SERVER) as server:
        server.login(from_addr, password)
        msg = EmailMessage()
        msg['From'] = from_addr
        msg['To'] = ', '.join(to_addrs)
        msg['Subject'] = subject
        msg.set_content(content)
        server.send_message(msg, from_addr, to_addrs)


def send_noreply(to_addrs, subject, content):
    args = (SMTP_NOREPLY, SMTP_NOREPLY_PASSWORD, to_addrs, subject, content)
    threading.Thread(target=send, args=args).start()
