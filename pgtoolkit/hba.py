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

    pgpass = parse('my_pg_hba.conf')

You can also pass a file-object:

.. code:: python

    with open('my_pg_hba.conf', 'r') as fo:
        hba = parse(fo)

Creating a ``pg_hba.conf`` file from scratch :

.. code:: python

    hba = HBA()
    record = HBARecord(
        conntype='local', database='all', user='all', method='peer',
    )
    hba.lines.append(record)

    with open('pg_hba.conf', 'w') as fo:
        hba.save(fo)


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

from __future__ import annotations

import os
import re
import sys
import warnings
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

from ._helpers import open_or_return, open_or_stdin
from .errors import ParseError


class HBAComment(str):
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self:.32}>"


class HBARecord:
    """Holds a HBA record composed of fields and a comment.

    Common fields are accessible through attribute : ``conntype``,
    ``database``, ``user``, ``address``, ``netmask``, ``method``.
    Auth-options fields are also accessible through attribute like ``map``,
    ``ldapserver``, etc.

    ``address`` and ``netmask`` fields are not always defined. If not,
    accessing undefined attributes trigger an :exc:`AttributeError`.

    .. automethod:: parse
    .. automethod:: __init__
    .. automethod:: __str__
    .. automethod:: matches
    .. autoattribute:: database
    .. autoattribute:: user

    """

    COMMON_FIELDS = [
        "conntype",
        "database",
        "user",
        "address",
        "netmask",
        "method",
    ]
    CONNECTION_TYPES = [
        "local",
        "host",
        "hostssl",
        "hostnossl",
        "hostgssenc",
        "hostnogssenc",
    ]

    @classmethod
    def parse(cls, line: str) -> HBARecord:
        """Parse a HBA record

        :rtype: :class:`HBARecord` or a :class:`str` for a comment or blank
                line.
        :raises ValueError: If connection type is wrong.

        """
        line = line.strip()
        record_fields = ["conntype", "database", "user"]

        # What the regexp below does is finding all elements separated by spaces
        # unless they are enclosed in double-quotes
        # (?: … )+ = non-capturing group
        # \"+.*?\"+ = any element with or without spaces enclosed within
        #             double-quotes (alternative 1)
        # \S = any non-whitespace character (alternative 2)
        values = [p for p in re.findall(r"(?:\"+.*?\"+|\S)+", line) if p.strip()]
        assert len(values) > 2
        try:
            hash_pos = values.index("#")
        except ValueError:
            comment = None
        else:
            values, comments = values[:hash_pos], values[hash_pos:]
            comment = " ".join(comments[1:])

        if values[0] not in cls.CONNECTION_TYPES:
            raise ValueError("Unknown connection type '%s'" % values[0])
        if "local" != values[0]:
            record_fields.append("address")
        common_values = [v for v in values if "=" not in v]
        if len(common_values) >= 6:
            record_fields.append("netmask")
        record_fields.append("method")
        base_options = list(zip(record_fields, values[: len(record_fields)]))
        auth_options = [o.split("=", 1) for o in values[len(record_fields) :]]
        # Remove extra outer double quotes for auth options values if any
        auth_options = [(o[0], re.sub(r"^\"|\"$", "", o[1])) for o in auth_options]
        options = base_options + auth_options
        return cls(**{k: v for k, v in options}, comment=comment)

    conntype: str | None
    database: str
    user: str

    def __init__(self, *, comment: str | None = None, **values: Any) -> None:
        """
        :param comment: Optional comment.
        :param values: Fields passed as keyword.
        """
        self.__dict__.update(values)
        self.comment = comment
        self.fields = list(values)

    def __repr__(self) -> str:
        return "<{} {}{}>".format(
            self.__class__.__name__,
            " ".join(self.common_values),
            "..." if self.auth_options else "",
        )

    def __str__(self) -> str:
        """Serialize a record line, without EOL."""
        # Stolen from default pg_hba.conf
        widths = [8, 16, 16, 16, 8]

        fmt = ""
        for i, field_ in enumerate(self.COMMON_FIELDS):
            try:
                width = widths[i]
            except IndexError:
                width = 0

            if field_ not in self.fields:
                fmt += " " * width
                continue

            if width:
                fmt += "%%(%s)-%ds " % (field_, width - 1)
            else:
                fmt += f"%({field_})s "
        line = fmt.rstrip() % self.__dict__

        auth_options = ['%s="%s"' % i for i in self.auth_options]
        if auth_options:
            line += " " + " ".join(auth_options)

        if self.comment is not None:
            line += "  # " + self.comment
        else:
            line = line.rstrip()

        return line

    def __eq__(self, other: object) -> bool:
        return str(self) == str(other)

    def as_dict(self) -> dict[str, Any]:
        str_fields = self.COMMON_FIELDS[:]
        return {f: getattr(self, f) for f in str_fields if hasattr(self, f)}

    @property
    def common_values(self) -> list[str]:
        str_fields = self.COMMON_FIELDS[:]
        return [getattr(self, f) for f in str_fields if f in self.fields]

    @property
    def auth_options(self) -> list[tuple[str, str]]:
        return [
            (f, getattr(self, f)) for f in self.fields if f not in self.COMMON_FIELDS
        ]

    @property
    def databases(self) -> list[str]:
        return self.database.split(",")

    @property
    def users(self) -> list[str]:
        return self.user.split(",")

    def matches(self, **attrs: str) -> bool:
        """Tells if the current record is matching provided attributes.

        :param attrs: keyword/values pairs corresponding to one or more
            HBARecord attributes (ie. user, conntype, etc…)
        """

        # Provided attributes should be comparable to HBARecord attributes
        for k in attrs.keys():
            if k not in self.COMMON_FIELDS + ["database", "user"]:
                raise AttributeError("%s is not a valid attribute" % k)

        for k, v in attrs.items():
            if getattr(self, k, None) != v:
                return False
        return True


