import re
from datetime import datetime, timedelta
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Pattern,
    Sequence,
    Union,
)


class LogParser:
    """Log parsing manager

    This object gather parsing parameters and trigger parsing logic. When
    parsing multiple files with the same parameters or when parsing multiple
    sets of lines, :class:`LogParser` object ease the initialization and
    preservation of parsing parameters.

    When parsing a single set of lines, one can use :func:`parse` helper
    instead.

    :param prefix_parser: An instance of :class:`PrefixParser`.
    :param filters: An instance of :class:`NoopFilters`

    """

    def __init__(
        self, prefix_parser: "PrefixParser", filters: Optional["NoopFilters"] = None
    ) -> None:
        self.prefix_parser = prefix_parser
        self.filters = filters or NoopFilters()

    def parse(self, fo: Iterable[str]) -> Iterator[Union["Record", "UnknownData"]]:
        """Yield records and unparsed data from file-like object ``fo``

        :param fo: A line iterator such as a file object.
        :rtype: Iterator[Union[:class:`Record`, :class:`UnknownData`]]
        :returns: Yields either :class:`Record` or :class:`UnknownData` object.
        """
        # Fast access variables to avoid attribute access overhead on each
        # line.
        parse_prefix = self.prefix_parser.parse
        stage1 = Record.parse_stage1
        filter_stage1 = self.filters.stage1
        filter_stage2 = self.filters.stage2
        filter_stage3 = self.filters.stage3

        for group in group_lines(fo):
            try:
                record = stage1(group)
                if filter_stage1(record):
                    continue
                record.parse_stage2(parse_prefix)
                if filter_stage2(record):
                    continue
                record.parse_stage3()
                if filter_stage3(record):
                    continue
            except UnknownData as e:
                yield e
            else:
                yield record


def parse(
    fo: Iterable[str], prefix_fmt: str, filters: Optional["NoopFilters"] = None
) -> Iterator[Union["Record", "UnknownData"]]:
    """Parses log lines and yield :class:`Record` or :class:`UnknownData` objects.

    This is a helper around :class:`LogParser` and :`PrefixParser`.

    :param fo: A line iterator such as a file-like object.
    :param prefix_fmt: is exactly the value of ``log_line_prefix`` Postgresql
        settings.
    :param filters: is an object like :class:`NoopFilters` instance.

    See Example_ section for usage.

    """

    parser = LogParser(
        PrefixParser.from_configuration(prefix_fmt),
        filters=filters,
    )
    for item in parser.parse(fo):
        yield item


def group_lines(lines: Iterable[str], cont: str = "\t") -> Iterator[List[str]]:
    # Group continuation lines according to continuation prefix. Yield a list
    # on lines supposed to belong to the same log record.

    group: List[str] = []
    for line in lines:
        if not line.startswith(cont) and group:
            yield group
            group = []
        group.append(line)

    if group:
        yield group


def parse_isodatetime(raw: str) -> datetime:
    try:
        infos = (
            int(raw[:4]),
            int(raw[5:7]),
            int(raw[8:10]),
            int(raw[11:13]),
            int(raw[14:16]),
            int(raw[17:19]),
            int(raw[20:23]) if raw[19] == "." else 0,
        )
    except ValueError:
        raise ValueError("%s is not a known date" % raw)

    if raw[-3:] != "UTC":
        # We need tzdata for that.
        raise ValueError("%s not in UTC." % raw)

    return datetime(*infos)


def parse_epoch(raw: str) -> datetime:
    epoch, ms = raw.split(".")
    return datetime.utcfromtimestamp(int(epoch)) + timedelta(microseconds=int(ms))


class UnknownData(Exception):
    """Represents unparseable data.

    :class:`UnknownData` is throwable, you can raise it.

    .. attribute:: lines

        The list of unparseable strings.
    """

    # UnknownData object is an exception to be throwable.

    def __init__(self, lines: Sequence[str]) -> None:
        self.lines = lines

    def __repr__(self) -> str:
        summary = str(self)[:32].replace("\n", "")
        return "<%s %s...>" % (self.__class__.__name__, summary)

    def __str__(self) -> str:
        return "".join(self.lines)


