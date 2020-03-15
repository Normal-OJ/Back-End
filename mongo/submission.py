import json
import os
import io
import pathlib
import secrets
import logging
import requests as rq
from flask import current_app
from tempfile import NamedTemporaryFile
from datetime import date, datetime
from typing import List, Union
from zipfile import ZipFile, is_zipfile

from . import engine
from .base import MongoBase
from .user import User
from .problem import Problem, can_view, get_problem_list
from .course import Course, perm

__all__ = [
    'SubmissionConfig',
    'Submission',
    'gen_token',
    'assign_token',
    'verify_token',
    'JudgeQueueFullError',
]

# TODO: save tokens in db
tokens = {}


def gen_token():
    return secrets.token_urlsafe()


def assign_token(submission_id, token=None):
    '''
    generate a token for the submission
    '''
    tokens[submission_id] = token or gen_token()
    return token


def verify_token(submission_id, token):
    if submission_id not in tokens:
        return False
    return secrets.compare_digest(tokens[submission_id], token)


# Errors
class JudgeQueueFullError(Exception):
    '''
    when sandbox task queue is full
    '''


class SubmissionConfig(MongoBase, engine=engine.SubmissionConfig):
    TMP_DIR = pathlib.Path(
        os.getenv(
            'SUBMISSION_TMP_DIR',
            '/tmp/submissions',
        ), )

    def __new__(cls, *args, **ks):
        cls.TMP_DIR.mkdir(exist_ok=True)
        return super().__new__(cls, *args, **ks)

    def __init__(self, name):
        self.name = name


