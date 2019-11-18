from smtplib import SMTP_SSL
from email.message import EmailMessage


def send(from_addr, to_addrs, subject, content):
	with SMTP_SSL('mail.gandi.net') as server:
		server.login(from_addr, 'pAejTW2rXHQssD8')
		msg = EmailMessage()
		msg['From'] = from_addr
		msg['To'] = ', '.join(to_addrs)
		msg['Subject'] = subject
		msg.set_content(content)
		server.send_message(msg, from_addr, to_addrs)


def send_noreply(to_addrs, subject, content):
	send('noreply@noj.tw', to_addrs, subject, content)
