import abc
import zipfile
from typing import BinaryIO, Set, TYPE_CHECKING, List
from .exception import BadTestCase
if TYPE_CHECKING:
    from .. import Problem  # pragma: no cover


class TestCaseRule(abc.ABC):

    def __init__(self, problem: 'Problem'):
        self.problem = problem

    # TODO: define generic validation error
    @abc.abstractmethod
    def validate(self, test_case: BinaryIO) -> bool:
        '''
        Validate test case
        '''
        raise NotImplementedError  # pragma: no cover


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
            raise BadTestCase('test case is None')
        path = zipfile.Path(test_case, at=self.path)

        if not path.exists():
            if self.optional:
                return True
            raise BadTestCase(f'directory {self.path} does not exist')

        if path.is_file():
            raise BadTestCase(f'{self.path} is not a directory')

        return True


class SimpleIO(TestCaseRule):
    '''
    Test cases that only contains single input and output file.
    '''

    def __init__(self, problem: 'Problem', excludes: List[str] = []):
        self.excludes = excludes
        super().__init__(problem)

    def validate(self, test_case: BinaryIO) -> bool:
        # test case must not be None
        if test_case is None:
            raise BadTestCase('test case is None')
        got = {*zipfile.ZipFile(test_case).namelist()}
        for ex in self.excludes:
            if ex.endswith('/'):
                got = {g for g in got if not g.startswith(ex)}
            else:
                got.discard(ex)
        expected = self.expected_test_case_filenames()
        if got != expected:
            extra = list(got - expected)
            missing = list(expected - got)
            raise BadTestCase(
                f'I/O data not equal to meta provided: {extra=}, {missing=}')
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


class ContextIO(TestCaseRule):
    '''
    Test cases that contains multiple file for input/output.
    e.g. given a image, rotate and save it on disk.
    '''

    def validate(self, test_case_fp: BinaryIO) -> bool:
        if test_case_fp is None:
            raise BadTestCase('test case is None')

        test_case_root = zipfile.Path(test_case_fp, at='test-case/')
        if not test_case_root.exists():
            raise BadTestCase('test-case not found')
        if not test_case_root.is_dir():
            raise BadTestCase('test-case is not a directory')

        expected_dirs = self.expected_test_case_dirs()

        for test_case in test_case_root.iterdir():
            try:
                expected_dirs.remove(test_case.name)
            except KeyError:
                raise BadTestCase(
                    f'extra test case directory found: {test_case.name}')
            self.validate_test_case_dir(test_case)

        if len(expected_dirs):
            raise BadTestCase(
                f'missing test case directory: {", ".join(expected_dirs)}')

    def validate_test_case_dir(self, test_case_dir: zipfile.Path):
        requireds = {
            'STDIN',
            'STDOUT',
        }

        for r in requireds:
            if not (test_case_dir / r).exists():
                raise BadTestCase(f'required file/dir not found: {r}')

        dirs = {
            'in',
            'out',
        }
        for fp in test_case_dir.iterdir():
            # files under in/out are allowed
            if fp.is_dir() and fp.name in dirs:
                continue
            # STDIN/STDOUT are allowed
            if fp.name in requireds:
                continue
            raise BadTestCase(f'files in unallowed path: {fp.name}')

    def expected_test_case_dirs(self) -> Set[str]:
        excepted = set()
        for i, task in enumerate(self.problem.test_case.tasks):
            for j in range(task.case_count):
                excepted.add(f'{i:02d}{j:02d}')
        return excepted
