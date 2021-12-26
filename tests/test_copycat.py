import pathlib
from model import *
from mongo import engine
from tests.base_tester import BaseTester

S_NAMES = {
    'student': 'Chika.Fujiwara',  # base.c base.py
    'student-2': 'Nico.Kurosawa',  # base.cpp base_2.py
}


class TestCopyCat(BaseTester):
    # user, course, problem, submission
    def test_copycat(self, forge_client, problem_ids, make_course, submit_once,
                     save_source, tmp_path):
        # create course
        course_name = make_course(
            username="teacher",
            students=S_NAMES,
        ).name
        # create problem
        pid = problem_ids("teacher", 1, True)[0]
        # save source code (for submit_once)
        src_dir = pathlib.Path('tests/src')
        exts = ['.c', '.cpp', '.py', '.pdf']
        for src in src_dir.iterdir():
            if any([not src.suffix in exts, not src.is_file()]):
                continue
            save_source(
                src.stem,
                src.read_bytes(),
                exts.index(src.suffix),
            )
        # submission
        name2code = {
            'student': [('base.c', 0), ('base.py', 2)],
            'student-2': [('base.cpp', 1), ('base_2.py', 2)]
        }
        for name, code in name2code.items():
            for filename, language in code:
                submit_once(
                    name=name,
                    pid=pid,
                    filename=filename,
                    lang=language,
                )
        # change all submissions to status 0 (Accepted)
        engine.Submission.objects.update(status=0)
        # 'post' to send report request /copycat course:course_name problemId: problem_id
        client = forge_client('teacher')
        rv, rv_json, rv_data = self.request(
            client,
            'post',
            '/copycat',
            json={
                'course': course_name,
                'problemId': pid,
                'studentNicknames': {
                    'student': 'student',
                    'student-2': 'student-2',
                },
            },
        )
        assert rv.status_code == 200, rv_json
        # 'get' to get the report url /copycat course:course_name problemId: problem_id
        client = forge_client('teacher')
        rv, rv_json, rv_data = self.request(
            client, 'get', f'/copycat?course={course_name}&problemId={pid}')
        assert rv.status_code == 200, rv_json
        assert isinstance(rv_data, dict), rv_data
