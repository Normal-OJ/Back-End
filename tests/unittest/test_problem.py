from tests import utils
from mongo import (
    User,
    Problem,
)


def setup_function(_):
    utils.drop_db()


def teardown_function(_):
    utils.drop_db()


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
