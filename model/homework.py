from typing import List
from flask import Blueprint
from mongo import *
from mongo import engine
from .utils import *
from .auth import login_required
from .course import course_api

__all__ = ['homework_api']

homework_api = Blueprint('homework_api', __name__)


@homework_api.post('/')
@login_required
@Request.json('name', 'course_name', 'markdown', 'start', 'end', 'problem_ids',
              'scoreboard_status', 'penalty')
def create_homework(user, course_name, name, markdown, start, end, problem_ids,
                    scoreboard_status, penalty):
    try:
        homework = Homework.add(
            user=user,
            hw_name=name,
            markdown=markdown,
            scoreboard_status=scoreboard_status,
            course_name=course_name,
            problem_ids=problem_ids or [],
            start=start,
            end=end,
            penalty=penalty,
        )
    except NameError:
        return HTTPError('user must be the teacher or ta of this course', 403)
    except FileExistsError:
        return HTTPError('homework exists in this course', 400)
    except engine.DoesNotExist as e:
        return HTTPError(str(e), 404)
    except (PermissionError, engine.NotUniqueError) as e:
        return HTTPError(str(e), 403)
    return HTTPResponse('Add homework Success')


@homework_api.get('/<homework_id>')
@login_required
def get_homework(user, homework_id):
    try:
        homework = Homework.get_by_id(homework_id)
        ret = {
            'name':
            homework.homework_name,
            'start':
            int(homework.duration.start.timestamp()),
            'end':
            int(homework.duration.end.timestamp()),
            'problemIds':
            homework.problem_ids,
            'markdown':
            homework.markdown,
            'studentStatus':
            homework.student_status
            if user.role < 2 else homework.student_status.get(user.username),
            'penalty':
            homework.penalty if hasattr(homework, 'penalty') else None,
        }
    except engine.DoesNotExist as e:
        return HTTPError(str(e), 404)
    except (PermissionError, engine.NotUniqueError) as e:
        return HTTPError(str(e), 403)
    return HTTPResponse('get homework', data=ret)


@homework_api.put('/<homework_id>')
@login_required
@Request.json('name', 'markdown', 'start', 'end', 'problem_ids',
              'scoreboard_status', 'penalty')
def update_homework(user, homework_id, name, markdown, start, end, problem_ids,
                    scoreboard_status, penalty):
    try:
        homework = Homework.update(
            user=user,
            homework_id=homework_id,
            markdown=markdown,
            new_hw_name=name,
            start=start,
            end=end,
            problem_ids=problem_ids,
            scoreboard_status=scoreboard_status,
            penalty=penalty,
        )
    except engine.DoesNotExist as e:
        return HTTPError(str(e), 404)
    except (PermissionError, engine.NotUniqueError) as e:
        return HTTPError(str(e), 403)
    return HTTPResponse('Update homework Success')


@homework_api.delete('/<homework_id>')
@login_required
def delete_homework(user, homework_id):
    try:
        homework = Homework(homework_id)
        homework = homework.delete_problems(user=user,
                                            course=homework.course_id)
    except engine.DoesNotExist as e:
        return HTTPError(str(e), 404)
    except (PermissionError, engine.NotUniqueError) as e:
        return HTTPError(str(e), 403)
    return HTTPResponse('Delete homework Success')


@course_api.route('/<course_name>/homework', methods=['GET'])
@login_required
def get_homework_list(user, course_name):
    '''
    get a list of homework
    '''
    try:
        homeworks = Homework.get_homeworks(course_name=course_name)
        data = []
        for homework in homeworks:
            new = {
                'name': homework.homework_name,
                'start': int(homework.duration.start.timestamp()),
                'end': int(homework.duration.end.timestamp()),
                'problemIds': homework.problem_ids,
                'markdown': homework.markdown,
                'id': str(homework.id)
            }
            # normal user can not view other's status
            if user.role < 2:
                new.update({'studentStatus': homework.student_status})
            else:
                new.update({
                    'studentStatus':
                    homework.student_status.get(user.username)
                })
            data.append(new)
    except DoesNotExist:
        return HTTPError('course not exists',
                         404,
                         data={'courseName': course_name})
    return HTTPResponse('get homeworks', data=data)


@homework_api.route('/<course>/<homework_name>/ip-filters', methods=['GET'])
@login_required
def get_ip_filters(
    user,
    course: str,
    homework_name: str,
):
    if user.role != 0:
        return HTTPError('Not admin!', 403)
    try:
        hw = Homework.get_by_name(course, homework_name)
    except DoesNotExist:
        return HTTPError('Homework does not exist', 404)
    return HTTPResponse(data={'ipFilters': hw.ip_filters})


@homework_api.route('/<course>/<homework_name>/ip-filters', methods=['PATCH'])
@login_required
@Request.json('patches:list')
def patch_ip_filters(
    user,
    course: str,
    homework_name: str,
    patches: List,
):
    if user.role != 0:
        return HTTPError('Not admin!', 403)
    try:
        hw = Homework.get_by_name(course, homework_name)
    except DoesNotExist:
        return HTTPError('Homework does not exist', 404)
    adds = []
    dels = []
    for patch in patches:
        op = patch.get('op')
        if op not in {'add', 'del'}:
            return HTTPError('Invalid operation', 400, data={'op': op})
        value = patch.get('value')
        if value is None:
            return HTTPError('Value not found', 400)
        if op == 'add':
            adds.append(value)
        else:
            dels.append(value)
        # Validate filter format
        try:
            IPFilter(value)
        except ValueError as e:
            return HTTPError(str(e), 400)

    hw.update(push_all__ip_filters=adds)
    hw.update(pull_all__ip_filters=dels)
    return HTTPResponse()
