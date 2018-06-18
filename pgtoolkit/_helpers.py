from datetime import datetime
import sys


def open_or_stdin(filename, stdin=sys.stdin):
    if filename == '-':
        fo = stdin
    else:
        fo = open(filename)
    return fo


class Timer(object):
    def __enter__(self):
        self.start = datetime.utcnow()
        return self

    def __exit__(self, *a):
        self.delta = datetime.utcnow() - self.start
