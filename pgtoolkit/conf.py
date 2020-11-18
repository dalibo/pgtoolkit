"""\
.. currentmodule:: pgtoolkit.conf

This module implements ``postgresql.conf`` file format. This is the same format
for ``recovery.conf``. The main entry point of the API is :func:`parse`. The
module can be used as a CLI script.


API Reference
-------------

.. autofunction:: parse
.. autoclass:: Configuration


Using as a CLI Script
---------------------

You can use this module to dump a configuration file as JSON object

.. code:: console

    $ python -m pgtoolkit.conf postgresql.conf | jq .
    {
      "lc_monetary": "fr_FR.UTF8",
      "datestyle": "iso, dmy",
      "log_rotation_age": "1d",
      "log_min_duration_statement": "3s",
      "log_lock_waits": true,
      "log_min_messages": "notice",
      "log_directory": "log",
      "port": 5432,
      "log_truncate_on_rotation": true,
      "log_rotation_size": 0
    }
    $

"""


import contextlib
import copy
import enum
import json
from collections import OrderedDict
import pathlib
import re
import sys
from datetime import timedelta
from typing import (
    Any,
    Dict,
    IO,
    Iterable,
    Iterator,
    List,
    NoReturn,
    Optional,
    Tuple,
    Union,
)

from ._helpers import JSONDateEncoder
from ._helpers import open_or_return


class IncludeType(enum.Enum):
    """Include directive types.

    https://www.postgresql.org/docs/13/config-setting.html#CONFIG-INCLUDES
    """
    include_dir = enum.auto()
    include_if_exists = enum.auto()
    include = enum.auto()


def parse(fo: Union[str, IO[str]]) -> "Configuration":
    """Parse a configuration file.

    The parser tries to return Python object corresponding to value, based on
    some heuristics. booleans, octal number, decimal integers and floating
    point numbers are parsed. Multiplier units like kB or MB are applyied and
    you get an int. Interval value like ``3s`` are returned as
    :class:`datetime.timedelta`.

    In case of doubt, the value is kept as a string. It's up to you to enforce
    format.

    Include directives are processed recursively, when 'fo' is a file path (not
    a file object). If some included file is not found a FileNotFoundError
    exception is raised. If a loop is detected in include directives, a
    RuntimeError is raised.

    :param fo: A line iterator such as a file-like object or a path.
    :returns: A :class:`Configuration` containing parsed configuration.

    """
    conf = Configuration()
    with open_or_return(fo) as f:
        includes_top = conf.parse(f)
        conf.path = getattr(f, 'name', None)

    if not includes_top:
        return conf

    if not isinstance(fo, str):
        raise ValueError(
            "cannot process include directives from a file argument; "
            "try passing a file path"
        )

    def absolute(
        path: pathlib.Path, relative_to: pathlib.Path
    ) -> pathlib.Path:
        """Make 'path' absolute by joining from 'relative_to' path."""
        if path.is_absolute():
            return path
        assert relative_to.is_absolute()
        if relative_to.is_file():
            relative_to = relative_to.parent
        return relative_to / path

    def make_includes(
        includes: List[Tuple[pathlib.Path, IncludeType]],
        reference_path: pathlib.Path,
    ) -> List[Tuple[pathlib.Path, pathlib.Path, IncludeType]]:
        return [
            (absolute(path, reference_path), reference_path, include_type)
            for path, include_type in includes
        ]

    def parse_include(path: pathlib.Path) -> None:
        with path.open() as f:
            includes.extend(make_includes(conf.parse(f), path.parent))

    def notfound(
        path: pathlib.Path,
        include_type: str,
        reference_path: pathlib.Path
    ) -> FileNotFoundError:
        return FileNotFoundError(
            f"{include_type} '{path}', included from '{reference_path}',"
            " not found"
        )

    includes = make_includes(includes_top, pathlib.Path(fo).absolute())
    processed = set()
    while includes:
        path, reference_path, include_type = includes.pop()

        if path in processed:
            raise RuntimeError(
                f"loop detected in include directive about '{path}'"
            )
        processed.add(path)

        if include_type == IncludeType.include_dir:
            if not path.exists() or not path.is_dir():
                raise notfound(path, "directory", reference_path)
            for confpath in path.glob("*.conf"):
                if not confpath.name.startswith("."):
                    parse_include(confpath)

        elif include_type == IncludeType.include_if_exists:
            if path.exists():
                parse_include(path)

        elif include_type == IncludeType.include:
            if not path.exists():
                raise notfound(path, "file", reference_path)
            parse_include(path)

        else:
            assert False, include_type  # pragma: nocover

    return conf


