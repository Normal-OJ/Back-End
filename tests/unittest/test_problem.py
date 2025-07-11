import io
from zipfile import ZipFile
from tests import utils
import mongomock
import pytest
from mongo import (
    User,
    Problem,
    Course,
    engine,
)
from mongo.problem import BadTestCase
from mongo.problem.test_case import (ContextIO, SimpleIO, IncludeDirectory)


def setup_module(_):
    mongomock.gridfs.enable_gridfs_integration()


def setup_function(_):
    utils.drop_db()


def teardown_function(_):
    utils.drop_db()


def test_copy_problem_without_target_should_dup_to_the_same_course():
    admin = utils.user.create_user(role=User.engine.Role.ADMIN)
    # Only allowed to use C
    original_problem = utils.problem.create_problem(allowed_language=1)
    course = original_problem.courses[0]
    assert len(
        Problem.get_problem_list(
            user=admin,
            course=course.course_name,
        )) == 1
    original_problem.copy_to(
        user=admin,
        target=None,
    )
    # There shouold be 2 problem
    _, copied_problem = Problem.get_problem_list(
        user=admin,
        course=course.course_name,
    )
    utils.problem.cmp_copied_problem(original_problem, copied_problem)


def test_admin_can_copy_problem_to_any_other_course():
    admin = utils.user.create_user(role=User.engine.Role.ADMIN)
    original_problem = utils.problem.create_problem()
    another_course = utils.course.create_course()
    assert len(
        Problem.get_problem_list(
            user=admin,
            course=another_course.course_name,
        )) == 0
    original_problem.copy_to(
        user=admin,
        target=another_course,
    )
    another_problems = Problem.get_problem_list(
        user=admin,
        course=another_course.course_name,
    )
    assert len(another_problems) == 1
    another_problem = another_problems[0]
    utils.problem.cmp_copied_problem(original_problem, another_problem)
    assert another_problem.problem_status == Problem.engine.Visibility.HIDDEN


def test_override_copied_problem_status():
    admin = utils.user.create_user(role=User.engine.Role.ADMIN)
    original_problem = utils.problem.create_problem(
        status=Problem.engine.Visibility.SHOW)
    # Copy and hide
    another_problem = Problem(
        original_problem.copy_to(
            user=admin,
            target=None,
            status=Problem.engine.Visibility.HIDDEN,
        ))
    utils.problem.cmp_copied_problem(original_problem, another_problem)
    assert original_problem.problem_status != Problem.engine.Visibility.HIDDEN
    assert another_problem.problem_status == Problem.engine.Visibility.HIDDEN


def test_simple_io_test_case():
    p = utils.problem.create_problem(
        test_case_info=utils.problem.create_test_case_info(
            language=1,
            task_len=2,
        ))
    f = io.BytesIO()
    with ZipFile(f, 'x') as zf:
        for i, task in enumerate(p.test_case.tasks):
            for j in range(task.case_count):
                zf.writestr(f'{i:02d}{j:02d}.in', 'hello')
                zf.writestr(f'{i:02d}{j:02d}.out', 'hello')
    f.seek(0)
    p.update_test_case(f)


def test_simple_io_with_missing_files_should_fail():
    p = utils.problem.create_problem(
        test_case_info=utils.problem.create_test_case_info(
            language=1,
            task_len=2,
        ))
    f = io.BytesIO()
    with ZipFile(f, 'x') as zf:
        for i, task in enumerate(p.test_case.tasks):
            for j in range(task.case_count):
                zf.writestr(f'{i:02d}{j:02d}.in', 'hello')
    f.seek(0)
    with pytest.raises(BadTestCase):
        p.update_test_case(f)


def test_test_case_include_optional_directory():
    p = utils.problem.create_problem(
        test_case_info=utils.problem.create_test_case_info(
            language=1,
            task_len=2,
        ))
    f = io.BytesIO()
    with ZipFile(f, 'x') as zf:
        zf.writestr('chaos/', '')
        for i, task in enumerate(p.test_case.tasks):
            for j in range(task.case_count):
                zf.writestr(f'{i:02d}{j:02d}.in', 'hello')
                zf.writestr(f'{i:02d}{j:02d}.out', 'hello')
    f.seek(0)
    p.update_test_case(f)


def test_context_io():
    p = utils.problem.create_problem(
        test_case_info=utils.problem.create_test_case_info(
            language=1,
            task_len=2,
        ))
    f = io.BytesIO()
    with ZipFile(f, 'x') as zf:
        zf.writestr('test-case/', '')
        for i, task in enumerate(p.test_case.tasks):
            for j in range(task.case_count):
                test_case_dir = f'test-case/{i:02d}{j:02d}'
                zf.writestr(f'{test_case_dir}/STDIN', 'hello')
                zf.writestr(f'{test_case_dir}/STDOUT', 'hello')
                zf.writestr(f'{test_case_dir}/in/', '')
                zf.writestr(f'{test_case_dir}/in/in.bin', b'hello')
                zf.writestr(f'{test_case_dir}/out/', '')
                zf.writestr(f'{test_case_dir}/out/out.bin', b'hello')
    f.seek(0)
    p.update_test_case(f)


