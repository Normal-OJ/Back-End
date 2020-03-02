from . import engine
from .user import *
from .base import *

__all__ = ['Inbox']


class Inbox(MongoBase, engine=engine.Inbox):
    def __init__(self, message_id):
        self.message_id = message_id

    @staticmethod
    def send(sender, receivers, title, message):
        receivers = [*filter(lambda n: User(n), receivers)]
        message = engine.Message(sender=sender,
                                 receivers=receivers,
                                 title=title,
                                 markdown=message)
        message.save()
        for r in receivers:
            engine.Inbox(receiver=r, message=message).save()
        return message

    @staticmethod
    def messages(username):
        messages = sorted(engine.Inbox.objects(receiver=username,
                                               status__ne=2),
                          key=lambda x: x.message.timestamp,
                          reverse=True)
        return [{
            'messageId': str(m.id),
            'status': m.status,
            'sender': User(m.message.sender).info,
            'title': m.message.title,
            'message': m.message.markdown,
            'timestamp': int(m.message.timestamp.timestamp())
        } for m in messages]

    @staticmethod
    def sents(username):
        sents = engine.Message.objects(sender=username,
                                       status=0).order_by('-timestamp')
        return [{
            'messageId': str(s.id),
            'receivers': [User(r).info for r in s.receivers],
            'title': s.title,
            'message': s.markdown,
            'timestamp': int(s.timestamp.timestamp())
        } for s in sents]

    @staticmethod
    def sent(message_id):
        return engine.Message.objects.get(id=message_id, status=0)

    def change_status(self):
        self.update(status=self.status ^ 1)

    def delete(self):
        self.update(status=2)