MEMORY_MULTIPLIERS = {
    'kB': 1024,
    'MB': 1024 * 1024,
    'GB': 1024 * 1024 * 1024,
    'TB': 1024 * 1024 * 1024 * 1024,
}
_memory_re = re.compile(r'^\s*(?P<number>\d+)\s*(?P<unit>[kMGT]B)\s*$')
TIMEDELTA_ARGNAME = {
    'ms': 'milliseconds',
    's': 'seconds',
    'min': 'minutes',
    'h': 'hours',
    'd': 'days',
}
_timedelta_re = re.compile(r'^\s*(?P<number>\d+)\s*(?P<unit>ms|s|min|h|d)\s*$')


Value = Union[str, bool, float, int, timedelta]


def parse_value(raw: str) -> Value:
    # Ref.
    # https://www.postgresql.org/docs/current/static/config-setting.html#CONFIG-SETTING-NAMES-VALUES

    if raw.startswith("'"):
        if not raw.endswith("'"):
            raise ValueError(raw)
        # unquote value and unescape quotes
        raw = raw[1:-1].replace("''", "'").replace(r"\'", "'")

    if raw.startswith('0'):
        try:
            return int(raw, base=8)
        except ValueError:
            pass

    m = _memory_re.match(raw)
    if m:
        unit = m.group('unit')
        mul = MEMORY_MULTIPLIERS[unit]
        return int(m.group('number')) * mul

    m = _timedelta_re.match(raw)
    if m:
        unit = m.group('unit')
        arg = TIMEDELTA_ARGNAME[unit]
        kwargs = {arg: int(m.group('number'))}
        return timedelta(**kwargs)

    elif raw in ('true', 'yes', 'on'):
        return True
    elif raw in ('false', 'no', 'off'):
        return False
    else:
        try:
            return int(raw)
        except ValueError:
            try:
                return float(raw)
            except ValueError:
                return raw


class Entry:
    # Holds the parsed representation of a configuration entry line.
    #
    # This includes the comment.

    def __init__(
        self,
        name: str,
        value: Value,
        commented: bool = False,
        comment: Optional[str] = None,
        raw_line: Optional[str] = None,
    ) -> None:
        self._name = name
        if isinstance(value, str):
            value = parse_value(value)
        self._value = value
        self.commented = commented
        self.comment = comment
        # Store the raw_line to track the position in the list of lines.
        if raw_line is None:
            raw_line = str(self) + '\n'
        self.raw_line = raw_line

    @property
    def name(self) -> str:
        return self._name

    @property
    def value(self) -> Value:
        return self._value

    @value.setter
    def value(self, value: Union[str, Value]) -> None:
        if isinstance(value, str):
            value = parse_value(value)
        self._value = value

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Entry):
            return NotImplemented  # pragma: nocover
        return (
            self.name == other.name
            and self.value == other.value
            and self.comment == other.comment
            and self.commented == other.commented
        )

    def __repr__(self) -> str:
        return '<%s %s=%s>' % (self.__class__.__name__, self.name, self.value)

    _minute = 60
    _hour = 60 * _minute
    _day = 24 * _hour

    _timedelta_unit_map = [
        ('d', _day),
        ('h', _hour),
        # The space before 'min' is intentionnal. I find '1 min' more readable
        # than '1min'.
        (' min', _minute),
        ('s', 1),
    ]

    def serialize(self) -> Union[int, str]:
        # This is the reverse of parse_value.
        value = self.value
        if isinstance(value, bool):
            value = 'on' if value else 'off'
        elif isinstance(value, int) and value != 0:
            for unit in None, 'kB', 'MB', 'GB', 'TB':
                if value % 1024:
                    break
                value = value // 1024
            if unit:
                value = "%s%s" % (value, unit)
        elif isinstance(value, str):
            # Only quote if not already quoted.
            if not (value.startswith("'") and value.endswith("'")):
                # Only double quotes, if not already done; we assume this is
                # done everywhere in the string or nowhere.
                if "''" not in value and r"\'" not in value:
                    value = value.replace("'", "''")
                value = "'%s'" % value
        elif isinstance(value, timedelta):
            seconds = value.days * self._day + value.seconds
            if value.microseconds:
                unit = ' ms'
                value = seconds * 1000 + value.microseconds // 1000
            else:
                for unit, mod in self._timedelta_unit_map:
                    if seconds % mod:
                        continue
                    value = seconds // mod
                    break
            value = "'%s%s'" % (value, unit)
        else:
            value = str(value)
        return value

    def __str__(self) -> str:
        line = '%(name)s = %(value)s' % dict(
            name=self.name, value=self.serialize())
        if self.comment:
            line += '  # ' + self.comment
        if self.commented:
            line = '#' + line
        return line