def test_context_io_with_missing_files():
    p = utils.problem.create_problem(
        test_case_info=utils.problem.create_test_case_info(
            language=1,
            task_len=2,
        ))
    f = io.BytesIO()
    with ZipFile(f, 'x') as zf:
        zf.writestr('test-case/', '')
        for i, task in enumerate(p.test_case.tasks):
            for j in range(task.case_count):
                test_case_dir = f'test-case/{i:02d}{j:02d}'
                zf.writestr(f'{test_case_dir}/STDOUT', 'hello')
                zf.writestr(f'{test_case_dir}/in/', '')
                zf.writestr(f'{test_case_dir}/in/in.bin', b'hello')
                zf.writestr(f'{test_case_dir}/out/', '')
                zf.writestr(f'{test_case_dir}/out/out.bin', b'hello')
    f.seek(0)
    with pytest.raises(BadTestCase, match=r'.*STDIN.*'):
        p.update_test_case(f)


def test_context_io_with_missing_test_case_dir():
    p = utils.problem.create_problem(
        test_case_info=utils.problem.create_test_case_info(
            language=1,
            task_len=2,
        ))
    f = io.BytesIO()
    skip = True
    with ZipFile(f, 'x') as zf:
        zf.writestr('test-case/', '')
        for i, task in enumerate(p.test_case.tasks):
            for j in range(task.case_count):
                if skip:
                    skip = False
                    continue
                test_case_dir = f'test-case/{i:02d}{j:02d}'
                zf.writestr(f'{test_case_dir}/STDIN', 'hello')
                zf.writestr(f'{test_case_dir}/STDOUT', 'hello')
                zf.writestr(f'{test_case_dir}/in/', '')
                zf.writestr(f'{test_case_dir}/in/in.bin', b'hello')
                zf.writestr(f'{test_case_dir}/out/', '')
                zf.writestr(f'{test_case_dir}/out/out.bin', b'hello')
    f.seek(0)
    with pytest.raises(BadTestCase):
        p.update_test_case(f)


def test_context_io_extra_file_in_unallowed_path():
    p = utils.problem.create_problem(
        test_case_info=utils.problem.create_test_case_info(
            language=1,
            task_len=2,
        ))
    f = io.BytesIO()
    with ZipFile(f, 'x') as zf:
        zf.writestr('test-case/', '')
        for i, task in enumerate(p.test_case.tasks):
            for j in range(task.case_count):
                test_case_dir = f'test-case/{i:02d}{j:02d}'
                zf.writestr(f'{test_case_dir}/STDIN', 'hello')
                zf.writestr(f'{test_case_dir}/STDOUT', 'hello')
                zf.writestr(f'{test_case_dir}/in/', '')
                zf.writestr(f'{test_case_dir}/out/', '')
                # these files are not allowed
                # they should be placed under in/ and out/
                zf.writestr(f'{test_case_dir}/extra-input', b'aaa')
                zf.writestr(f'{test_case_dir}/extra-output', b'bbb')
    f.seek(0)
    with pytest.raises(
            BadTestCase,
            match=r'.*(extra-input|extra-output),*',
    ):
        p.update_test_case(f)


def test_student_cannot_view_hidden_problem():
    c = utils.course.create_course()
    u = utils.user.create_user(course=c)
    p = utils.problem.create_problem(
        status=engine.Problem.Visibility.HIDDEN,
        course=c,
    )

    assert c.permission(u, Course.Permission.VIEW)
    assert not p.permission(
        u,
        Problem.Permission.VIEW | Problem.Permission.ONLINE,
    )


def test_teacher_can_manage_hidden_problem():
    u = utils.user.create_user(role=engine.User.Role.TEACHER)
    c = utils.course.create_course(teacher=u)
    p = utils.problem.create_problem(
        status=engine.Problem.Visibility.HIDDEN,
        course=c,
    )

    assert p.permission(
        u,
        Problem.Permission.MANAGE | Problem.Permission.ONLINE,
    )


class TestSimpleIO:

    def test_validate_with_none_test_case(self):
        rule = SimpleIO(Problem(87))
        with pytest.raises(BadTestCase) as err:
            rule.validate(None)
        assert str(err.value) == 'test case is None'

    def test_validate_with_excludes_raise_bad_test_case_error(self):
        zip = 'tests/problem_test_case/bogay/test_case.zip'
        rule = SimpleIO(Problem(87), ['0000'])
        with pytest.raises(BadTestCase) as err:
            rule.validate(zip)
        assert str(err.value).startswith('I/O data not equal to meta provided')


