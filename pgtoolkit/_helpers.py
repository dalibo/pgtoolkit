from datetime import datetime
import json
import sys
from datetime import timedelta


def format_timedelta(delta):
    values = [
        (delta.days, 'd'),
        (delta.seconds, 's'),
        (delta.microseconds, 'us'),
    ]
    values = ['%d%s' % v for v in values if v[0]]
    if values:
        return ' '.join(values)
    else:
        return '0s'


class JSONDateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, timedelta):
            return format_timedelta(obj)
        return super().default(obj)


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
