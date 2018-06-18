import sys


def open_or_stdin(filename, stdin=sys.stdin):
    if filename == '-':
        fo = stdin
    else:
        fo = open(filename)
    return fo
