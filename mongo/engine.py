from mongoengine import *
from mongoengine import signals
import mongoengine
import os
import html
from enum import Enum, IntEnum
from datetime import datetime
from zipfile import ZipFile, BadZipFile
from .utils import perm, can_view_problem
from typing import Union
import redis
import fakeredis
import json

__all__ = [*mongoengine.__all__]

MONGO_HOST = os.environ.get('MONGO_HOST', 'mongomock://localhost')
REDIS_POOL = redis.ConnectionPool(
    host=os.getenv('REDIS_HOST'),
    port=os.getenv('REDIS_PORT'),
    db=0,
)
connect('normal-oj', host=MONGO_HOST)
REDIS_CLIENT = redis.Redis(connection_pool=REDIS_POOL)
if os.getenv('REDIS_HOST') is None:
    REDIS_CLIENT = fakeredis.FakeStrictRedis()


def handler(event):
    '''
    Signal decorator to allow use of callback functions as class decorators.
    reference: http://docs.mongoengine.org/guide/signals.html
    '''
    def decorator(fn):
        def apply(cls):
            event.connect(fn, sender=cls)
            return cls

        fn.apply = apply
        return fn

    return decorator


@handler(signals.pre_save)
def escape_markdown(sender, document):
    document.markdown = html.escape(document.markdown)


class ZipField(FileField):
    def __init__(self, max_size=0, **ks):
        super().__init__(**ks)
        self.max_size = max_size

    def validate(self, value):
        super().validate(value)
        # skip check
        if not value:
            return
        try:
            with ZipFile(value) as zf:
                # the size of original files
                size = sum(info.file_size for info in zf.infolist())
        except BadZipFile:
            self.error('Only accept zip file.')
        # no limit
        if self.max_size <= 0:
            return
        if size > self.max_size:
            self.error(
                f'{size} bytes exceed the max size limit ({self.max_size} bytes)'
            )


class IntEnumField(IntField):
    def __init__(self, enum: IntEnum, **ks):
        super().__init__(**ks)
        self.enum = enum

    def validate(self, value):
        choices = (*self.enum.__members__.values(), )
        if value not in choices:
            self.error(f'Value must be one of {choices}')


class Profile(EmbeddedDocument):
    displayed_name = StringField(
        db_field='displayedName',
        default='',
        max_length=16,
    )
    bio = StringField(
        max_length=64,
        required=True,
        default='',
    )


class EditorConfig(EmbeddedDocument):
    font_size = IntField(db_field='fontSize',
                         min_value=8,
                         max_value=72,
                         default=14)
    theme = StringField(
        default='default',
        choices=[
            "default", "base16-dark", "base16-light", "dracula", "eclipse",
            "material", "monokai"
        ],
    )
    indent_type = IntField(db_field='indentType', default=1, choices=[0, 1])
    tab_size = IntField(
        db_field='tabSize',
        default=4,
        min_value=1,
        max_value=8,
    )
    language = IntField(
        default=0,
        choices=[0, 1, 2],
    )


class Duration(EmbeddedDocument):
    start = DateTimeField(default=datetime.now)
    end = DateTimeField(default=datetime.max)

    def __contains__(self, other) -> bool:
        if not isinstance(other, datetime):
            return False
        return self.start <= other <= self.end


class User(Document):
    class Role(IntEnum):
        ADMIN = 0
        TEACHER = 1
        STUDENT = 2

    username = StringField(max_length=16, required=True, primary_key=True)
    user_id = StringField(db_field='userId', max_length=24, required=True)
    user_id2 = StringField(db_field='userId2', max_length=24, default='')
    email = EmailField(required=True, unique=True, max_length=128)
    md5 = StringField(required=True, max_length=32)
    active = BooleanField(default=False)
    role = IntEnumField(default=Role.STUDENT, enum=Role)
    profile = EmbeddedDocumentField(Profile, default=Profile)
    editor_config = EmbeddedDocumentField(
        EditorConfig,
        db_field='editorConfig',
        default=EditorConfig,
        null=True,
    )
    contest = ReferenceField('Contest', db_field='contestId')
    courses = ListField(ReferenceField('Course'))
    submissions = ListField(ReferenceField('Submission'))
    last_submit = DateTimeField(default=datetime.min)
    AC_problem_ids = ListField(IntField(), default=list)
    AC_submission = IntField(default=0)
    submission = IntField(default=0)
    problem_submission = DictField(db_field='problemSubmission')

    @property
    def info(self):
        return {
            'username': self.username,
            'displayedName': self.profile.displayed_name,
            'md5': self.md5,
        }


