# coding: utf-8

""".. currentmodule:: pgtoolkit.hba

This module supports reading, validating, editing and rendering ``pg_hba.conf``
file. See `Client Authentication
<https://www.postgresql.org/docs/current/static/auth-pg-hba-conf.html>`__ in
PostgreSQL documentation for details on format and values of ``pg_hba.conf``
file.


API Reference
-------------

The main entrypoint of this API is the :func:`parse` function. It returns a
:class:`HBA` object containing :class:`HBARecord` instances.

.. autofunction:: parse
.. autoclass:: HBA
.. autoclass:: HBARecord


Examples
--------

Loading a ``pg_hba.conf`` file :

.. code:: python

    hba = 'my_pg_hba.conf'
    with open(hba, 'r') as fo:
        hba = parse(fo)
    for record in hba:
        print(record.database, record.user)

Shorter version using the file directly in `parse`:

.. code:: python

    pgpass = parse('my_pg_hba.conf')


Creating a ``pg_hba.conf`` file from scratch :

.. code:: python

    hba = HBA()
    hba.lines.append(HBARecord(conntype='local', database='all', user='all', method='peer'))
    with open('pg_hba.conf', 'w') as fo:
        hba.write(fo)


Using as a script
-----------------

:mod:`pgtoolkit.hba` is usable as a CLI script. It accepts a pg_hba file path
as first argument, read it, validate it and re-render it. Fields are aligned to
fit pseudo-column width. If filename is ``-``, stdin is read instead.

.. code:: console

    $ python -m pgtoolkit.hba - < data/pg_hba.conf
    # TYPE  DATABASE        USER            ADDRESS                 METHOD

    # "local" is for Unix domain socket connections only
    local   all             all                                     trust
    # IPv4 local connections:
    host    all             all             127.0.0.1/32            ident map=omicron

"""  # noqa


from __future__ import print_function

import os
import shlex
import sys

from .errors import ParseError
from ._helpers import open_or_stdin


class HBAComment(str):
    def __repr__(self):
        return '<%s %.32s>' % (self.__class__.__name__, self)


class HBARecord(object):
    """Holds a HBA record

    Known fields are accessible through attribute : ``conntype``, ``database``,
    ``user``, ``address``, ``netmask``, ``method``. Auth-options fields are
    also accessible through attribute like ``map``, ``ldapserver``, etc.

    .. automethod:: parse
    .. automethod:: __init__
    .. automethod:: __str__

    """

    CONNECTION_TYPES = ['local', 'host', 'hostssl', 'hostnossl']
    KNOWN_FIELDS = [
        'conntype', 'database', 'user', 'address', 'netmask', 'method',
    ]

    @classmethod
    def parse(cls, line):
        """Parse a HBA record

        :rtype: :class:`HBARecord` or a :class:`str` for a comment or blank
                line.
        :raises ValueError: If connection type is wrong.

        """
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

    def __init__(self, values=None, comment=None, **kw_values):
        """
        :param values: A dict of fields.
        :param kw_values: Fields passed as keyword.
        :param comment:  Comment at the end of the line.
        """
        values = dict(values or {}, **kw_values)
        self.__dict__.update(values)
        self.fields = [k for k, _ in values.items()]
        self.comment = comment

    def __repr__(self):
        return '<%s %s%s>' % (
            self.__class__.__name__,
            ' '.join(self.known_values),
            '...' if self.auth_options else ''
        )

    def __str__(self):
        """Serialize a record line, without EOL."""
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
    """Represents pg_hba.conf records

    .. attribute:: lines

        List of :class:`HBARecord` and comments.

    .. attribute:: path

        Path to a file. Is automatically set when calling :meth:`parse` with a
        path to a file. :meth:`save` will write to this file if set.

    .. automethod:: __iter__
    .. automethod:: parse
    .. automethod:: save
    """
    def __init__(self):
        self.lines = []
        self.path = None

    def __iter__(self):
        """Iterate on records, ignoring comments and blank lines."""
        return iter(filter(lambda l: isinstance(l, HBARecord), self.lines))

    def parse(self, fo):
        """Parse records and comments from file object

        :param fo: An iterable returning lines
        """
        for i, line in enumerate(fo):
            stripped = line.lstrip()
            if not stripped or stripped.startswith('#'):
                record = HBAComment(line.replace(os.linesep, ''))
            else:
                try:
                    record = HBARecord.parse(line)
                except Exception as e:
                    raise ParseError(1 + i, line, str(e))
            self.lines.append(record)

    def save(self, fo=None):
        """Write records and comments in a file

        :param fo: a file-like object. Is not required if :attr:`path` is set.

        Line order is preserved. Record fields are vertically aligned to match
        the columen size of column headers from default configuration file.

        .. code::

            # TYPE  DATABASE        USER            ADDRESS                 METHOD
            local   all             all                                     trust
        """  # noqa
        def _write(fo, lines):
            for line in lines:
                fo.write(str(line) + os.linesep)

        if fo:
            _write(fo, self.lines)
        elif self.path:
            with open(self.path, 'w') as fo:
                _write(fo, self.lines)
        else:
            raise ValueError('No file-like object nor path provided')


def parse(file):
    """Parse a `pg_hba.conf` file.

    :param file: Either a line iterator such as a file-like object or a string
        corresponding to the path to the file to open and parse.
    :rtype: :class:`HBA`.
    """
    if isinstance(file, str):
        with open(file) as fo:
            hba = parse(fo)
            hba.path = file
    else:
        hba = HBA()
        hba.parse(file)
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
