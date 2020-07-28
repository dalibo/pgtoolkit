from datetime import datetime, timedelta
import json
import sys


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


class PassthroughManager:
    def __init__(self, ret=None):
        self.ret = ret

    def __enter__(self):
        return self.ret

    def __exit__(self, *a):
        pass


def open_or_return(fo_or_path, mode='r'):
    # Returns a context manager around a file-object for fo_or_path. If
    # fo_or_path is a file-object, the context manager keeps it open. If it's a
    # path, the file is opened with mode and will be closed upon context exit.
    # If fo_or_path is None, a ValueError is raised.

    if fo_or_path is None:
        raise ValueError('No file-like object nor path provided')
    if isinstance(fo_or_path, str):
        return open(fo_or_path, mode)

    # Skip default file context manager. This allows to always use with
    # statement and don't care about closing the file. If the file is opened
    # here, it will be closed properly. Otherwise, it will be kept open thanks
    # to PassthroughManager.
    return PassthroughManager(fo_or_path)


class Timer:
    def __enter__(self):
        self.start = datetime.utcnow()
        return self

    def __exit__(self, *a):
        self.delta = datetime.utcnow() - self.start