@dataclass
class HBA:
    """Represents pg_hba.conf records

    .. attribute:: lines

        List of :class:`HBARecord` and comments.

    .. attribute:: path

        Path to a file. Is automatically set when calling :meth:`parse` with a
        path to a file. :meth:`save` will write to this file if set.

    .. automethod:: __iter__
    .. automethod:: parse
    .. automethod:: save
    .. automethod:: remove
    .. automethod:: merge
    """

    lines: list[HBAComment | HBARecord] = field(default_factory=list)
    path: str | Path | None = None

    def __iter__(self) -> Iterator[HBARecord]:
        """Iterate on records, ignoring comments and blank lines."""
        for line in self.lines:
            if isinstance(line, HBARecord):
                yield line

    def parse(self, fo: Iterable[str]) -> None:
        """Parse records and comments from file object

        :param fo: An iterable returning lines
        """
        for i, line in enumerate(fo):
            stripped = line.lstrip()
            record: HBARecord | HBAComment
            if not stripped or stripped.startswith("#"):
                record = HBAComment(line.replace(os.linesep, ""))
            else:
                try:
                    record = HBARecord.parse(line)
                except Exception as e:
                    raise ParseError(1 + i, line, str(e))
            self.lines.append(record)

    def save(self, fo: str | Path | IO[str] | None = None) -> None:
        """Write records and comments in a file

        :param fo: a file-like object. Is not required if :attr:`path` is set.

        Line order is preserved. Record fields are vertically aligned to match
        the columen size of column headers from default configuration file.

        .. code::

            # TYPE  DATABASE        USER            ADDRESS                 METHOD
            local   all             all                                     trust
        """  # noqa
        with open_or_return(fo or self.path, mode="w") as fo:
            for line in self.lines:
                fo.write(str(line) + os.linesep)

    def remove(
        self,
        filter: Callable[[HBARecord], bool] | None = None,
        **attrs: str,
    ) -> bool:
        """Remove records matching the provided attributes.

        One can for example remove all records for which user is 'david'.

        :param filter: a function to be used as filter. It is passed the record
            to test against. If it returns True, the record is removed. It is
            kept otherwise.
        :param attrs: keyword/values pairs correspond to one or more
            HBARecord attributes (ie. user, conntype, etc...)

        :returns: ``True`` if records have changed.

        Usage examples:

        .. code:: python

            hba.remove(filter=lamdba r: r.user == 'david')
            hba.remove(user='david')

        """
        if filter is not None and len(attrs.keys()):
            warnings.warn("Only filter will be taken into account")

        # Attributes list to look for must not be empty
        if filter is None and not len(attrs.keys()):
            raise ValueError("Attributes dict cannot be empty")

        filter = filter or (lambda line: line.matches(**attrs))

        lines_before = self.lines

        self.lines = [
            line
            for line in self.lines
            if not (isinstance(line, HBARecord) and filter(line))
        ]

        return lines_before != self.lines

    def merge(self, other: HBA) -> bool:
        """Add new records to HBAFile or replace them if they are matching
            (ie. same conntype, database, user and address)

        :param other: HBAFile to merge into the current one.
            Lines with matching conntype, database, user and database will be
            replaced by the new one. Otherwise they will be added at the end.
            Comments from the original hba are preserved.

        :returns: ``True`` if records have changed.
        """
        lines = self.lines[:]
        new_lines = other.lines[:]
        other_comments = []

        for i, line in enumerate(lines):
            if isinstance(line, HBAComment):
                continue
            for new_line in new_lines:
                if isinstance(new_line, HBAComment):
                    # preserve comments until next record
                    other_comments.append(new_line)
                else:
                    kwargs = dict()
                    for a in ["conntype", "database", "user", "address"]:
                        if hasattr(new_line, a):
                            kwargs[a] = getattr(new_line, a)
                    if line.matches(**kwargs):
                        # replace matched line with comments + record
                        self.lines[i : i + 1] = other_comments + [new_line]
                        for c in other_comments:
                            new_lines.remove(c)
                        new_lines.remove(new_line)
                        break  # found match, go to next line
                    other_comments[:] = []
        # Then add remaining new lines (not merged)
        self.lines.extend(new_lines)

        return lines != self.lines


def parse(file: str | Iterable[str] | Path) -> HBA:
    """Parse a `pg_hba.conf` file.

    :param file: Either a line iterator such as a file-like object, a path or a string
        corresponding to the path to the file to open and parse.
    :rtype: :class:`HBA`.
    """
    if isinstance(file, (str, Path)):
        with open(file) as fo:
            hba = parse(fo)
            hba.path = file
    else:
        hba = HBA()
        hba.parse(file)
    return hba


if __name__ == "__main__":  # pragma: nocover
    argv = sys.argv[1:] + ["-"]
    try:
        with open_or_stdin(argv[0]) as fo:
            hba = parse(fo)
        hba.save(sys.stdout)
    except Exception as e:
        print(str(e), file=sys.stderr)
        exit(1)
