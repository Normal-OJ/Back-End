class BadTestCase(Exception):

    def __init__(self, expression, extra, short):
        super().__init__(expression)
        self.extra = extra
        self.short = short

    @property
    def dict(self):
        return {
            'extra': self.extra,
            'short': self.short,
            'ERR_TYPE': 'BAD_TEST_CASE',
        }