class NoopFilters:
    """Basic filter doing nothing.

    Filters are grouped in an object to simplify the definition of a filtering
    policy. By subclassing :class:`NoopFilters`, you can implement simple
    filtering or heavy parameterized filtering policy from this API.

    If a filter method returns True, the record processing stops and the
    record is dropped.

    .. automethod:: stage1
    .. automethod:: stage2
    .. automethod:: stage3

    """

    def stage1(self, record: "Record") -> None:
        """First stage filter.

        :param Record record: A new record.
        :returns: ``True`` if record must be dropped.

        ``record`` has only `prefix`, `severity` and `message_type`
        attributes.
        """

    def stage2(self, record: "Record") -> None:
        """Second stage filter.

        :param Record record: A new record.
        :returns: ``True`` if record must be dropped.

        ``record`` has attributes from stage 1 plus attributes from prefix
        analysis. See :class:`Record` for details.
        """

    def stage3(self, record: "Record") -> None:
        """Third stage filter.

        :param Record record: A new record.
        :returns: ``True`` if record must be dropped.

        ``record`` has attributes from stage 2 plus attributes from message
        analysis, depending on message type.
        """


class PrefixParser:
    """Extract record metadata from PostgreSQL log line prefix.

    .. automethod:: from_configuration
    """

    # cf.
    # https://www.postgresql.org/docs/current/static/runtime-config-logging.html#GUC-LOG-LINE-PREFIX

    _datetime_pat = r"\d{4}-[01]\d-[0-3]\d [012]\d:[0-6]\d:[0-6]\d"
    # Pattern map of Status informations.
    _status_pat = dict(
        # Application name
        a=r"(?P<application>\[unknown\]|\w+)?",
        # Session ID
        c=r"(?P<session>\[unknown\]|[0-9a-f.]+)",
        # Database name
        d=r"(?P<database>\[unknown\]|\w+)?",
        # SQLSTATE error code
        e=r"(?P<error>\d+)",
        # Remote host name or IP address
        h=r"(?P<remote_host>\[local\]|\[unknown\]|[a-z0-9_-]+|[0-9.:]+)?",
        # Command tag: type of session's current command
        i=r"(?P<command_tag>\w+)",
        # Number of the log line for each session or process, starting at 1.
        l=r"(?P<line_num>\d+)",  # noqa
        # Time stamp with milliseconds
        m=r"(?P<timestamp_ms>" + _datetime_pat + r".\d{3} [A-Z]{2,5})",
        # Time stamp with milliseconds (as a Unix epoch)
        n=r"(?P<epoch>\d+\.\d+)",
        # Process ID
        p=r"(?P<pid>\d+)",
        # Remote host name or IP address, and remote port
        r=r"(?P<remote_host_r>\[local\]|\[unknown\]|[a-z0-9_-]+|[0-9.:]+\((?P<remote_port>\d+)\))?",  # noqa
        # Process start time stamp
        s=r"(?P<start>" + _datetime_pat + " [A-Z]{2,5})",
        # Time stamp without milliseconds
        t=r"(?P<timestamp>" + _datetime_pat + " [A-Z]{2,5})",
        # User name
        u=r"(?P<user>\[unknown\]|\w+)?",
        # Virtual transaction ID (backendID/localXID)
        v=r"(?P<virtual_xid>\d+/\d+)",
        # Transaction ID (0 if none is assigned)
        x=r"(?P<xid>\d+)",
    )
    # re to search for %… in log_line_prefix.
    _format_re = re.compile(r"%([" + "".join(_status_pat.keys()) + "])")
    # re to find %q separator in log_line_prefix.
    _q_re = re.compile(r"(?<!%)%q")

    _casts: Dict[str, Callable[[str], Union[int, datetime]]] = {
        "epoch": parse_epoch,
        "line_num": int,
        "pid": int,
        "remote_port": int,
        "start": parse_isodatetime,
        "timestamp": parse_isodatetime,
        "timestamp_ms": parse_isodatetime,
        "xid": int,
    }

    @classmethod
    def mkpattern(cls, prefix: str) -> str:
        # Builds a pattern from each known fields.
        segments = cls._format_re.split(prefix)
        for i, segment in enumerate(segments):
            if i % 2:
                segments[i] = cls._status_pat[segment]
            else:
                segments[i] = re.escape(segment)
        return "".join(segments)

    @classmethod
    def from_configuration(cls, log_line_prefix: str) -> "PrefixParser":
        """Factory from log_line_prefix

        Parses log_line_prefix and build a prefix parser from this.

        :param log_line_prefix: ``log_line_prefix`` PostgreSQL setting.
        :return: A :class:`PrefixParser` instance.

        """
        optionnal: Optional[str]
        try:
            fixed, optionnal = cls._q_re.split(log_line_prefix)
        except ValueError:
            fixed, optionnal = log_line_prefix, None

        pattern = cls.mkpattern(fixed)
        if optionnal:
            pattern += r"(?:" + cls.mkpattern(optionnal) + ")?"
        return cls(re.compile(pattern), log_line_prefix)

    def __init__(self, re_: Pattern[str], prefix_fmt: Optional[str] = None) -> None:
        self.re_ = re_
        self.prefix_fmt = prefix_fmt

    def __repr__(self) -> str:
        return "<%s '%s'>" % (self.__class__.__name__, self.prefix_fmt)

    def parse(self, prefix: str) -> MutableMapping[str, Any]:
        # Parses the prefix line according to the inner regular expression. If
        # prefix does not match, raises an UnknownData.

        match = self.re_.search(prefix)
        if not match:
            raise UnknownData([prefix])
        fields = match.groupdict()

        self.cast_fields(fields)

        # Ensure remote_host is fed either by %h or %r.
        remote_host = fields.pop("remote_host_r", None)
        if remote_host:
            fields.setdefault("remote_host", remote_host)

        # Ensure timestamp field is fed eiter by %m or %t.
        timestamp_ms = fields.pop("timestamp_ms", None)
        if timestamp_ms:
            fields.setdefault("timestamp", timestamp_ms)

        return fields

    @classmethod
    def cast_fields(cls, fields: MutableMapping[str, Any]) -> None:
        # In-place cast of values in fields dictionnary.

        for k in fields:
            v = fields[k]
            if v is None:
                continue
            cast = cls._casts.get(k)
            if cast:
                fields[k] = cast(v)


