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
.. autofunction:: edit
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

Shorter version using the file directly in `parse`:

.. code:: python

    pgpass = parse('.pgpass')
    pgpass.lines.append(PassEntry(username='toto', password='confidentiel'))
    pgpass.sort()
    pgpass.save()

Alternatively, this can be done with the `edit` context manager:

.. code:: python

    with edit('.pgpass') as pgpass:
        pgpass.lines.append((PassEntry(username='toto', password='confidentiel'))
        passfile.sort()


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

import os
import sys
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Callable, Iterable, Iterator, List, Optional, Tuple, Union

from ._helpers import open_or_stdin
from .errors import ParseError


def unescape(s: str, delim: str) -> str:
    return s.replace("\\" + delim, delim).replace("\\\\", "\\")


def escapedsplit(s: str, delim: str) -> Iterator[str]:
    if len(delim) != 1:
        raise ValueError("Invalid delimiter: " + delim)

    ln = len(s)
    escaped = False
    i = 0
    j = 0

    while j < ln:
        if s[j] == "\\":
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

    .. automethod:: matches

    .. attribute:: comment

        The actual message of the comment. Surrounding whitespaces stripped.

    """

    def __repr__(self) -> str:
        return "<%s %.32s>" % (self.__class__.__name__, self)

    def __lt__(self, other: str) -> bool:
        if isinstance(other, PassEntry):
            try:
                return self.entry < other
            except ValueError:
                pass
        return False

    @property
    def comment(self) -> str:
        return self.lstrip("#").strip()

    @property
    def entry(self) -> "PassEntry":
        if not hasattr(self, "_entry"):
            self._entry = PassEntry.parse(self.comment)
        return self._entry

    def matches(self, **attrs: Union[int, str]) -> bool:
        """In case of a commented entry, tells if it is matching provided
        attributes. Returns False otherwise.

        :param attrs: keyword/values pairs correspond to one or more
            PassEntry attributes (ie. hostname, port, etc...)
        """
        try:
            return self.entry.matches(**attrs)
        except ValueError:
            return False


class PassEntry:
    """Holds a .pgpass entry.

    .. automethod:: parse
    .. automethod:: matches

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
    def parse(cls, line: str) -> "PassEntry":
        """Parse a single line.

        :param line: string containing a serialized .pgpass entry.
        :return: :class:`PassEntry` object holding entry data.
        :raises ValueError: on invalid line.
        """
        fields = list(escapedsplit(line.strip(), ":"))
        if len(fields) != 5:
            raise ValueError("Invalid line.")
        if fields[1] != "*":
            fields[1] = int(fields[1])  # type: ignore[call-overload]
        return cls(*fields)

    def __init__(
        self,
        hostname: str,
        port: Union[int, str],
        database: str,
        username: str,
        password: str,
    ) -> None:
        self.hostname = hostname
        self.port = port
        self.database = database
        self.username = username
        self.password = password

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PassComment):
            try:
                other = other.entry
            except ValueError:
                return False
        if isinstance(other, PassEntry):
            return self.as_tuple()[:-1] == other.as_tuple()[:-1]
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.as_tuple()[:-1])

    def __lt__(self, other: Union[PassComment, "PassEntry"]) -> bool:
        if isinstance(other, PassComment):
            try:
                other = other.entry
            except ValueError:
                return False
        if isinstance(other, PassEntry):
            return self.sort_key() < other.sort_key()
        return NotImplemented

    def __repr__(self) -> str:
        return "<%s %s@%s:%s/%s>" % (
            self.__class__.__name__,
            self.username,
            self.hostname,
            self.port,
            self.database,
        )

    def __str__(self) -> str:
        return ":".join(
            [str(x).replace("\\", r"\\").replace(":", r"\:") for x in self.as_tuple()]
        )

    def as_tuple(self) -> Tuple[str, str, str, str, str]:
        return (
            self.hostname,
            str(self.port),
            self.database,
            self.username,
            self.password,
        )

    def sort_key(self) -> Tuple[int, str, Union[int, str], str, str]:
        tpl = self.as_tuple()[:-1]
        # Compute precision from * occurences.
        precision = len([x for x in tpl if x == "*"])
        # More specific entries comes first.
        return (precision,) + tuple(chr(0xFF) if x == "*" else x for x in tpl)  # type: ignore[return-value]

    def matches(self, **attrs: Union[int, str]) -> bool:
        """Tells if the current entry is matching provided attributes.

        :param attrs: keyword/values pairs correspond to one or more
            PassEntry attributes (ie. hostname, port, etc...)
        """

        # Provided attributes should be comparable to PassEntry attributes
        expected_attributes = self.__dict__.keys()
        for k in attrs.keys():
            if k not in expected_attributes:
                raise AttributeError("%s is not a valid attribute" % k)

        for k, v in attrs.items():
            if getattr(self, k) != v:
                return False
        return True


