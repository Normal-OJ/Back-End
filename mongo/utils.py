import hashlib

__all__ = ['hash_id', 'perm', 'can_view_problem']


def hash_id(salt, text):
    text = ((salt or '') + (text or '')).encode()
    sha = hashlib.sha3_512(text)
    return sha.hexdigest()[:24]


def perm(course, user):
    '''4: admin, 3: teacher, 2: TA, 1: student, 0: not found
    '''
    return 4 - [
        user.role == 0, user == course.teacher, user in course.tas,
        user.username in course.student_nicknames.keys(), True
    ].index(True)


def can_view_problem(user, problem):
    '''cheeck if a user can view the problem'''
    if user.role == 0:
        return True
    if user.contest:
        if user.contest in problem.contests:
            return True
        return False
    if user.username == problem.owner:
        return True
    for course in problem.courses:
        permission = 1 if course.course_name == "Public" else perm(
            course, user)
        if permission and (problem.problem_status == 0 or permission >= 2):
            return True
    return False