# TODO: use **ks to simplify function definition
from . import engine
from .base import MongoBase
from .course import *
from .utils import (
    RedisCache,
    can_view_problem,
    doc_required,
    drop_none,
)
from .user import User
from zipfile import ZipFile
from datetime import datetime
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
import json
import zipfile

__all__ = [
    'Problem',
    'BadTestCase',
]


class BadTestCase(Exception):

    def __init__(self, expression, extra, short):
        super().__init__(expression)
        self.extra = extra
        self.short = short

    @property
    def dict(self):
        return {
            'extra': self.extra,
            'short': self.short,
            'ERR_TYPE': 'BAD_TEST_CASE',
        }


class Problem(MongoBase, engine=engine.Problem):

    def __init__(self, problem_id):
        self.problem_id = problem_id

    def detailed_info(self, *ks, **kns) -> Dict[str, Any]:
        '''
        return detailed info about this problem. notice
        that the `input` and `output` of problem test
        case won't be sent to front end, need call other
        route to get this info.

        Args:
            ks (*str): the field name you want to get
            kns (**[str, str]):
                specify the dict key you want to store
                the data get by field name
        Return:
            a dict contains problem's data
        '''
        if not self:
            return {}
        # problem -> dict
        _ret = self.to_mongo()
        # preprocess fields
        # case zip can not be serialized
        if 'caseZip' in _ret['testCase']:
            del _ret['testCase']['caseZip']
        # convert couse document to course name
        _ret['courses'] = [course.course_name for course in self.courses]
        ret = {}
        for k in ks:
            kns[k] = k
        for k, n in kns.items():
            s_ns = n.split('__')
            # extract wanted value
            v = _ret[s_ns[0]]
            for s_n in s_ns[1:]:
                v = v[s_n]
            # extract wanted keys
            e = ret
            s_ks = k.split('__')
            for s_k in s_ks[:-1]:
                e = e.get(s_k, {s_k: {}})
            e[s_ks[-1]] = v
        return ret

    def allowed(self, language):
        if self.problem_type == 2:
            return True
        if language >= 3 or language < 0:
            return False
        return bool((1 << language) & self.allowed_language)

    def submit_count(self, user: User) -> int:
        '''
        Calculate how many submissions the user has submitted to this problem.
        '''
        # reset quota if it's a new day
        if user.last_submit.date() != datetime.now().date():
            user.update(problem_submission={})
            return 0
        return user.problem_submission.get(str(self.problem_id), 0)

    def running_homeworks(self) -> List:
        from .homework import Homework
        now = datetime.now()
        return [Homework(hw.id) for hw in self.homeworks if now in hw.duration]

    def is_valid_ip(self, ip: str):
        return all(hw.is_valid_ip(ip) for hw in self.running_homeworks())

    def get_submission_status(self) -> Dict[str, int]:
        pipeline = {
            "$group": {
                "_id": "$status",
                "count": {
                    "$sum": 1
                },
            }
        }
        cursor = engine.Submission.objects(problem=self.id).aggregate(
            [pipeline], )
        return {item['_id']: item['count'] for item in cursor}

    def get_ac_user_count(self) -> int:
        ac_users = engine.Submission.objects(
            problem=self.id,
            status=0,
        ).distinct('user')
        return len(ac_users)

    def get_tried_user_count(self) -> int:
        tried_users = engine.Submission.objects(
            problem=self.id, ).distinct('user')
        return len(tried_users)

    @doc_required('user', User)
    def high_score_key(self, user: User) -> str:
        return f'PROBLEM_{self.id}_{user.id}_HIGH_SCORE'

    @doc_required('user', User)
    def get_high_score(self, user: User) -> int:
        '''
        Get highest score for user of this problem.
        '''
        cache = RedisCache()
        key = self.high_score_key(user=user)
        if (val := cache.get(key)) is not None:
            return int(val.decode())
        # TODO: avoid calling mongoengine API directly
        submissions = engine.Submission.objects(
            user=user.id,
            problem=self.id,
        ).only('score').order_by('-score').limit(1)
        if submissions.count() == 0:
            high_score = 0
        else:
            # It might < 0 if there is only incomplete submission
            high_score = max(submissions[0].score, 0)
        cache.set(key, high_score, ex=600)
        return high_score

    # TODO: Provide a general interface to test permission
    @doc_required('user', User)
    def check_manage_permission(self, user: User) -> bool:
        '''
        Check whether a user is permmited to call manage API
        '''
        # Admin
        if user.role == 0:
            return True
        # Student
        if user.role == 2:
            return False
        # Teacher && is owner
        return self.owner == user.username

    @classmethod
    def get_problem_list(
        cls,
        user,
        offset: int = 0,
        count: int = -1,
        problem_id: int = None,
        name: str = None,
        tags: list = None,
        course: str = None,
    ):
        '''
        get a list of problems
        '''
        if course is not None:
            course = Course(course).obj
            if course is None:
                return []
        # qurey args
        ks = {
            'problem_id': problem_id,
            'problem_name': name,
            'courses': course,
            'tags__in': tags,
        }
        ks = {k: v for k, v in ks.items() if v is not None}
        problems = engine.Problem.objects(**ks).order_by('problemId')
        problems = [p for p in problems if can_view_problem(user, p)]
        # truncate
        if offset < 0 or (offset >= len(problems) and len(problems)):
            raise IndexError
        right = len(problems) if count < 0 else offset + count
        right = min(len(problems), right)
        return problems[offset:right]

    @classmethod
    def add(
        cls,
        user: User,
        courses: List[str],
        problem_name: str,
        status: Optional[int] = None,
        description: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        type: Optional[int] = None,
        test_case_info: Optional[Dict[str, Any]] = None,
        can_view_stdout: bool = False,
        allowed_language: Optional[int] = None,
        quota: Optional[int] = None,
        default_code: Optional[str] = None,
    ):
        if len(courses) == 0:
            raise ValueError('No course provided')
        course_objs = []
        for course in map(Course, courses):
            if not course:
                raise engine.DoesNotExist
            course_objs.append(course.id)
        problem_args = drop_none({
            'courses': course_objs,
            'problem_status': status,
            'problem_type': type,
            'problem_name': problem_name,
            'description': description,
            'owner': user.username,
            'tags': tags,
            'quota': quota,
            'default_code': default_code,
        })
        problem = cls.engine(**problem_args).save()
        programming_problem_args = drop_none({
            'test_case':
            test_case_info,
            'can_view_stdout':
            can_view_stdout,
            'allowed_language':
            allowed_language,
        })
        if programming_problem_args and type != 2:
            problem.update(**programming_problem_args)
        return problem.problem_id

    @classmethod
    def edit_problem(
        cls,
        user: User,
        problem_id: int,
        courses: List[str],
        status: int,
        problem_name: str,
        description: Dict[str, Any],
        tags: List[str],
        type,
        test_case_info: Dict[str, Any] = None,
        allowed_language: int = 7,
        can_view_stdout: bool = False,
        quota: int = -1,
        default_code: str = '',
    ):
        if type != 2:
            score = sum(t['taskScore'] for t in test_case_info['tasks'])
            if score != 100:
                raise ValueError("Cases' scores should be 100 in total")
        problem = Problem(problem_id).obj
        course_objs = []
        for name in courses:
            if not (course := Course(name)):
                raise engine.DoesNotExist
            course_objs.append(course.obj)
        problem.update(
            courses=course_objs,
            problem_status=status,
            problem_type=type,
            problem_name=problem_name,
            description=description,
            owner=user.username,
            tags=tags,
            quota=quota,
            default_code=default_code,
        )
        if type != 2:
            # preprocess test case
            test_case = problem.test_case
            if test_case_info:
                test_case = engine.ProblemTestCase.from_json(
                    json.dumps(test_case_info))
                test_case.case_zip = problem.test_case.case_zip
            problem.update(
                allowed_language=allowed_language,
                can_view_stdout=can_view_stdout,
                test_case=test_case,
            )

    def update_testcase(self, test_case):
        '''
        edit problem's testcase

        Args:
            test_case: testcase zip file
        Exceptions:
            zipfile.BadZipFile: if `test_case` is not a zip file
            ValueError: if test case is None or problem_id is invalid
            engine.DoesNotExist
        '''
        # test case must not be None
        if test_case is None:
            raise ValueError('test case is None')
        # check file structure
        # create set of excepted filenames
        excepted_names = set()
        for i, task in enumerate(self.test_case.tasks):
            for j in range(task.case_count):
                excepted_names.add(f'{i:02d}{j:02d}.in')
                excepted_names.add(f'{i:02d}{j:02d}.out')
        # check chaos folder
        chaos_path = zipfile.Path(test_case, at='chaos')
        if chaos_path.exists() and chaos_path.is_file():
            raise BadTestCase('find chaos, but it\'s not a directory')
        # input/output filenames
        in_out = {
            name
            for name in ZipFile(test_case).namelist()
            if not name.startswith('chaos')
        }
        # check diff
        ex = in_out - excepted_names
        sh = excepted_names - in_out
        if len(ex) or len(sh):
            raise BadTestCase(
                'io data not equal to meta provided',
                [*ex],
                [*sh],
            )
        # save zip file
        test_case.seek(0)
        # check whether the test case exists
        if self.test_case.case_zip.grid_id is None:
            # if no, put data to a new file
            write_func = self.test_case.case_zip.put
        else:
            # else, replace original file with a new one
            write_func = self.test_case.case_zip.replace
        write_func(
            test_case,
            content_type='application/zip',
        )
        # update problem obj
        self.save()

    @classmethod
    def copy_problem(cls, user, problem_id):
        problem = Problem(problem_id).obj
        engine.Problem(
            problem_status=problem.problem_status,
            problem_type=problem.problem_type,
            problem_name=problem.problem_name,
            description=problem.description,
            owner=user.username,
            tags=problem.tags,
            test_case=problem.test_case,
        ).save()

    @doc_required('target', Course, null=True)
    def copy_to(
        self,
        user: User,
        target: Optional[Course] = None,
        **override,
    ) -> 'Problem':
        '''
        Copy a problem to target course, hidden by default.

        Args:
            user (User): The user who execute this action and will become
                the owner of copied problem.
            target (Optional[Course] = None): The course this problem will
                be copied to, default to the first of origial courses.
            override: Override field values passed to `Problem.add`.
        '''
        target = self.courses[0] if target is None else target
        # Copied problem is hidden by default
        status = override.pop('status', Problem.engine.Visibility.HIDDEN)
        ks = dict(
            user=user,
            courses=[target.course_name],
            problem_name=self.problem_name,
            status=status,
            description=self.description.to_mongo(),
            tags=self.tags,
            type=self.problem_type,
            test_case_info=self.test_case.to_mongo(),
            can_view_stdout=self.can_view_stdout,
            allowed_language=self.allowed_language,
            quota=self.quota,
            default_code=self.default_code,
        )
        ks.update(override)
        copy = self.add(**ks)
        return copy

    @classmethod
    def release_problem(cls, problem_id):
        course = Course('Public').obj
        problem = Problem(problem_id).obj
        problem.courses = [course]
        problem.owner = 'first_admin'
        problem.save()
