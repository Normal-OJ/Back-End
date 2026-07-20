from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP
from typing import Optional, Iterable

import threading

from config import settings

__all__ = ['send_noreply']


def send(
    from_addr: str,
    password: Optional[str],
    to_addrs: Iterable[str],
    subject: str,
    text: str,
    html: str,
):
    if settings.SMTP_SERVER is None:
        return
    with SMTP(settings.SMTP_SERVER, 587) as server:
        if password is not None:
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
    args = (
        settings.SMTP_NOREPLY,
        settings.SMTP_NOREPLY_PASSWORD,
        to_addrs,
        subject,
        text,
        html or text,
    )
    threading.Thread(target=send, args=args).start()
