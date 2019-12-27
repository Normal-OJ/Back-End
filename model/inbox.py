from flask import Blueprint, request

from mongo import *
from .auth import *
from .utils import *

__all__ = ['inbox_api']

inbox_api = Blueprint('inbox_api', __name__)


@inbox_api.route('/', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def inbox(user):
    def get_messages():
        # Get received list
        messages = Inbox.messages(user.username)
        return HTTPResponse('Received List', data=messages)

    @Request.json('receivers', 'title', 'message')
    def send(receivers, title, message):
        # Sent message
        if not all([receivers, isinstance(receivers, list)]):
            return HTTPError('At least one receiver is required', 400)
        try:
            message = Inbox.send(user.username, receivers, title, message)
        except ValidationError as ve:
            return HTTPError('Failed to Send a Message',
                             400,
                             data=ve.to_dict())
        data = {
            'messageId': str(message.id),
            'receivers': message.receivers,
            'timestamp': int(message.timestamp.timestamp())
        }
        return HTTPResponse('Successfully Send', data=data)

    @Request.json('message_id')
    def read(message_id):
        # Read <-> Unread
        message = Inbox(message_id)
        if message.receiver != user.username:
            return HTTPError('Failed to Read the Message', 403)
        message.change_status()
        return HTTPResponse('Message Status Changed',
                            data={'status': message.status})

    @Request.json('message_id')
    def delete(message_id):
        # Delete message
        message = Inbox(message_id)
        if message.receiver != user.username:
            return HTTPError('Failed to Access the Message', 403)
        message.delete()
        return HTTPResponse('Deleted')

    methods = {
        'GET': get_messages,
        'POST': send,
        'PUT': read,
        'DELETE': delete
    }

    return methods[request.method]()


@inbox_api.route('/sent', methods=['GET', 'DELETE'])
@login_required
def sent(user):
    def read():
        # Get sent list
        messages = Inbox.sents(user.username)
        return HTTPResponse('Sent List', data=messages)

    @Request.json('message_id')
    def delete(message_id):
        # Delete message
        try:
            sent = Inbox.sent(message_id)
        except (DoesNotExist, ValidationError):
            return HTTPError('Message Not Found', 404)
        if sent.sender != user.username:
            return HTTPError('Failed to Access the Message', 403)
        sent.update(status=1)
        return HTTPResponse('Deleted')

    methods = {'GET': read, 'DELETE': delete}

    return methods[request.method]()
