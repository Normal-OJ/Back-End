import io
from zipfile import ZipFile
from tests import utils
import mongomock
import pytest
from mongo import (
    User,
    Problem,
)
from mongo.problem import BadTestCase


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
