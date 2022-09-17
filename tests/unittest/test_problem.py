from tests import utils
from mongo import (
    User,
    Problem,
)


def setup_function(_):
    utils.drop_db()


def teardown_function(_):
    utils.drop_db()


def cmp_copied_problem(original: Problem, copy: Problem):
    # It shouold be a new problem
    assert original.problem_id != copy.problem_id
    # But some fields are identical
    fields = (
        'problem_name',
        'problem_status',
        'problem_type',
        'description',
        'tags',
        'can_view_stdout',
        'allowed_language',
        'quota',
    )
    for field in fields:
        assert getattr(original, field) == getattr(copy, field)
    # And some fields shuold be default
    assert len(copy.homeworks) == 0
    assert len(copy.high_scores) == 0


def test_copy_problem_without_target_should_dup_to_the_same_course():
    admin = utils.user.create_user(role=User.engine.Role.ADMIN)
    original_problem = utils.problem.create_problem()
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
    cmp_copied_problem(original_problem, copied_problem)


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
    cmp_copied_problem(original_problem, another_problem)
