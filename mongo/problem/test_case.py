import abc
import zipfile
from typing import BinaryIO, Set, TYPE_CHECKING, List
from .exception import BadTestCase
if TYPE_CHECKING:
    from .. import Problem


class TestCaseRule(abc.ABC):

    def __init__(self, problem: 'Problem'):
        self.problem = problem

    # TODO: define generic validation error
    @abc.abstractmethod
    def validate(self, test_case: BinaryIO) -> bool:
        '''
        Validate test case
        '''
        raise NotImplementedError


class IncludeDirectory(TestCaseRule):

    def __init__(
        self,
        problem: 'Problem',
        path: str,
        optional: bool = True,
    ):
        self.path = path
        self.optional = optional
        super().__init__(problem)

    def validate(self, test_case: BinaryIO) -> bool:
        if test_case is None:
            raise ValueError('test case is None')
        path = zipfile.Path(test_case, at=self.path)

        if not path.exists():
            if self.optional:
                return True
            raise BadTestCase(f'directory {self.path} does not exist')

        if path.is_file():
            raise BadTestCase(f'{self.path} is not a directory')

        return True


class SimpleIO(TestCaseRule):

    def __init__(self, problem: 'Problem', excludes: List[str] = []):
        self.excludes = excludes
        super().__init__(problem)

    def validate(self, test_case: BinaryIO) -> bool:
        # test case must not be None
        if test_case is None:
            raise ValueError('test case is None')
        got = {*zipfile.ZipFile(test_case).namelist()}
        for ex in self.excludes:
            if ex.endswith('/'):
                got = {g for g in got if not g.startswith(ex)}
            else:
                got.discard(ex)
        expected = self.expected_test_case_filenames()
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

    def expected_test_case_filenames(self) -> Set[str]:
        excepted = set()
        for i, task in enumerate(self.problem.test_case.tasks):
            for j in range(task.case_count):
                excepted.add(f'{i:02d}{j:02d}.in')
                excepted.add(f'{i:02d}{j:02d}.out')
        return excepted