class Submission(MongoBase, engine=engine.Submission):
    _config = None

    def __init__(self, submission_id):
        self.submission_id = str(submission_id)

    def __str__(self):
        return f'submission [{self.submission_id}]'

    @property
    def id(self):
        '''
        convert mongo ObjectId to hex string for serialize
        '''
        return str(self.obj.id)

    @property
    def problem_id(self):
        return self.problem.problem_id

    def to_dict(self):
        _ret = {
            'problemId': self.problem_id,
            'user': User(self.user.username).info,
            'submissionId': self.id,
            'timestamp': self.timestamp.timestamp(),
            'code': bool(self.code),
        }
        ret = self.to_mongo()
        old = [
            '_id',
            'problem',
            'code',
        ]
        # delete old keys
        for o in old:
            del ret[o]
        # insert new keys
        for n in _ret:
            ret[n] = _ret[n]
        return ret

    @property
    def status2code(self):
        return {
            'AC': 0,
            'WA': 1,
            'CE': 2,
            'TLE': 3,
            'MLE': 4,
            'RE': 5,
            'JE': 6,
            'OLE': 7,
        }

    @property
    def handwritten(self):
        return self.language == 3

    @property
    def tmp_dir(self) -> pathlib.Path:
        return self.config().TMP_DIR / self.id

    @property
    def main_code_path(self) -> str:
        # get excepted code name & temp path
        lang2ext = {0: '.c', 1: '.cpp', 2: '.py'}
        ext = lang2ext[self.language]
        path = self.tmp_dir / f'main{ext}'
        # check whether the code has been generated
        if not path.exists():
            with ZipFile(self.code) as zf:
                path.write_text(zf.read(f'main{ext}').decode('utf-8'))
        # return absolute path
        return str(path.absolute())

    @property
    def logger(self):
        try:
            return current_app.logger
        except RuntimeError:
            return logging.getLogger('gunicorn.error')

    @classmethod
    def config(cls):
        if not cls._config:
            cls._config = SubmissionConfig('submission')
        if not cls._config:
            cls._config.save()
        cls._config.reload()
        return cls._config

    def permission(self, user):
        '''
        4: can rejudge & grade, 
        3: can view upload & comment, 
        2: can view score, 
        1: can view basic info, 
        0: can't view
        '''
        if not can_view(user, self.problem):
            return 0

        return 3 - [
            max(perm(course, user) for course in self.problem.courses) >= 2,
            user.username == self.user.username, True
        ].index(True)

    def sandbox_resp_handler(self, resp):
        # judge queue is currently full
        def on_500(resp):
            raise JudgeQueueFullError

        # backend send some invalid data
        def on_400(resp):
            raise ValueError(resp.text)

        # send a invalid token
        def on_403(resp):
            raise ValueError('invalid token')

        h = {
            500: on_500,
            403: on_403,
            400: on_400,
            200: lambda r: True,
        }
        try:
            return h[resp.status_code](resp)
        except KeyError:
            self.logger.error('can not handle response from sandbox')
            self.logger.error(
                f'status code: {resp.status_code}\n'
                f'headers: {resp.headers}\n'
                f'body: {resp.text}', )
            return False

    def target_sandbox(self):
        load = 10**3  # current min load
        tar = None  # target
        for sb in self.config().sandbox_instances:
            resp = rq.get(f'{sb.url}/status')
            if not resp.ok:
                self.logger.warning(f'sandbox {sb.name} status exception')
                self.logger.warning(
                    f'status code: {resp.status_code}\n '
                    f'body: {resp.text}', )
                continue
            resp = resp.json()
            if resp['load'] < load:
                load = resp['load']
                tar = sb
        return tar

    def get_code(self, path: str, binary=False) -> Union[str, bytes]:
        # read file
        try:
            with ZipFile(self.code) as zf:
                data = zf.read(path)
        except KeyError:
            # file not exists in the zip
            return None
        except AttributeError:
            # code haven't been uploaded
            return None
        # decode byte if need
        if not binary:
            try:
                data = data.decode('utf-8')
            except UnicodeDecodeError:
                data = 'Unusual file content, decode fail'
        return data

    def get_comment(self) -> bytes:
        return self.comment.read()

    def check_code(self, file):
        if not file:
            return 'no file'
        if not is_zipfile(file):
            return 'not a valid zip file'
        with ZipFile(file) as zf:
            infos = zf.infolist()
            if len(infos) != 1:
                return 'more than one file in zip'
            name, ext = os.path.splitext(infos[0].filename)
            if name != 'main':
                return 'only accept file with name \'main\''
            if ext != ['.c', '.cpp', '.py', '.pdf'][self.language]:
                return f'invalid file extension, got {ext}'
        file.seek(0)
        return True

    def rejudge(self) -> bool:
        '''
        rejudge this submission
        '''
        # delete result
        for task_result in self.tasks:
            for case_result in task_result:
                case_result.output.delete()
                case_result.save()

        # turn back to haven't be judged
        self.update(status=-1, last_send=datetime.now(), tasks=[])
        if current_app.config['TESTING']:
            return True
        return self.send()

    def submit(self, code_file) -> bool:
        '''
        prepara data for submit code to sandbox and then send it

        Args:
            code_file: a zip file contains user's code
        '''
        # unexisted id
        if not self:
            raise engine.DoesNotExist(f'{self}')
        # save source
        res = self.check_code(code_file)
        if res is not True:
            raise ValueError(res)
        self.code.put(code_file)
        self.update(status=-1, last_send=datetime.now())
        self.save()
        self.reload()
        self.logger.debug(f'{self} code updated.')
        # delete old handwritten submission
        if self.handwritten:
            q = {
                'problem': self.problem,
                'score': -1,
                'user': self.user,
                'language': 3,
            }
            for submission in engine.Submission.objects(**q):
                if submission != self.obj:
                    submission.delete()
        # we no need to actually send code to sandbox during testing
        if current_app.config['TESTING'] or self.handwritten:
            return True
        return self.send()

    def send(self) -> bool:
        '''
        send code to sandbox
        '''
        if self.handwritten:
            logging.warning(f'try to send a handwritten {self}')
            return False
        # metadata
        meta = {
            'language':
            self.language,
            'tasks': [
                json.loads(task.to_json())
                for task in self.problem.test_case.tasks
            ],
        }
        self.logger.debug(f'meta: {meta}')
        # setup post body
        files = {
            'src': (
                f'{self.id}-source.zip',
                self.code,
            ),
            'testcase': (
                f'{self.id}-testcase.zip',
                self.problem.test_case.case_zip,
            ),
            'meta.json': (
                f'{self.id}-meta.json',
                io.StringIO(json.dumps(meta)),
            ),
        }
        # look for the target sandbox
        tar = self.target_sandbox()
        if tar is None:
            self.logger.error(f'can not target a sandbox for {repr(self)}')
            return False
        # save token for validation
        assign_token(self.id, tar.token)
        post_data = {
            'token': tar.token,
            'checker': 'print("not implement yet. qaq")',
        }
        judge_url = f'{tar.url}/submit/{self.id}'
        # send submission to snadbox for judgement
        self.logger.info(f'send {self} to {tar.name}')
        resp = rq.post(
            judge_url,
            data=post_data,
            files=files,
        )
        self.logger.info(f'recieve {self} resp from sandbox')
        return self.sandbox_resp_handler(resp)

    def process_result(self, tasks: list):
        self.logger.info(f'recieve {self} result')
        for task in tasks:
            for case in task:
                # we don't need exit code
                del case['exitCode']
                # convert status into integer
                case['status'] = self.status2code.get(case['status'], -3)
        # process task
        for i, cases in enumerate(tasks):
            # save stdout/stderr
            fds = ['stdout', 'stderr']
            for j, case in enumerate(cases):
                tf = NamedTemporaryFile(delete=False)
                with ZipFile(tf, 'w') as zf:
                    for fd in fds:
                        content = case.pop(fd)
                        if content is None:
                            self.logger.error(
                                f'key {fd} not in case result {self} {i:02d}{j:02d}'
                            )
                        zf.writestr(fd, content)
                tf.seek(0)
                case['output'] = tf
                # convert dict to document
                cases[j] = engine.CaseResult(
                    status=case['status'],
                    exec_time=case['execTime'],
                    memory_usage=case['memoryUsage'],
                    output=case['output'],
                )
            status = max(c.status for c in cases)
            exec_time = max(c.exec_time for c in cases)
            memory_usage = max(c.memory_usage for c in cases)
            tasks[i] = engine.TaskResult(
                status=status,
                exec_time=exec_time,
                memory_usage=memory_usage,
                score=self.problem.test_case.tasks[i].task_score
                if status == 0 else 0,
                cases=cases,
            )
        status = max(t.status for t in tasks)
        exec_time = max(t.exec_time for t in tasks)
        memory_usage = max(t.memory_usage for t in tasks)
        self.update(
            score=sum(task.score for task in tasks),
            status=status,
            tasks=tasks,
            exec_time=exec_time,
            memory_usage=memory_usage,
        )
        self.finish_judging()

        return True

    def finish_judging(self):
        # update user's submission
        User(self.user.username).add_submission(self.reload())
        # update homework data
        for homework in self.problem.homeworks:
            stat = homework.student_status[self.user.username][str(
                self.problem_id)]
            stat['submissionIds'].append(self.id)
            if self.score >= stat['score']:
                stat['score'] = self.score
                stat['problemStatus'] = self.status
            homework.save()
        # update problem
        ac_submissions = Submission.filter(
            user=self.user,
            offset=0,
            count=-1,
            problem=self.problem,
            status=0,
        )
        ac_users = {s.user.username for s in ac_submissions}
        self.problem.ac_user = len(ac_users)
        self.problem.save()

    def add_comment(self, file):
        '''
        comment a submission with PDF

        Args:
            file: a PDF file
        '''
        data = file.read()
        if data[1:4] != b'PDF':
            raise ValueError('only accept PDF file.')
        self.comment.put(data)
        self.logger.debug(f'{self} comment updated.')

    @staticmethod
    def count():
        return len(engine.Submission.objects)

    @staticmethod
    def filter(
        user,
        offset,
        count,
        problem=None,
        submission=None,
        q_user=None,
        status=None,
        language_type=None,
        course=None,
    ):
        # convert args
        if offset is None or count is None:
            raise ValueError('offset and count are required!')
        try:
            offset = int(offset)
            count = int(count)
        except ValueError:
            raise ValueError('offset and count must be integer!')
        if offset < 0:
            raise ValueError(f'offset must >= 0! get {offset}')
        if count < -1:
            raise ValueError(f'count must >=-1! get {count}')
        if not isinstance(problem, engine.Problem) and problem is not None:
            try:
                problem = Problem(int(problem)).obj
            except ValueError:
                raise ValueError(f'can not convert {type(problem)} into int')
            if problem is None:
                return []
        if isinstance(submission, (Submission, engine.Submission)):
            submission = submission.id
        if isinstance(q_user, str):
            q_user = User(q_user)
            # if not exist
            if not q_user:
                return []
            q_user = q_user.obj
        if isinstance(course, str):
            course = Course(course).obj
            if course is None:
                return []
        p_k = 'problem'
        # if problem not in course
        if course:
            problems = get_problem_list(user, course=course.course_name)
            if problem is None:
                p_k = 'problem__in'
                problem = problems
            elif problem not in problems:
                return []
        # query args
        q = {
            p_k: problem,
            'id': submission,
            'status': status,
            'language': language_type,
            'user': q_user,
        }
        q = {k: v for k, v in q.items() if v is not None}
        # sort by upload time
        submissions = engine.Submission.objects(**q).order_by('-timestamp')
        # truncate
        if offset >= len(submissions) and len(submissions):
            raise ValueError(f'offset ({offset}) is out of range!')
        right = min(offset + count, len(submissions))
        if count == -1:
            right = len(submissions)
        return submissions[offset:right]

    @classmethod
    def add(
            cls,
            problem_id: str,
            username: str,
            lang: int,
            timestamp: date,
    ) -> 'Submission':
        '''
        Insert a new submission into db

        Returns:
            The created submission
        '''
        user = User(username)
        if not user:
            raise engine.DoesNotExist(f'user {username} does not exist')

        problem = Problem(problem_id)
        if problem.obj is None:
            raise engine.DoesNotExist(f'problem {problem_id} dose not exist')

        submission = engine.Submission(
            problem=problem.obj,
            user=user.obj,
            language=lang,
            timestamp=timestamp,
        )
        submission.save()

        return cls(submission.id)
