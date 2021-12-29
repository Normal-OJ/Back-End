from __future__ import annotations
import json
import os
import io
import pathlib
import secrets
import logging
from typing import Optional, Union
import requests as rq
import itertools
from flask import current_app
from tempfile import NamedTemporaryFile
from datetime import date, datetime
from zipfile import ZipFile, is_zipfile

from . import engine
from .base import MongoBase
from .user import User
from .problem import Problem
from .course import Course
from .utils import RedisCache

__all__ = [
    'SubmissionConfig',
    'Submission',
    'JudgeQueueFullError',
    'TestCaseNotFound',
]

# TODO: modular token function


def gen_key(_id):
    return f'stoekn_{_id}'


def gen_token():
    return secrets.token_urlsafe()


# Errors
class JudgeQueueFullError(Exception):
    '''
    when sandbox task queue is full
    '''


class TestCaseNotFound(Exception):
    '''
    when a problem's testcase havn't been uploaded
    '''
    __test__ = False

    def __init__(self, problem_id):
        self.problem_id = problem_id

    def __str__(self):
        return f'{Problem(self.problem_id)}\'s testcase is not found'


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
    def problem_id(self) -> int:
        return self.problem.problem_id

    @property
    def username(self) -> str:
        return self.user.username

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
    def tmp_dir(self) -> pathlib.Path:
        tmp_dir = self.config().TMP_DIR / self.username / self.id
        tmp_dir.mkdir(exist_ok=True, parents=True)
        return tmp_dir

    @property
    def main_code_path(self) -> str:
        # handwritten submission didn't provide this function
        if self.handwritten:
            return
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
        return cls._config.reload()

    def get_output(self, task_no, case_no, text=True):
        try:
            case = self.tasks[task_no].cases[case_no]
        except IndexError:
            raise FileNotFoundError('task not exist')
        ret = {}
        try:
            with ZipFile(case.output) as zf:
                ret = {k: zf.read(k) for k in ('stdout', 'stderr')}
                if text:
                    ret = {k: v.decode('utf-8') for k, v in ret.items()}
        except AttributeError as e:
            raise AttributeError('The submission is still in pending')
        return ret

    def delete_output(self, *args):
        '''
        delete stdout/stderr of this submission

        Args:
            args: ignored value, don't mind
        '''
        for task in self.tasks:
            for case in task.cases:
                case.output.delete()

    def delete(self, *keeps):
        '''
        delete submission and its related file

        Args:
            keeps:
                the field name you want to keep, accepted
                value is {'comment', 'code', 'output'}
                other value will be ignored
        '''
        drops = {'comment', 'code', 'output'} - {*keeps}
        del_funcs = {
            'output': self.delete_output,
        }

        def default_del_func(d):
            return self.obj[d].delete()

        for d in drops:
            del_funcs.get(d, default_del_func)(d)
        self.obj.delete()

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

    def get_comment(self) -> bytes:
        '''
        if comment not exist
        '''
        if self.comment.grid_id is None:
            raise FileNotFoundError('it seems that comment haven\'t upload')
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
            if ext == '.pdf':
                with zf.open('main.pdf') as pdf:
                    if pdf.read(5) != b'%PDF-':
                        return 'only accept PDF file.'
        file.seek(0)
        return True

    def rejudge(self) -> bool:
        '''
        rejudge this submission
        '''
        # delete output file
        self.delete_output()
        # turn back to haven't be judged
        self.update(
            status=-1,
            last_send=datetime.now(),
            tasks=[],
        )
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
                'user': self.user,
                'language': 3,
            }
            for submission in engine.Submission.objects(**q):
                if submission != self.obj:
                    for homework in self.problem.homeworks:
                        stat = homework.student_status[self.user.username][str(
                            self.problem_id)]
                        stat['score'] = 0
                        stat['problemStatus'] = -1
                        stat['submissionIds'] = []
                        homework.save()
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
        if self.problem.test_case.case_zip is None:
            raise TestCaseNotFound(self.problem.problem_id)
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
        Submission.assign_token(self.id, tar.token)
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
        '''
        process results from sandbox

        Args:
            tasks:
                a 2-dim list of the dict with schema
                {
                    'exitCode': int,
                    'status': str,
                    'stdout': str,
                    'stderr': str,
                    'execTime': int,
                    'memoryUsage': int
                }
        '''
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
        for has_code, has_output, has_code_detail in itertools.product(
            [True, False], repeat=3):
            # iterate through True and False
            key = f'{self.id}_{has_code}_{has_output}_{has_code_detail}'
            RedisCache().delete(key)
        return True

    def finish_judging(self):
        # update user's submission
        User(self.username).add_submission(self.reload())
        # update homework data
        for homework in self.problem.homeworks:
            # if the homework is overdue, skip it
            if self.timestamp > homework.duration.end:
                continue
            stat = homework.student_status[self.username][str(self.problem_id)]
            stat['submissionIds'].append(self.id)
            # handwritten problem will only keep the last submission
            if self.handwritten:
                stat['submissionIds'] = stat['submissionIds'][-1:]
            # update high score / handwritten problem is judged by teacher
            if self.score >= stat['score'] or self.handwritten:
                stat['score'] = self.score
                stat['problemStatus'] = self.status
            homework.save()
        # update problem
        # TODO: compute ac_user count (unused now)
        # ac_submissions = Submission.filter(
        #     user=self.user,
        #     offset=0,
        #     count=-1,
        #     problem=self.problem,
        #     status=0,
        # )
        # ac_users = {s.username for s in ac_submissions}
        # self.problem.ac_user = len(ac_users)
        # update high score
        self.problem.high_scores[self.username] = engine.Submission.objects(
            user=self.user,
            problem=self.problem,
        ).only('score').order_by('-score').first().score
        self.problem.save()

    def add_comment(self, file):
        '''
        comment a submission with PDF

        Args:
            file: a PDF file
        '''
        data = file.read()
        # check magic number
        if data[:5] != b'%PDF-':
            raise ValueError('only accept PDF file.')
        # write to a new file if it did not exist before
        if self.comment.grid_id is None:
            write_func = self.comment.put
        # replace its content otherwise
        else:
            write_func = self.comment.replace
        write_func(data)
        self.logger.debug(f'{self} comment updated.')
        # update submission
        self.save()

    @staticmethod
    def count():
        return len(engine.Submission.objects)

    @staticmethod
    def filter(
        user,
        offset: int = 0,
        count: int = -1,
        problem: Optional[Union[Problem, int]] = None,
        submission: Optional[Union[Submission, str]] = None,
        q_user: Optional[Union[User, str]] = None,
        status: Optional[int] = None,
        language_type: Optional[int] = None,
        course: Optional[Union[Course, str]] = None,
        before: Optional[datetime] = None,
        after: Optional[datetime] = None,
    ):
        if before is not None and after is not None:
            if after > before:
                raise ValueError('the query period is empty')
        if offset < 0:
            raise ValueError(f'offset must >= 0!')
        if count < -1:
            raise ValueError(f'count must >=-1!')
        if isinstance(problem, int):
            problem = Problem(problem).obj
            if problem is None:
                return []
        if not isinstance(submission, (str, type(None))):
            submission = submission.id
        if isinstance(q_user, str):
            q_user = User(q_user)
            if not q_user:
                return []
            q_user = q_user.obj
        if isinstance(course, str):
            course = Course(course)
            if not course:
                return []
        # problem's query key
        p_k = 'problem'
        if course:
            problems = Problem.get_problem_list(
                user,
                course=course.course_name,
            )
            # use all problems under this course to filter
            if problem is None:
                p_k = 'problem__in'
                problem = problems
            # if problem not in course
            elif problem not in problems:
                return []
        # query args
        q = {
            p_k: problem,
            'id': submission,
            'status': status,
            'language': language_type,
            'user': q_user,
            'timestamp__lte': before,
            'timestamp__gte': after,
        }
        q = {k: v for k, v in q.items() if v is not None}
        # sort by upload time
        submissions = engine.Submission.objects(**q).order_by('-timestamp')
        # truncate
        right = min(offset + count, len(submissions))
        if count == -1:
            right = len(submissions)
        return submissions[offset:right]

    @classmethod
    def add(
        cls,
        problem_id: int,
        username: str,
        lang: int,
        timestamp: Optional[date] = None,
    ) -> 'Submission':
        '''
        Insert a new submission into db

        Returns:
            The created submission
        '''
        # check existence
        user = User(username)
        if not user:
            raise engine.DoesNotExist(f'{user} does not exist')
        problem = Problem(problem_id)
        if not problem:
            raise engine.DoesNotExist(f'{problem} dose not exist')
        if problem.test_case.case_zip is None:
            raise TestCaseNotFound(problem_id)
        if timestamp is None:
            timestamp = datetime.now()
        # create a new submission
        submission = engine.Submission(
            problem=problem.obj,
            user=user.obj,
            language=lang,
            timestamp=timestamp,
        )
        submission.save()
        return cls(submission.id)

    @classmethod
    def assign_token(cls, submission_id, token=None):
        '''
        generate a token for the submission
        '''
        if token is None:
            token = gen_token()
        RedisCache().set(gen_key(submission_id), token)
        return token

    @classmethod
    def verify_token(cls, submission_id, token):
        cache = RedisCache()
        key = gen_key(submission_id)
        s_token = cache.get(key)
        if s_token is None:
            return False
        s_token = s_token.decode('ascii')
        valid = secrets.compare_digest(s_token, token)
        if valid:
            cache.delete(key)
        return valid