@escape_markdown.apply
class Homework(Document):
    homework_name = StringField(
        max_length=64,
        required=True,
        db_field='homeworkName',
        unique_with='course_id',
    )
    markdown = StringField(max_length=10000, default='')
    scoreboard_status = IntField(
        default=0,
        choices=[0, 1],
        db_field='scoreboardStatus',
    )
    course_id = StringField(required=True, db_field='courseId')
    duration = EmbeddedDocumentField(Duration, default=Duration)
    problem_ids = ListField(IntField(), db_field='problemIds')
    student_status = DictField(db_field='studentStatus')
    ip_filters = ListField(StringField(max_length=64), default=list)


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
    course_name = StringField(
        max_length=64,
        required=True,
        unique=True,
        db_field='courseName',
    )
    student_nicknames = DictField(db_field='studentNicknames')
    course_status = IntField(default=0, choices=[0, 1])
    teacher = ReferenceField('User')
    tas = ListField(ReferenceField('User'))
    contests = ListField(ReferenceField('Contest', reverse_delete_rule=PULL))
    homeworks = ListField(ReferenceField('Homework', reverse_delete_rule=PULL))
    announcements = ListField(ReferenceField('Announcement'))
    posts = ListField(ReferenceField('Post'), default=list)
    student_scores = DictField(db_field='studentScores')


class Number(Document):
    name = StringField(
        max_length=64,
        primary_key=True,
    )
    number = IntField(default=1)


class ProblemCase(EmbeddedDocument):
    task_score = IntField(required=True, db_field='taskScore')
    case_count = IntField(required=True, db_field='caseCount')
    memory_limit = IntField(required=True, db_field='memoryLimit')
    time_limit = IntField(required=True, db_field='timeLimit')


class ProblemTestCase(EmbeddedDocument):
    language = IntField(choices=[0, 1, 2])
    fill_in_template = StringField(db_field='fillInTemplate', max_length=16000)
    tasks = EmbeddedDocumentListField(
        ProblemCase,
        default=list,
    )
    # zip file contains testcase input/output
    case_zip = ZipField(
        db_field='caseZip',
        defautl=None,
        null=True,
    )


class ProblemDescription(EmbeddedDocument):
    description = StringField(max_length=100000)
    input = StringField(max_length=100000)
    output = StringField(max_length=100000)
    hint = StringField(max_length=100000)
    sample_input = ListField(
        StringField(max_length=1024),
        default=list,
        db_field='sampleInput',
    )
    sample_output = ListField(
        StringField(max_length=1024),
        default=list,
        db_field='sampleOutput',
    )

    def escape(self):
        self.description, self.input, self.output, self.hint = (
            v or html.escape(v) for v in (
                self.description,
                self.input,
                self.output,
                self.hint,
            ))
        _io = zip(self.sample_input, self.sample_output)
        for i, (ip, op) in enumerate(_io):
            self.sample_input[i] = ip or html.escape(ip)
            self.sample_output[i] = op or html.escape(op)


@handler(signals.pre_save)
def problem_desc_escape(sender, document):
    document.description.escape()


@problem_desc_escape.apply
class Problem(Document):
    problem_id = IntField(
        db_field='problemId',
        required=True,
        primary_key=True,
    )
    courses = ListField(ReferenceField('Course'), default=list)
    problem_status = IntField(
        default=1,
        choices=[0, 1],
        db_field='problemStatus',
    )
    problem_type = IntField(
        default=0,
        choices=[0, 1, 2],
        db_field='problemType',
    )
    problem_name = StringField(
        db_field='problemName',
        max_length=64,
        required=True,
    )
    description = EmbeddedDocumentField(
        ProblemDescription,
        default=ProblemDescription,
    )
    owner = StringField(max_length=16, required=True)
    # pdf =
    tags = ListField(StringField(max_length=16))
    test_case = EmbeddedDocumentField(
        ProblemTestCase,
        db_field='testCase',
        default=ProblemTestCase,
    )
    ac_user = IntField(db_field='ACUser', default=0)
    submitter = IntField(default=0)
    homeworks = ListField(ReferenceField('Homework'), default=list)
    contests = ListField(ReferenceField('Contest'), default=list)
    # user can view stdout/stderr
    can_view_stdout = BooleanField(db_field='canViewStdout', default=True)
    cpp_report_url = StringField(
        db_field='cppReportUrl',
        default='',
        max_length=128,
    )
    python_report_url = StringField(
        db_field='pythonReportUrl',
        default='',
        max_length=128,
    )
    # bitmask of allowed languages (c: 1, cpp: 2, py3: 4)
    allowed_language = IntField(db_field='allowedLanguage', default=7)
    # high score for each student
    # Dict[username, score]
    high_scores = DictField(db_field='highScore', default={})
    quota = IntField(default=-1)
    default_code = StringField(
        db_field='defaultCode',
        max_length=10**4,
        default='',
    )


class CaseResult(EmbeddedDocument):
    status = IntField(required=True)
    exec_time = IntField(required=True, db_field='execTime')
    memory_usage = IntField(required=True, db_field='memoryUsage')
    output = ZipField(
        required=True,
        null=True,
        max_size=11**9,
    )


class TaskResult(EmbeddedDocument):
    status = IntField(default=-1)
    exec_time = IntField(default=-1, db_field='execTime')
    memory_usage = IntField(default=-1, db_field='memoryUsage')
    score = IntField(default=0)
    cases = EmbeddedDocumentListField(CaseResult, default=list)