class EntriesProxy(Dict[str, Entry]):
    """Proxy object used during Configuration edition.

    >>> p = EntriesProxy(port=Entry('port', '5432'),
    ...                  shared_buffers=Entry('shared_buffers', '1GB'))

    Existing entries can be edited:

    >>> p['port'].value = '5433'

    New entries can be added as:

    >>> p.add('listen_addresses', '*', commented=True, comment='IP address')
    >>> p  # doctest: +NORMALIZE_WHITESPACE
    {'port': <Entry port=5433>,
     'shared_buffers': <Entry shared_buffers=1073741824>,
     'listen_addresses': <Entry listen_addresses=*>}
    >>> del p['shared_buffers']
    >>> p
    {'port': <Entry port=5433>, 'listen_addresses': <Entry listen_addresses=*>}

    Adding an existing entry fails:
    >>> p.add('port', 5433)
    Traceback (most recent call last):
        ...
    ValueError: 'port' key already present

    So does adding a value to the underlying dict:
    >>> p['bonjour_name'] = 'pgserver'
    Traceback (most recent call last):
        ...
    TypeError: cannot set a key
    """

    def __setitem__(self, key: str, value: Any) -> NoReturn:
        raise TypeError("cannot set a key")

    def add(
        self,
        name: str,
        value: Value,
        *,
        commented: bool = False,
        comment: Optional[str] = None,
    ) -> None:
        """Add a new entry."""
        if name in self:
            raise ValueError(f"'{name}' key already present")
        entry = Entry(name, value, commented=commented, comment=comment)
        super().__setitem__(name, entry)


