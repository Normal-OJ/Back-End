import abc
import zipfile
from typing import BinaryIO
from .exception import BadTestCase


class TestCase(abc.ABC):
    def __init__(self, problem):
        self.problem = problem

    # TODO: define generic validation error
    @abc.abstractmethod
    def validate(self, test_case: BinaryIO) -> bool:
        '''
        Validate test case
        '''
        raise NotImplementedError


class SimpleIO(TestCase):
    def validate(self, test_case: BinaryIO) -> bool:
        # test case must not be None
        if test_case is None:
            raise ValueError('test case is None')
        expected = self.expected_test_case_filenames()
        # check chaos folder
        chaos_path = zipfile.Path(test_case, at='chaos')
        if chaos_path.exists() and chaos_path.is_file():
            raise BadTestCase('find chaos, but it\'s not a directory')
        got = {*zipfile.ZipFile(test_case).namelist()} - {'chaos'}
        # check diff
        extra = got - expected
        short = expected - got
        if len(extra) or len(short):
            raise BadTestCase(
                'io data not equal to meta provided',
                [*extra],
                [*short],
            )
        # reset
        test_case.seek(0)
        return True

    def expected_test_case_filenames(self):
        excepted = set()
        for i, task in enumerate(self.problem.test_case.tasks):
            for j in range(task.case_count):
                excepted.add(f'{i:02d}{j:02d}.in')
                excepted.add(f'{i:02d}{j:02d}.out')
        return excepted
