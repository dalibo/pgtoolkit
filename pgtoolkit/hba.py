# cf. https://www.postgresql.org/docs/devel/static/auth-pg-hba-conf.html

from __future__ import print_function

import os
import shlex
import sys

from .errors import ParseError
from ._helpers import open_or_stdin


class HBAComment(str):
    def __repr__(self):
        return '<%s %.32s>' % (self.__class__.__name__, self)


class HBAEntry(object):
    CONNECTION_TYPES = ['local', 'host', 'hostssl', 'hostnossl']
    KNOWN_FIELDS = [
        'conntype', 'database', 'user', 'address', 'netmask', 'method',
    ]

    @classmethod
    def parse(cls, line):
        line = line.strip()
        fields = ['conntype', 'database', 'user']
        values = shlex.split(line, comments=False)
        try:
            hash_idx = values.index('#')
        except ValueError:
            comment = None
        else:
            values, comment = values[:hash_idx], values[hash_idx:]
            comment = ' '.join(comment[1:])

        if values[0] not in cls.CONNECTION_TYPES:
            raise ValueError("Unknown connection types %s" % values[0])
        if 'local' != values[0]:
            fields.append('address')
        known_values = [v for v in values if '=' not in v]
        if len(known_values) >= 6:
            fields.append('netmask')
        fields.append('method')
        base_options = list(zip(fields, values[:len(fields)]))
        auth_options = [o.split('=') for o in values[len(fields):]]
        return cls(base_options + auth_options, comment=comment)

    def __init__(self, values, comment=None):
        self.__dict__.update(dict(values))
        self.fields = [k for k, _ in values]
        self.comment = comment

    def __repr__(self):
        return '<%s %s%s>' % (
            self.__class__.__name__,
            ' '.join(self.known_values),
            '...' if self.auth_options else ''
        )

    def __str__(self):
        # Stolen from default pg_hba.conf
        widths = [8, 16, 16, 16, 8]

        fmt = ''
        for i, field in enumerate(self.KNOWN_FIELDS):
            try:
                width = widths[i]
            except IndexError:
                width = 0

            if field not in self.fields:
                fmt += ' ' * width
                continue

            if width:
                fmt += '%%(%s)-%ds ' % (field, width - 1)
            else:
                fmt += '%%(%s)s ' % (field,)
        line = fmt.rstrip() % self.__dict__

        auth_options = ['%s=%s' % i for i in self.auth_options]
        if auth_options:
            line += ' ' + ' '.join(auth_options)

        if self.comment is not None:
            line += '  # ' + self.comment
        else:
            line = line.rstrip()

        return line

    @property
    def known_values(self):
        return [
            getattr(self, f)
            for f in self.KNOWN_FIELDS
            if f in self.fields
        ]

    @property
    def auth_options(self):
        return [
            (f, getattr(self, f))
            for f in self.fields
            if f not in self.KNOWN_FIELDS
        ]


class HBA(object):
    def __init__(self):
        self.lines = []

    def __iter__(self):
        return iter(filter(lambda l: isinstance(l, HBAEntry), self.lines))

    def parse(self, fo):
        for i, line in enumerate(fo):
            stripped = line.lstrip()
            if not stripped or stripped.startswith('#'):
                entry = HBAComment(line.replace(os.linesep, ''))
            else:
                try:
                    entry = HBAEntry.parse(line)
                except Exception as e:
                    raise ParseError(1 + i, line, str(e))
            self.lines.append(entry)

    def save(self, fo):
        for line in self.lines:
            fo.write(str(line) + os.linesep)


def parse(fo):
    hba = HBA()
    hba.parse(fo)
    return hba


if __name__ == '__main__':  # pragma: nocover
    argv = sys.argv[1:] + ['-']
    try:
        with open_or_stdin(argv[0]) as fo:
            hba = parse(fo)
        hba.save(sys.stdout)
    except Exception as e:
        print(str(e), file=sys.stderr)
        exit(1)