class Configuration:
    r"""Holds a parsed configuration.

    You can access parameter using attribute or dictionnary syntax.

    >>> conf = parse(['port=5432\n', 'pg_stat_statement.min_duration = 3s\n'])
    >>> conf.port
    5432
    >>> conf.port = 5433
    >>> conf.port
    5433
    >>> conf['port'] = 5434
    >>> conf.port
    5434
    >>> conf['pg_stat_statement.min_duration'].total_seconds()
    3.0

    .. attribute:: path

        Path to a file. Automatically set when calling :func:`parse` with a path
        to a file. This is default target for :meth:`save`.

    .. automethod:: save

    """  # noqa
    lines: List[str]
    entries: Dict[str, Entry]
    path: Optional[str]

    _parameter_re = re.compile(
        r'^(?P<name>[a-z_.]+)(?: +(?!=)| *= *)(?P<value>.*?)'
        '[\\s\t]*'
        r'(?P<comment>#.*)?$'
    )

    # Internally, lines property contains an updated list of all comments and
    # entries serialized. When adding a setting or updating an existing one,
    # the serialized line is updated accordingly. This allows to keep comments
    # and serialize only what's needed. Other lines are just written as-is.

    def __init__(self) -> None:
        self.__dict__.update(dict(
            lines=[],
            entries=OrderedDict(),
            path=None,
        ))

    def parse(
        self, fo: Iterable[str]
    ) -> List[Tuple[pathlib.Path, IncludeType]]:
        includes = []
        for raw_line in fo:
            self.lines.append(raw_line)
            line = raw_line.strip()
            if not line:
                continue
            commented = False
            if line.startswith('#'):
                # Try to parse the uncommented line.
                line = line.lstrip('#').lstrip()
                m = self._parameter_re.match(line)
                if not m:
                    # This is a real comment
                    continue
                commented = True
            else:
                m = self._parameter_re.match(line)
                if not m:
                    raise ValueError("Bad line: %r." % raw_line)
            kwargs = m.groupdict()
            name = kwargs.pop('name')
            value = parse_value(kwargs.pop('value'))
            comment = kwargs['comment']
            if comment is not None:
                kwargs['comment'] = comment.lstrip('#').lstrip()
            if name in IncludeType.__members__ and not commented:
                include_type = IncludeType[name]
                assert isinstance(value, str), type(value)
                includes.append((pathlib.Path(value), include_type))
            else:
                self.entries[name] = Entry(
                    name=name,
                    value=value,
                    commented=commented,
                    raw_line=raw_line,
                    **kwargs
                )
        includes.reverse()
        return includes

    def __getattr__(self, name: str) -> Value:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name: str, value: Value) -> None:
        if name in self.__dict__:
            self.__dict__[name] = value
        else:
            self[name] = value

    def __contains__(self, key: str) -> bool:
        return key in self.entries

    def __getitem__(self, key: str) -> Value:
        return self.entries[key].value

    def __setitem__(self, key: str, value: Value) -> None:
        if key in IncludeType.__members__:
            raise ValueError("cannot add an include directive")
        if key in self.entries:
            e = self.entries[key]
            e.value = value
            self._update_entry(e)
        else:
            self._add_entry(Entry(name=key, value=value))

    def _add_entry(self, entry: Entry) -> None:
        assert entry.name not in self.entries
        self.entries[entry.name] = entry
        # Append serialized line.
        entry.raw_line = str(entry) + '\n'
        self.lines.append(entry.raw_line)

    def _update_entry(self, entry: Entry) -> None:
        old_entry = self.entries[entry.name]
        if entry.commented:
            # If the entry was previously commented, we uncomment it (assuming
            # that setting a value to a commented entry does not make much
            # sense.)
            entry.commented = False
        # Update serialized entry.
        old_line = old_entry.raw_line
        entry.raw_line = str(entry) + '\n'
        lineno = self.lines.index(old_line)
        self.lines[lineno:lineno+1] = [entry.raw_line]

    def __iter__(self) -> Iterator[Entry]:
        return iter(self.entries.values())

    def as_dict(self) -> Dict[str, Value]:
        return dict([(k, v.value) for k, v in self.entries.items()
                     if not v.commented])

    @contextlib.contextmanager
    def edit(self) -> Iterator[EntriesProxy]:
        r"""Context manager allowing edition of the Configuration instance.

        >>> import sys

        >>> cfg = Configuration()
        >>> _ = cfg.parse([
        ...     "#listen_addresses = 'localhost'  # what IP address(es) to listen on;\n",
        ...     "                                 # comma-separated list of addresses;\n",
        ...     "port = 5432				# (change requires restart)\n",
        ...     "max_connections = 100			# (change requires restart)\n",
        ... ])
        >>> cfg.save(sys.stdout)
        #listen_addresses = 'localhost'  # what IP address(es) to listen on;
                                         # comma-separated list of addresses;
        port = 5432                            # (change requires restart)
        max_connections = 100                  # (change requires restart)

        >>> with cfg.edit() as entries:
        ...     entries["port"].value = 2345
        ...     entries["port"].comment = None
        ...     entries["listen_addresses"].value = '*'
        ...     del entries["max_connections"]
        ...     entries.add(
        ...         "unix_socket_directories",
        ...         "'/var/run/postgresql'",
        ...         comment="comma-separated list of directories",
        ...     )
        >>> cfg.save(sys.stdout)
        listen_addresses = '*'  # what IP address(es) to listen on;
                                         # comma-separated list of addresses;
        port = 2345
        unix_socket_directories = '/var/run/postgresql'  # comma-separated list of directories
        """  # noqa: E501
        entries = EntriesProxy(
            {k: copy.copy(v) for k, v in self.entries.items()}
        )
        try:
            yield entries
        except Exception:
            raise
        else:
            # Add or update entries.
            for k, entry in entries.items():
                assert isinstance(entry, Entry), "expecting Entry values"
                if k not in self:
                    self._add_entry(entry)
                elif self.entries[k] != entry:
                    self._update_entry(entry)
            # Discard removed entries.
            for k, entry in list(self.entries.items()):
                if k not in entries:
                    del self.entries[k]
                    if entry.raw_line is not None:
                        self.lines.remove(entry.raw_line)

    def save(self, fo: Optional[Union[str, IO[str]]] = None) -> None:
        """Write configuration to a file.

        Configuration entries order and comments are preserved.

        :param fo: A path or file-like object. Required if :attr:`path` is
            None.

        """
        with open_or_return(fo or self.path, mode='w') as fo:
            for line in self.lines:
                fo.write(line)


def _main(argv: List[str]) -> int:  # pragma: nocover
    try:
        conf = parse(argv[0] if argv else sys.stdin)
        print(json.dumps(conf.as_dict(), cls=JSONDateEncoder, indent=2))
        return 0
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == '__main__':  # pragma: nocover
    exit(_main(sys.argv[1:]))
