# .pgpass file format implementation
#
# cf. https://www.postgresql.org/docs/current/static/libpq-pgpass.html
#
# - Support : and \ escape.
# - Sort entry by precision (even if commented).
# - Preserve comment order when sorting.

from __future__ import print_function

import os
import sys

from .errors import ParseError
from ._helpers import open_or_stdin


def unescape(s, delim):
    return s.replace('\\' + delim, delim).replace('\\\\', '\\')


def escapedsplit(s, delim):
    if len(delim) != 1:
        raise ValueError('Invalid delimiter: ' + delim)

    ln = len(s)
    escaped = False
    i = 0
    j = 0

    while j < ln:
        if s[j] == '\\':
            escaped = not escaped
        elif s[j] == delim:
            if not escaped:
                yield unescape(s[i:j], delim)
                i = j + 1
                escaped = False
        j += 1
    yield unescape(s[i:j], delim)


class PassComment(str):
    def __repr__(self):
        return '<%s %.32s>' % (self.__class__.__name__, self)

    def __lt__(self, other):
        if isinstance(other, PassEntry):
            try:
                return self.entry < other
            except ValueError:
                pass
        return False

    @property
    def comment(self):
        return self.lstrip('#').strip()

    @property
    def entry(self):
        if not hasattr(self, '_entry'):
            self._entry = PassEntry.parse(self.comment)
        return self._entry


class PassEntry(object):
    @classmethod
    def parse(cls, line):
        fields = list(escapedsplit(line.strip(), ':'))
        if len(fields) != 5:
            raise ValueError("Invalid line.")
        if fields[1] != '*':
            fields[1] = int(fields[1])
        return cls(*fields)

    def __init__(self, hostname, port, database, username, password):
        self.hostname = hostname
        self.port = port
        self.database = database
        self.username = username
        self.password = password

    def __eq__(self, other):
        if isinstance(other, PassComment):
            try:
                other = other.entry
            except ValueError:
                return False
        return self.as_tuple()[:-1] == other.as_tuple()[:-1]

    def __hash__(self):
        return hash(self.as_tuple()[:-1])

    def __lt__(self, other):
        if isinstance(other, PassComment):
            try:
                other = other.entry
            except ValueError:
                return False

        return self.sort_key() < other.sort_key()

    def __repr__(self):
        return '<%s %s@%s:%s/%s>' % (
            self.__class__.__name__,
            self.username, self.hostname, self.port, self.database,
        )

    def __str__(self):
        return ':'.join([
            str(x).replace('\\', r'\\').replace(':', r'\:')
            for x in self.as_tuple()
        ])

    def as_tuple(self):
        return (
            self.hostname,
            self.port,
            self.database,
            self.username,
            self.password,
        )

    def sort_key(self):
        tpl = self.as_tuple()[:-1]
        # Compute precision from * occurences.
        precision = len([x for x in tpl if x == '*'])
        # More specific entries comes first.
        return [precision] + [chr(0xFF) if x == '*' else x for x in tpl]


class PassFile(object):
    def __init__(self):
        self.lines = []

    def __iter__(self):
        return iter(filter(lambda l: isinstance(l, PassEntry), self.lines))

    def parse(self, fo):
        for i, line in enumerate(fo):
            stripped = line.lstrip()
            if not stripped or stripped.startswith('#'):
                entry = PassComment(line.replace(os.linesep, ''))
            else:
                try:
                    entry = PassEntry.parse(line)
                except Exception as e:
                    raise ParseError(1 + i, line, str(e))
            self.lines.append(entry)

    def sort(self):
        # Sort but preserve comments above entries.
        entries = []
        comments = []
        for line in self.lines:
            if isinstance(line, PassComment):
                try:
                    line.entry
                except ValueError:
                    comments.append(line)
                    continue

            entries.append((line, comments))
            comments = []

        entries.sort()
        self.lines[:] = []
        for entry, comments in entries:
            self.lines.extend(comments)
            self.lines.append(entry)

    def save(self, fo):
        for line in self.lines:
            fo.write(str(line) + os.linesep)


def parse(fo):
    pgpass = PassFile()
    pgpass.parse(fo)
    return pgpass


if __name__ == '__main__':  # pragma: nocover
    argv = sys.argv[1:] + ['-']
    try:
        with open_or_stdin(argv[0]) as fo:
            pgpass = parse(fo)
        pgpass.sort()
        pgpass.save(sys.stdout)
    except Exception as e:
        print(str(e), file=sys.stderr)
        exit(1)
