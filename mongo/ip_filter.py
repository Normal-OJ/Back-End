import re
from typing import Union

__all__ = (
    'OctetMatcher',
    'IPFilter',
)


class OctetMatcher:
    def __init__(self, pattern: str) -> None:
        if pattern.isdecimal():
            num = int(pattern)
            if not 0 <= num < 256:
                raise ValueError(f'A octet must in range [0, 255], got {num}.')
            self.ranges = ((num, num), )
        else:
            pattern = pattern.replace(' ', '').split(',')
            if any(not re.match(r'\d+-\d+', r) for r in pattern):
                raise ValueError(f'Invalid range pattern.')
            ranges = ((*sorted(map(int, r.split('-'))), ) for r in pattern)
            if any(l < 0 or h > 255 for l, h in ranges):
                raise ValueError(f'Invalid number range.')
            self.ranges = ranges

    def match(self, num: Union[int, str]) -> bool:
        if type(num) == str:
            num = int(num)
        return any(l <= num <= r for l, r in self.ranges)


class IPFilter:
    def __init__(self, pattern: str) -> None:
        pattern = pattern.split('.')
        if len(pattern) != 4:
            raise ValueError('Invalid filter pattern.')
        self.matchers = [OctetMatcher(p) for p in pattern]

    def is_valid_ip(self, ip: str) -> bool:
        ip = ip.split('.')
        if len(ip) != 4:
            raise False
        if not all(x.isdecimal() for x in ip):
            raise False
        if not all(0 <= x <= 255 for x in ip):
            return False
        return True

    def match(self, ip: str) -> bool:
        if not self.is_valid_ip(ip):
            return False
        return all(m.match(i) for i, m in zip(ip.split(','), self.matchers))
