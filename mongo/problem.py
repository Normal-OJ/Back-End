from . import engine
from .base import MongoBase
from .course import *
from .utils import can_view_problem
from zipfile import ZipFile
from datetime import datetime
import json

__all__ = [
    'Problem',
    'BadTestCase',
    'get_problem_list',
    'add_problem',
    'edit_problem',
    'edit_problem_test_case',
    'delete_problem',
    'copy_problem',
    'release_problem',
]


def serial_number():
    try:
        number = engine.Number.objects(name='serial_number').get()
    except engine.DoesNotExist:
        number = engine.Number(name='serial_number')
        number.save()
    return number


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

    def detailed_info(self, *ks, **kns):
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

    def submit_count(self, user):
        # reset quota if it's a new day
        if user.last_submit.date() != datetime.now().date():
            user.update(problem_submission={})
            return 0
        return user.problem_submission.get(str(self.problem_id), 0)


def increased_number():
    serial_number().update(inc__number=1)


def get_problem_list(
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


def add_problem(
    user,
    courses,
    status,
    problem_name,
    description,
    tags,
    type,
    test_case_info=None,
    can_view_stdout=False,
    allowed_language=7,
    quota=-1,
):
    problem_id = serial_number().number
    course_objs = []
    for name in courses:
        if Course(name).obj is None:
            raise engine.DoesNotExist
        course_objs.append(Course(name).obj)
    problem = engine.Problem(
        problem_id=problem_id,
        courses=course_objs,
        problem_status=status,
        problem_type=type,
        problem_name=problem_name,
        description=description,
        owner=user.username,
        tags=tags,
        quota=quota,
    )
    problem.save()
    if type != 2:
        problem.update(
            test_case=test_case_info,
            can_view_stdout=can_view_stdout,
            allowed_language=allowed_language,
        )
    increased_number()
    return problem_id


def edit_problem(
    user,
    problem_id,
    courses,
    status,
    problem_name,
    description,
    tags,
    type,
    test_case_info=None,
    allowed_language=7,
    can_view_stdout=False,
    quota=-1,
):
    problem = Problem(problem_id).obj
    course_objs = []
    for name in courses:
        if (course := Course(name).obj) is None:
            raise engine.DoesNotExist
        course_objs.append(course)
    problem.update(
        courses=course_objs,
        problem_status=status,
        problem_type=type,
        problem_name=problem_name,
        description=description,
        owner=user.username,
        tags=tags,
        quota=quota,
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


def edit_problem_test_case(problem_id, test_case):
    '''
    edit problem's testcase

    Args:
        problem_id: target problem's id
        test_case: testcase zip file
    Exceptions:
        zipfile.BadZipFile: if `test_case` is not a zip file
        ValueError: if test case is None or problem_id is invalid
        engine.DoesNotExist
    Return:
        a bool denote whether the update is successful
    '''
    # query problem document
    problem = Problem(problem_id).obj
    if problem is None:
        raise engine.DoesNotExist(f'problem [{problem_id}] not exists.')
    # test case must not be None
    if test_case is None:
        raise ValueError('test case is None')
    # check file structure
    # create set of excepted filenames
    excepted_names = set()
    for i, task in enumerate(problem.test_case.tasks):
        for j in range(task.case_count):
            excepted_names.add(f'{i:02d}{j:02d}.in')
            excepted_names.add(f'{i:02d}{j:02d}.out')
    # input/output filenames
    in_out = {*ZipFile(test_case).namelist()}
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
    if problem.test_case.case_zip.grid_id is None:
        # if no, put data to a new file
        write_func = problem.test_case.case_zip.put
    else:
        # else, replace original file with a new one
        write_func = problem.test_case.case_zip.replace
    write_func(
        test_case,
        content_type='application/zip',
    )
    # update problem obj
    problem.save()
    return True


def delete_problem(problem_id):
    problem = Problem(problem_id).obj
    problem.delete()


def copy_problem(user, problem_id):
    problem = Problem(problem_id).obj
    engine.Problem(
        problem_id=serial_number().number,
        problem_status=problem.problem_status,
        problem_type=problem.problem_type,
        problem_name=problem.problem_name,
        description=problem.description,
        owner=user.username,
        tags=problem.tags,
        test_case=problem.test_case,
    ).save()
    increased_number()


def release_problem(problem_id):
    course = Course('Public').obj
    problem = Problem(problem_id).obj
    problem.courses = [course]
    problem.owner = 'first_admin'
    problem.save()
