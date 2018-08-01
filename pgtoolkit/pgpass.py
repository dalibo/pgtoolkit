# coding: utf-8
r""".. currentmodule:: pgtoolkit.pgpass

This module provides support for `.pgpass` file format. Here are some
highlights :

 - Supports ``:`` and ``\`` escape.
 - Sorts entry by precision (even if commented).
 - Preserves comments order when sorting.

See `The Password File
<https://www.postgresql.org/docs/current/static/libpq-pgpass.html>`__ section
in PostgreSQL documentation.

.. autofunction:: parse
.. autoclass:: PassEntry
.. autoclass:: PassComment
.. autoclass:: PassFile


Editing a .pgpass file
----------------------

.. code:: python

    with open('.pgpass') as fo:
        pgpass = parse(fo)
    pgpass.lines.append(PassEntry(username='toto', password='confidentiel'))
    pgpass.sort()
    with open('.pgpass', 'w') as fo:
        pgpass.save(fo)


Using as a script
-----------------

You can call :mod:`pgtoolkit.pgpass` module as a CLI script. It accepts a file
path as first argument, read it, validate it, sort it and output it in stdout.


.. code:: console

   $ python -m pgtoolkit.pgpass ~/.pgpass
   more:5432:precise:entry:0revea\\ed
   #disabled:5432:*:entry:0secret

   # Multiline
   # comment.
   other:5432:*:username:0unveiled
   *:*:*:postgres:c0nfident\:el

"""  # noqa


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
    """A .pgpass comment, including spaces and ``#``.

    It's a child of ``str``.

    >>> comm = PassComment("# my comment")
    >>> comm.comment
    'my comment'

    .. attribute:: comment

        The actual message of the comment. Surrounding whitespaces stripped.

    """
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
    """Holds a .pgpass entry.

    .. automethod:: parse

    .. attribute:: hostname

       Server hostname, the first field.

    .. attribute:: port

       Server port, the second field.

    .. attribute:: database

       Database, the third field.

    .. attribute:: username

       Username, the fourth field.

    .. attribute:: password

       Password, the fifth field.

    :class:`PassEntry` object is sortable. A :class:`PassEntry` object is lower
    than another if it is more specific. The more an entry has wildcard, the
    less it is specific.

    """

    @classmethod
    def parse(cls, line):
        """ Parse a single line.

        :param line: string containing a serialized .pgpass entry.
        :return: :class:`PassEntry` object holding entry data.
        :raises ValueError: on invalid line.
        """
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
    """Holds .pgpass file entries and comments.

    .. automethod:: parse
    .. automethod:: __iter__
    .. automethod:: sort
    .. automethod:: save

    .. attribute:: lines

        List of either :class:`PassEntry` or :class:`PassFile`. You can add
        lines by appending :class:`PassEntry` or :class:`PassFile` instances to
        this list.

    """

    lines = []

    def __init__(self):
        self.lines = []

    def __iter__(self):
        """Iterate entries

        Yield :class:`PassEntry` instance from parsed file, ignoring comments.
        """
        return iter(filter(lambda l: isinstance(l, PassEntry), self.lines))

    def parse(self, fo):
        """Parse lines

        :param fo: A line iterator such as a file-like object.

        Raises ``ParseError`` if a bad line is found.
        """
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
        """Sort entries preserving comments.

        libpq use the first entry from .pgpass matching connexion informations.
        Thus, less specific entries should be last in the file. This is the
        purpose of :func:`sort` method.

        About comments. Comments are supposed to bear with the entrie
        **below**. Thus comments block are sorted according to the first entry
        below.

        Commented entries are sorted like entries, not like comment.
        """
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
        """Save entries and comment in a file.

        :param fo: a file-like object.
        """
        for line in self.lines:
            fo.write(str(line) + os.linesep)


def parse(fo):
    """Parses a .pgpass file.

    :param fo: A line iterator such as a file-like object.
    :rtype: :class:`PassFile`
    """
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