class Submission(Document):
    meta = {
        'indexes': [(
            'timestamp',
            'user',
            'language',
            'status',
            'score',
        )]
    }
    problem = ReferenceField(Problem, required=True)
    user = ReferenceField(User, required=True)
    language = IntField(
        required=True,
        min_value=0,
        max_value=3,
        db_field='languageType',
    )
    timestamp = DateTimeField(required=True)
    status = IntField(default=-2)
    score = IntField(default=-1)
    tasks = EmbeddedDocumentListField(TaskResult, default=list)
    exec_time = IntField(default=-1, db_field='runTime')
    memory_usage = IntField(default=-1, db_field='memoryUsage')
    code = ZipField(required=True, null=True, max_size=10**7)
    last_send = DateTimeField(db_field='lastSend', default=datetime.now)
    comment = FileField(default=None, null=True)

    def permission(self, user):
        '''
        3: can rejudge & grade, 
        2: can view upload & comment, 
        1: can view basic info, 
        0: can't view
        '''
        if not can_view_problem(user, self.problem):
            return 0

        return 3 - [
            max(perm(course, user) for course in self.problem.courses) >= 2,
            user.username == self.user.username,
            True,
        ].index(True)

    def to_dict(self, has_code=False, has_output=False, has_code_detail=False):
        key = f'{self.id}_{has_code}_{has_output}_{has_code_detail}'
        if REDIS_CLIENT.exists(key):
            return json.loads(REDIS_CLIENT.get(key))

        _ret = {
            'problemId': self.problem.problem_id,
            'user': self.user.info,
            'submissionId': str(self.id),
            'timestamp': self.timestamp.timestamp(),
            'lastSend': self.last_send.timestamp()
        }
        if has_code:
            if has_code_detail:
                # give user source code
                ext = ['.c', '.cpp', '.py'][self.language]
                _ret['code'] = self.get_code(f'main{ext}')
            else:
                _ret['code'] = False

        ret = self.to_mongo()
        old = [
            '_id',
            'problem',
            'code',
            'comment',
        ]
        # delete old keys
        for o in old:
            del ret[o]
        # insert new keys
        for n in _ret:
            ret[n] = _ret[n]
        if has_output:
            for task in ret['tasks']:
                for case in task['cases']:
                    # extract zip file
                    output = GridFSProxy(case.pop('output'))
                    if output is not None:
                        with ZipFile(output) as zf:
                            case['stdout'] = zf.read('stdout').decode('utf-8')
                            case['stderr'] = zf.read('stderr').decode('utf-8')
        else:
            for task in ret['tasks']:
                for case in task['cases']:
                    del case['output']

        REDIS_CLIENT.set(key, json.dumps(ret), 60)
        return ret

    @property
    def handwritten(self):
        return self.language == 3

    def get_code(self, path: str, binary=False) -> Union[str, bytes]:
        # read file
        try:
            with ZipFile(self.code) as zf:
                data = zf.read(path)
        # file not exists in the zip or code haven't been uploaded
        except (KeyError, AttributeError):
            return None
        # decode byte if need
        if not binary:
            try:
                data = data.decode('utf-8')
            except UnicodeDecodeError:
                data = 'Unusual file content, decode fail'
        return data


@escape_markdown.apply
class Message(Document):
    timestamp = DateTimeField(default=datetime.now)
    sender = StringField(max_length=16, required=True)
    receivers = ListField(StringField(max_length=16), required=True)
    status = IntField(default=0, choices=[0, 1])  # not delete / delete
    title = StringField(max_length=32, required=True)
    markdown = StringField(max_length=100000, required=True)


class Inbox(Document):
    receiver = StringField(max_length=16, required=True)
    status = IntField(default=0, choices=[0, 1, 2])  # unread / read / delete
    message = ReferenceField('Message')


@escape_markdown.apply
class Announcement(Document):
    status = IntField(default=0, choices=[0, 1])  # not delete / delete
    title = StringField(max_length=64, required=True)
    course = ReferenceField('Course', required=True)
    create_time = DateTimeField(db_field='createTime', default=datetime.now)
    update_time = DateTimeField(db_field='updateTime', default=datetime.now)
    creator = ReferenceField('User', required=True)
    updater = ReferenceField('User', required=True)
    markdown = StringField(max_length=100000, required=True)
    pinned = BooleanField(default=False)


@escape_markdown.apply
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


class Config(Document):
    meta = {
        'allow_inheritance': True,
    }
    name = StringField(required=True, max_length=64, primary_key=True)


class Sandbox(EmbeddedDocument):
    name = StringField(required=True)
    url = StringField(required=True)
    token = StringField(required=True)


class SubmissionConfig(Config):
    rate_limit = IntField(default=0, db_field='rateLimit')
    sandbox_instances = EmbeddedDocumentListField(
        Sandbox,
        default=[
            Sandbox(
                name='Sandbox-0',
                url='http://sandbox:1450',
                token='KoNoSandboxDa',
            ),
        ],
        db_field='sandboxInstances',
    )
