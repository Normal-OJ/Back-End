from mongoengine import *

import mongoengine
import os
from datetime import datetime

__all__ = [*mongoengine.__all__]

MONGO_HOST = os.environ.get('MONGO_HOST', 'mongomock://localhost')
connect('normal-oj', host=MONGO_HOST)


class Profile(EmbeddedDocument):
    displayed_name = StringField(db_field='displayedName',
                                 default='',
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


class Duration(EmbeddedDocument):
    start = DateTimeField(default=datetime.now())
    end = DateTimeField(default=datetime.max)


class User(Document):
    username = StringField(max_length=16, required=True, primary_key=True)
    user_id = StringField(db_field='userId', max_length=24, required=True)
    user_id2 = StringField(db_field='userId2', max_length=24, default='')
    email = EmailField(required=True, unique=True)
    md5 = StringField(required=True)
    active = BooleanField(default=False)
    role = IntField(default=2, choices=[0, 1, 2])
    profile = EmbeddedDocumentField(Profile, default=Profile)
    editor_config = EmbeddedDocumentField(EditorConfig,
                                          db_field='editorConfig',
                                          default=EditorConfig,
                                          null=True)
    contest = ReferenceField('Contest', db_field='contestId')
    courses = ListField(ReferenceField('Course'))
    submissions = ListField(ReferenceField('Submission'))
    last_submit = DateTimeField(default=datetime.min)
    AC_problem_ids = ListField(IntField(), default=list)
    AC_submission = IntField(default=0)
    submission = IntField(default=0)


class Homework(Document):
    homework_name = StringField(max_length=64,
                                required=True,
                                db_field='homeworkName')
    markdown = StringField(max_length=10000, default='')
    scoreboard_status = IntField(default=0,
                                 choices=[0, 1],
                                 db_field='scoreboardStatus')
    course_id = StringField(required=True, db_field='courseId')
    duration = EmbeddedDocumentField(Duration, default=Duration)
    problem_ids = ListField(IntField(), db_field='problemIds')
    student_status = DictField(db_field='studentStatus')


class Contest(Document):
    name = StringField(max_length=64, required=True, db_field='contestName')
    scoreboard_status = IntField(default=0,
                                 choice=[0, 1],
                                 db_field='scoreboardStatus')
    course_id = StringField(db_field='courseId')
    duration = EmbeddedDocumentField(Duration, default=Duration)
    contest_mode = IntField(default=0, choice=[0, 1], db_field='contestMode')
    problem_ids = ListField(IntField(), db_field='problemIds')
    participants = DictField(db_field='participants')


class Course(Document):
    student_nicknames = DictField(db_field='studentNicknames')
    course_status = IntField(default=0, choices=[0, 1])
    course_name = StringField(max_length=64,
                              required=True,
                              unique=True,
                              db_field='courseName')
    teacher = ReferenceField('User', db_field='teacher')
    tas = ListField(ReferenceField('User'), db_field='tas')
    contests = ListField(ReferenceField('Contest', reverse_delete_rule=PULL),
                         db_field='contests')
    homeworks = ListField(ReferenceField('Homework', reverse_delete_rule=PULL),
                          db_field='homeworks')
    announcements = ListField(ReferenceField('Announcement'),
                              db_field='announcements')
    posts = ListField(ReferenceField('Post'), db_field='posts', default=list)


class Number(Document):
    name = StringField()
    number = IntField(default=1)


class ProblemCase(EmbeddedDocument):
    case_score = IntField(required=True, db_field='caseScore')
    case_count = IntField(required=True, db_field='caseCount')
    memory_limit = IntField(required=True, db_field='memoryLimit')
    time_limit = IntField(required=True, db_field='timeLimit')
    input = ListField(StringField(), default=list)
    output = ListField(StringField(), default=list)


class ProblemTestCase(EmbeddedDocument):
    language = IntField(choices=[0, 1, 2])
    fill_in_template = StringField(db_field='fillInTemplate', max_length=16000)
    cases = ListField(EmbeddedDocumentField(ProblemCase, default=ProblemCase),
                      default=list)


class Problem(Document):
    problem_id = IntField(db_field='problemId', required=True, unique=True)
    courses = ListField(ReferenceField('Course'), default=list)
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
                                      required=True,
                                      default=ProblemTestCase,
                                      null=True)
    ac_user = IntField(db_field='ACUser', default=0)
    submitter = IntField(default=0)
    homeworks = ListField(ReferenceField('Homework'), default=list)
    contests = ListField(ReferenceField('Contest'), default=list)
    # user can view stdout/stderr
    can_view_stdout = BooleanField(db_field='canViewStdout', default=True)
    # bitmask of allowed languages (c: 1, cpp: 2, py3: 4)
    allowed_language = IntField(db_field='allowedLanguage', default=7)


class CaseResult(EmbeddedDocument):
    status = IntField(required=True)
    exec_time = IntField(required=True, db_field='execTime')
    memory_usage = IntField(required=True, db_field='memoryUsage')
    stdout = StringField(required=True)
    stderr = StringField(required=True)


class TaskResult(EmbeddedDocument):
    status = IntField(default=-1)
    exec_time = IntField(default=-1, db_field='execTime')
    memory_usage = IntField(default=-1, db_field='memoryUsage')
    score = IntField(default=0)
    cases = EmbeddedDocumentListField(CaseResult, default=list)


class Submission(Document):
    problem = ReferenceField(Problem, required=True)
    user = ReferenceField(User, required=True)
    language = IntField(required=True, db_field='languageType')
    timestamp = DateTimeField(required=True)
    status = IntField(default=-2)
    score = IntField(default=0)
    tasks = EmbeddedDocumentListField(TaskResult, default=list)
    exec_time = IntField(default=-1, db_field='runTime')
    memory_usage = IntField(default=-1, db_field='memoryUsage')
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


class Announcement(Document):
    status = IntField(default=0, choices=[0, 1])  # not delete / delete
    title = StringField(max_length=64, required=True)
    course = ReferenceField('Course', required=True)
    create_time = DateTimeField(db_field='createTime', default=datetime.utcnow)
    update_time = DateTimeField(db_field='updateTime', default=datetime.utcnow)
    creator = ReferenceField('User', required=True)
    updater = ReferenceField('User', required=True)
    markdown = StringField(max_length=100000, required=True)


class PostThread(Document):
    markdown = StringField(default='', required=True, max_length=100000)
    author = ReferenceField('User', db_field='author')
    course_id = ReferenceField('Course', db_field='courseId')
    depth = IntField(default=0)  # 0 is top post, 1 is reply to post
    created = DateTimeField(required=True)
    updated = DateTimeField(required=True)
    status = IntField(default=0, choices=[0, 1])  # not delete / delete
    reply = ListField(ReferenceField('PostThread', db_field='postThread'),
                      dafault=list)


class Post(Document):
    post_name = StringField(default='', required=True, max_length=64)
    thread = ReferenceField('PostThread', db_field='postThread')