class TestContextIO:

    def test_validate_with_none_test_case(self):
        rule = ContextIO(Problem(87))
        with pytest.raises(BadTestCase) as err:
            rule.validate(None)
        assert str(err.value) == 'test case is None'

    def test_validate_with_test_case_is_not_dir(self, monkeypatch):
        zip = 'tests/problem_test_case/bogay/test_case.zip'
        rule = ContextIO(Problem(87))
        from mongo.problem.test_case import zipfile
        monkeypatch.setattr(zipfile.Path, 'exists', lambda _: True)
        monkeypatch.setattr(zipfile.Path, 'is_dir', lambda _: False)
        with pytest.raises(BadTestCase) as err:
            rule.validate(zip)
        assert str(err.value) == 'test-case is not a directory'

    def test_validate_with_extra_test_case_dir(self, problem_ids):
        pid = problem_ids('teacher', 1)[0]
        rule = ContextIO(Problem(pid))
        zip = 'tests/problem_test_case/alardutp/test_case.zip'
        with pytest.raises(BadTestCase) as err:
            rule.validate(zip)
        assert str(err.value) == 'extra test case directory found: extra'


class TestIncludeDirectory:

    def test_validate_with_none_test_case(self):
        rule = IncludeDirectory(Problem(87), 'path/to/include/dir')
        with pytest.raises(BadTestCase) as err:
            rule.validate(None)
        assert str(err.value) == 'test case is None'

    def test_validate_with_path_does_not_exist(self):
        rule = IncludeDirectory(Problem(87), 'path/does/not/exist', False)
        with pytest.raises(BadTestCase) as err:
            zip = 'tests/problem_test_case/bogay/test_case.zip'
            rule.validate(zip)
        assert str(err.value) == 'directory path/does/not/exist does not exist'

    def test_validate_with_non_directory_path(self):
        file = '0000.in'
        rule = IncludeDirectory(Problem(87), file, False)
        with pytest.raises(BadTestCase) as err:
            zip = 'tests/problem_test_case/bogay/test_case.zip'
            rule.validate(zip)
        assert str(err.value) == f'{file} is not a directory'

    def test_validate(self):
        dir = 'dir/'
        rule = IncludeDirectory(Problem(87), dir, False)
        zip = 'tests/problem_test_case/alardutp/test_case.zip'
        assert rule.validate(zip)


class TestMongoProblem:

    def test_boolen_of_problem(self, problem_ids, monkeypatch):
        problem = Problem(problem_ids('teacher', 1)[0])
        assert problem

        def mock_filter_raise_validation_error(*args, **kwargs):
            raise engine.ValidationError

        from mongoengine.queryset.queryset import QuerySet
        monkeypatch.setattr(QuerySet, 'filter',
                            mock_filter_raise_validation_error)
        problem.proble_id = 878787
        assert not problem

    def test_detailed_info_of_problem_does_not_exist(self):
        problem = Problem(878787)
        assert problem.detailed_info() == {}
        assert repr(problem) == '{}'

    def test_detailed_info_with_nested_value(self, problem_ids):
        problem = Problem(problem_ids('teacher', 1)[0])
        assert problem.detailed_info(nested__info='testCase__language') == {
            'nested': {
                'info': 2
            }
        }

    def test_negtive_language_is_not_allowed(self, problem_ids):
        problem = Problem(problem_ids('teacher', 1)[0])
        assert not problem.allowed(-1)

    def test_high_score_with_cache(self, problem_ids, monkeypatch):
        from mongo.problem.problem import RedisCache
        monkeypatch.setattr(RedisCache, 'get', lambda *_: b'87')
        problem = Problem(problem_ids('teacher', 1)[0])
        utils.user.create_user(username='student')
        assert problem.get_high_score(user='student') == 87

    def test_get_problem_list_with_course_does_not_exist(self, problem_ids):
        problem = Problem(problem_ids('teacher', 1)[0])
        plist = problem.get_problem_list('teacher',
                                         course='CourseDoesNotExist')
        assert plist == []

    def test_edit_problem_without_100_scores_in_total(self, problem_ids):
        request_json = {
            'courses': [],
            'status': 1,
            'type': 0,
            'problem_name': 'Problem title',
            'description': {
                'description': 'Test description.',
                'input': '',
                'output': '',
                'hint': '',
                'sampleInput': [],
                'sampleOutput': []
            },
            'tags': [],
            'test_case_info': {
                'language':
                1,
                'fillInTemplate':
                '',
                'tasks': [{
                    'caseCount': 1,
                    'taskScore': 87,
                    'memoryLimit': 1000,
                    'timeLimit': 1000
                }]
            }
        }
        pid = problem_ids('teacher', 1)[0]
        with pytest.raises(ValueError):
            Problem.edit_problem(User('teacher'), pid, **request_json)

    def test_copy_problem(self, problem_ids):
        pid = problem_ids('teacher', 1)[0]
        teacher = utils.user.create_user(
            username='teacher-2',
            role=engine.User.Role.TEACHER,
        )
        Problem.copy_problem(teacher, pid)
        new_problem = Problem.get_problem_list(teacher)[-1]
        assert Problem(pid).problem_name == new_problem.problem_name