class Record:
    """Log record object.

    Record object stores record fields and implements the different parse
    stages.

    A record is primarily composed by a prefix, a severity and a message.
    Actually, severity is mixed with message type. For example, a HINT: message
    has the same severity as ``LOG:`` and is actually a continuation message
    (see csvlog output to compare). Thus we can determine easily message type
    as this stage. :mod:`pgtoolkit.log` does not rewrite message severity.

    Once prefix, severity and message are splitted, the parser analyze prefix
    according to ``log_line_prefix`` parameter. Prefix can give a lot of
    informations for filtering, but costs some CPU cycles to process.

    Finally, the parser analyze the message to extract informations such as
    statement, hint, duration, execution plan, etc. depending on the message
    type.

    These stages are separated so that marshalling can apply filter between
    each stage.

    .. automethod:: as_dict

    Each record field is accessible as an attribute :

    .. attribute:: prefix

        Raw prefix line.

    .. attribute:: severity

        One of ``DEBUG1`` to ``DEBUG5``, ``CONTEXT``, ``DETAIL``, ``ERROR``,
        etc.

    .. attribute:: message_type

        A string identifying message type. One of ``unknown``, ``duration``,
        ``connection``, ``analyze``, ``checkpoint``.

    .. attribute:: raw_lines

        A record can span multiple lines. This attribute keep a reference on
        raw record lines of the record.

    .. attribute:: message_lines

        Just like :attr:`raw_lines`, but the first line only include message,
        without prefix nor severity.

    The following attributes correspond to prefix fields. See `log_line_prefix
    documentation
    <https://www.postgresql.org/docs/current/static/runtime-config-logging.html#GIC-LOG-LINE-PREFIX>`_
    for details.

    .. attribute:: application_name
    .. attribute:: command_tag
    .. attribute:: database
    .. attribute:: epoch

       :type: :class:`datetime.datetime`

    .. attribute:: error
    .. attribute:: line_num

       :type: :class:`int`

    .. attribute:: pid

       :type: :class:`int`

    .. attribute:: remote_host
    .. attribute:: remote_port

       :type: :class:`int`

    .. attribute:: session
    .. attribute:: start

       :type: :class:`datetime.datetime`

    .. attribute:: timestamp

       :type: :class:`datetime.datetime`

    .. attribute:: user
    .. attribute:: virtual_xid
    .. attribute:: xid

       :type: :class:`int`

    If the log lines miss a field, the record won't have the attribute. Use
    :func:`hasattr` to check whether a record have a specific attribute.
    """

    __slots__ = (
        "__dict__",
        "message_lines",
        "prefix",
        "raw_lines",
    )

    # This actually mix severities and message types since they are in the same
    # field.
    _severities = [
        "CONTEXT",
        "DETAIL",
        "ERROR",
        "FATAL",
        "HINT",
        "INFO",
        "LOG",
        "NOTICE",
        "PANIC",
        "QUERY",
        "STATEMENT",
        "WARNING",
    ]
    _stage1_re = re.compile("(DEBUG[1-5]|" + "|".join(_severities) + "):  ")

    _types_prefixes = {
        "duration: ": "duration",
        "connection ": "connection",
        "disconnection": "connection",
        "automatic analyze": "analyze",
        "checkpoint ": "checkpoint",
    }

    @classmethod
    def guess_type(cls, severity: str, message_start: str) -> str:
        # Guess message type from severity and the first line of the message.

        if severity in ("HINT", "STATEMENT"):
            return severity.lower()
        for prefix in cls._types_prefixes:
            if message_start.startswith(prefix):
                return cls._types_prefixes[prefix]
        return "unknown"

    @classmethod
    def parse_stage1(cls, lines: List[str]) -> "Record":
        # Stage1: split prefix, severity and message.
        try:
            prefix, severity, message0 = cls._stage1_re.split(lines[0], maxsplit=1)
        except ValueError:
            raise UnknownData(lines)

        return cls(
            prefix=prefix,
            severity=severity,
            message_type=cls.guess_type(severity, message0),
            message_lines=[message0] + lines[1:],
            raw_lines=lines,
        )

    def __init__(
        self,
        prefix: str,
        severity: str,
        message_type: str = "unknown",
        message_lines: Optional[List[str]] = None,
        raw_lines: Optional[List[str]] = None,
        **fields: str,
    ) -> None:
        self.prefix = prefix
        self.severity = severity
        self.message_type = message_type
        self.message_lines = message_lines or []
        self.raw_lines = raw_lines or []
        self.__dict__.update(fields)

    def __repr__(self) -> str:
        return "<%s %s: %.32s...>" % (
            self.__class__.__name__,
            self.severity,
            self.message_lines[0].replace("\n", ""),
        )

    def parse_stage2(self, parse_prefix: Callable[[str], Mapping[str, Any]]) -> None:
        # Stage 2. Analyze prefix fields

        self.__dict__.update(parse_prefix(self.prefix))

    def parse_stage3(self) -> None:
        # Stage 3. Analyze message lines.

        self.message = "".join(
            [line.lstrip("\t").rstrip("\n") for line in self.message_lines]
        )

    def as_dict(self) -> Dict[str, Union[str, object, datetime]]:
        """Returns record fields as a :class:`dict`."""
        return dict([(k, v) for k, v in self.__dict__.items()])