class PassFile:
    """Holds .pgpass file entries and comments.

    .. automethod:: parse
    .. automethod:: __iter__
    .. automethod:: sort
    .. automethod:: save
    .. automethod:: remove

    .. attribute:: lines

        List of either :class:`PassEntry` or :class:`PassFile`. You can add
        lines by appending :class:`PassEntry` or :class:`PassFile` instances to
        this list.

    .. attribute:: path

        Path to a file. Is automatically set when calling :meth:`parse` with a
        path to a file. :meth:`save` will write to this file if set.

    """

    lines: List[Union[PassComment, PassEntry]]
    path: Optional[str] = None

    def __init__(
        self,
        entries: Optional[List[Union[PassComment, PassEntry]]] = None,
        *,
        path: Optional[str] = None,
    ) -> None:
        """PassFile constructor.

        :param entries: A list of PassEntry or PassComment. Optional.
        """
        if entries and not isinstance(entries, list):
            raise ValueError("%s should be a list" % entries)
        self.lines = entries or []
        self.path = path

    def __iter__(self) -> Iterator[PassEntry]:
        """Iterate entries

        Yield :class:`PassEntry` instance from parsed file, ignoring comments.
        """
        for line in self.lines:
            if isinstance(line, PassEntry):
                yield line

    def parse(self, fo: Iterable[str]) -> None:
        """Parse lines

        :param fo: A line iterator such as a file-like object.

        Raises ``ParseError`` if a bad line is found.
        """
        entry: Union[PassComment, PassEntry]
        for i, line in enumerate(fo):
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                entry = PassComment(line.replace(os.linesep, ""))
            else:
                try:
                    entry = PassEntry.parse(line)
                except Exception as e:
                    raise ParseError(1 + i, line, str(e))
            self.lines.append(entry)

    def sort(self) -> None:
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

        self.lines[:] = []
        if not entries and comments:
            # no entry, only comments
            self.lines.extend(comments)
        else:
            entries.sort()
            for entry, comments in entries:
                self.lines.extend(comments)
                self.lines.append(entry)

    def save(self, fo: Optional[IO[str]] = None) -> None:
        """Save entries and comment in a file.

        :param fo: a file-like object. Is not required if :attr:`path` is set.
        """

        def _write(fo: IO[str], lines: Iterable[object]) -> None:
            for line in lines:
                fo.write(str(line) + os.linesep)

        if fo:
            _write(fo, self.lines)
        elif self.path:
            fpath = Path(self.path)
            if not fpath.exists():
                if not self.lines:
                    return
                fpath.touch(mode=0o600)
            with open(self.path, "w") as fo:
                _write(fo, self.lines)
        else:
            raise ValueError("No file-like object nor path provided")

    def remove(
        self,
        filter: Optional[Callable[[Union[PassComment, PassEntry, str]], bool]] = None,
        **attrs: Union[int, str],
    ) -> None:
        """Remove entries matching the provided attributes.

        One can for example remove all entries for which port is 5433.

        Note: commented entries matching will also be removed.

        :param filter: a function to be used as filter. It is passed the line
             to test against. If it returns True, the line is removed. It is
             kept otherwise.
        :param attrs: keyword/values pairs correspond to one or more
            PassEntry attributes (ie. hostname, port, etc...)

        Usage examples:

        .. code:: python

            pgpass.remove(port=5432)
            pgpass.remove(filter=lambda r: r.port != 5432)
        """
        if filter is not None and len(attrs):
            warnings.warn("Only filter will be taken into account")

        # Attributes list to look for must not be empty
        if filter is None and not len(attrs.keys()):
            raise ValueError("Attributes dict cannot be empty")

        if filter is not None:
            # Silently handle the case when line is a PassComment
            def filter_(line: Union[PassComment, PassEntry]) -> bool:
                if isinstance(line, PassComment):
                    try:
                        return filter(line.entry)  # type: ignore[misc]
                    except ValueError:
                        return False
                else:
                    return filter(line)  # type: ignore[misc]

        else:

            def filter_(line: Union[PassComment, PassEntry]) -> bool:
                return line.matches(**attrs)

        self.lines = [line for line in self.lines if not filter_(line)]


def parse(file: Union[Path, str, IO[str]]) -> PassFile:
    """Parses a .pgpass file.

    :param file: Either a line iterator such as a file-like object or a file
        path to open and parse.
    :rtype: :class:`PassFile`
    """
    if isinstance(file, (Path, str)):
        with open(os.path.expanduser(file)) as fo:
            pgpass = parse(fo)
            pgpass.path = str(file)
    else:
        pgpass = PassFile()
        pgpass.parse(file)
    return pgpass


@contextmanager
def edit(fpath: Union[Path, str]) -> Iterator[PassFile]:
    """Context manager to edit a .pgpass file.

    If the file does not exists, it is created with 600 permissions.
    Upon exit of the context manager, the file is saved, if no error occurred.
    """
    fpath = Path(fpath).expanduser()
    if fpath.exists():
        passfile = parse(fpath)
    else:
        passfile = PassFile(path=str(fpath))
    yield passfile
    passfile.save()


if __name__ == "__main__":  # pragma: nocover
    argv = sys.argv[1:] + ["-"]
    try:
        with open_or_stdin(argv[0]) as fo:
            pgpass = parse(fo)
        pgpass.sort()
        pgpass.save(sys.stdout)
    except Exception as e:
        print(str(e), file=sys.stderr)
        exit(1)
