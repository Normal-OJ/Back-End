from mongoengine import *

import mongoengine
import os

__all__ = [*mongoengine.__all__]

MONGO_HOST = os.environ.get('MONGO_HOST', 'mongomock://localhost')
connect('normal-oj', host=MONGO_HOST)


class Profile(EmbeddedDocument):
    displayed_name = StringField(db_field='displayedName',
                                 required=True,
                                 max_length=16)
    bio = StringField(max_length=64, required=True, default='')


class EditorConfig(EmbeddedDocument):
    font_size = IntField(db_field='fontSize',
                         min_value=8,
                         max_value=72,
                         default=14)
    theme = StringField(default='default',
                        choices=[
                            "default", "base16-dark", "base16-light",
                            "dracula", "eclipse", "material", "monokai"
                        ])
    indent_type = IntField(db_field='indentType', default=1, choices=[0, 1])
    tab_size = IntField(db_field='tabSize',
                        default=4,
                        min_value=1,
                        max_value=8)
    language = IntField(default=0, choices=[0, 1, 2])


class User(Document):
    user_id = StringField(db_field='userId',
                          max_length=24,
                          required=True,
                          unique=True)
    username = StringField(max_length=16, required=True, unique=True)
    email = EmailField(required=True, unique=True)
    active = BooleanField(default=False)
    role = IntField(default=2, choices=[0, 1, 2])
    profile = EmbeddedDocumentField(Profile, default=Profile, null=True)
    editor_config = EmbeddedDocumentField(EditorConfig,
                                          db_field='editorConfig',
                                          default=EditorConfig,
                                          null=True)
    # contest_id = ReferenceField('Contest', db_field='contestId')
    course_ids = ListField(ReferenceField('Course'), db_field='courseIds')
    # submission_ids = ListField(ReferenceField('Submission'), db_field='submissionIds')


class Course(Document):
    course_status = IntField(default=0, choices=[0, 1])
    course_name = StringField(max_length=64,
                              required=True,
                              unique=True,
                              db_field='courseName')
    teacher = ReferenceField('User', db_field='teacher')
    tas = ListField(ReferenceField('User'), db_field='tas')
    student_nicknames = DictField(db_field='studentNicknames')
    # contest_ids = ListField(ReferenceField('Contest'), db_field='contestIds')
    homework_ids = ListField(ReferenceField('Homework'), db_field='homeworkIds')
    # announcement_ids = ListField(ReferenceField('Announcement'), db_field='announcementIds')
    # post_ids = ListField(ReferenceField('Post'), db_field='postIds')


class Number(Document):
    name = StringField()
    number = IntField()


class ProblemTestCase(EmbeddedDocument):
    language = IntField(choices=[1, 2, 4])
    fill_in_template = StringField(db_field='fillInTemplate', max_length=16000)
    cases = ListField(DictField())


class Problem(Document):
    problem_id = IntField(db_field='problemId', required=True, unique=True)
    course_ids = ListField(ReferenceField('Course'), db_field='courseIds')
    problem_status = IntField(default=1, choices=[0, 1])
    problem_type = IntField(default=0, choices=[0, 1])
    problem_name = StringField(db_field='problemName',
                               max_length=64,
                               required=True)
    description = StringField(max_length=100000, required=True)
    owner = StringField(max_length=16, required=True)
    # pdf =
    tags = ListField(StringField(max_length=16))
    test_case = EmbeddedDocumentField(ProblemTestCase,
                                      db_field='testCase',
                                      default=ProblemTestCase,
                                      null=True)
    ac_user = IntField(db_field='ACUser', default=0)
    submitter = IntField(default=0)


class Duration(EmbeddedDocument):
    start = DateTimeField()
    end = DateTimeField()


class Homework(Document):
    name = StringField(max_length=64, required=True, db_field='homeworkName')
    markdown = StringField(max_length=10000)
    scoreboard_status = IntField(default=0,
                                 choice=[0, 1],
                                 db_field='scoreboardStatus')
    course_id = StringField(db_field='courseId')
    duration = EmbeddedDocumentField(Duration,
                                     db_field='duration',
                                     default=Duration)
    problem_ids = ListField(StringField(), db_field='problemIds')
    student_status = DictField(db_field='studentStatus')


class TestCase(EmbeddedDocument):
    status = IntField(required=True)
    exec_time = IntField(required=True)
    memory_usage = IntField(required=True)
    stdout = StringField(required=True)
    stderr = StringField(required=True)


class Submission(Document):
    problem_id = StringField(required=True)
    user = ReferenceField(User, required=True)
    language = IntField(required=True)
    timestamp = DateTimeField(required=True)
    status = IntField(default=-2)
    score = IntField(default=0)
    cases = ListField(EmbeddedDocumentField(TestCase), default=list)
    exec_time = IntField(default=-1)
    memory_usage = IntField(default=-1)
    code = BooleanField(
        default=False)  # wheather the user has uploaded source code


class Message(Document):
    timestamp = DateTimeField(default=datetime.utcnow)
    sender = StringField(max_length=16, required=True)
    receivers = ListField(StringField(max_length=16), required=True)
    status = IntField(default=0, choices=[0, 1])  # not delete / delete
    title = StringField(max_length=32, required=True)
    markdown = StringField(max_length=100000, required=True)


class Inbox(Document):
    receiver = StringField(max_length=16, required=True)
    status = IntField(default=0, choices=[0, 1, 2])  # unread / read / delete
    message = ReferenceField('Message')
