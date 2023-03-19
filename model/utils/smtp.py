from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP
from typing import Optional, Iterable

import os
import threading

__all__ = ['send_noreply']


def send(
    from_addr: str,
    password: str,
    to_addrs: Iterable[str],
    subject: str,
    text: str,
    html: str,
):
    SMTP_SERVER = os.environ.get('SMTP_SERVER')
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


def send_noreply(
    to_addrs: Iterable[str],
    subject: str,
    text: str,
    html: Optional[str] = None,
):
    SMTP_NOREPLY = os.environ.get('SMTP_NOREPLY')
    SMTP_NOREPLY_PASSWORD = os.environ.get('SMTP_NOREPLY_PASSWORD')
    args = (
        SMTP_NOREPLY,
        SMTP_NOREPLY_PASSWORD,
        to_addrs,
        subject,
        text,
        html or text,
    )
    threading.Thread(target=send, args=args).start()
