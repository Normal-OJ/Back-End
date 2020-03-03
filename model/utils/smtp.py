from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP

import os
import threading

__all__ = ['send_noreply']

SMTP_SERVER = os.environ.get('SMTP_SERVER')
SMTP_ADMIN = os.environ.get('SMTP_ADMIN')
SMTP_ADMIN_PASSWORD = os.environ.get('SMTP_PASSWORD')
SMTP_NOREPLY = os.environ.get('SMTP_NOREPLY')
SMTP_NOREPLY_PASSWORD = os.environ.get('SMTP_NOREPLY_PASSWORD')


def send(from_addr, password, to_addrs, subject, text, html):
    if SMTP_SERVER is None:
        return
    with SMTP(SMTP_SERVER, 587) as server:
        server.login(from_addr, password)
        msg = MIMEMultipart('alternative')
        msg['From'] = from_addr
        msg['To'] = ', '.join(to_addrs)
        msg['Subject'] = subject
        msg.attach(MIMEText(text, 'plain'))
        msg.attach(MIMEText(html, 'html'))
        server.send_message(msg, from_addr, to_addrs)


def send_noreply(to_addrs, subject, text, html=None):
    args = (SMTP_NOREPLY, SMTP_NOREPLY_PASSWORD, to_addrs, subject, text, html or text)
    threading.Thread(target=send, args=args).start()
