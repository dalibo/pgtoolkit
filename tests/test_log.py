import re

import pytest


def test_parse():
    from pgtoolkit.log import parse, UnknownData

    lines = """\
\tResult  (cost=0.00..0.01 rows=1 width=4) (actual time=1001.117..1001.118 rows=1 loops=1)
\t  Output: pg_sleep('1'::double precision)
2018-06-15 10:03:53.488 UTC [7931]: [2-1] app=[unknown],db=[unknown],client=[local],user=[unknown] LOG:  incomplete startup packet
2018-06-15 10:44:42.923 UTC [8280]: [2-1] app=,db=,client=,user= LOG:  checkpoint starting: shutdown immediate
2018-06-15 10:44:58.206 UTC [8357]: [4-1] app=psql,db=postgres,client=[local],user=postgres HINT:  No function matches the given name and argument types. You might need to add explicit type casts.
2018-06-15 10:45:03.175 UTC [8357]: [7-1] app=psql,db=postgres,client=[local],user=postgres LOG:  duration: 1002.209 ms  statement: select pg_sleep(1);
2018-06-15 10:49:11.512 UTC [8357]: [8-1] app=psql,db=postgres,client=[local],user=postgres LOG:  duration: 0.223 ms  statement: show log_timezone;
2018-06-15 10:49:26.084 UTC [8420]: [2-1] app=[unknown],db=postgres,client=[local],user=postgres LOG:  connection authorized: user=postgres database=postgres
2018-06-15 10:49:26.088 UTC [8420]: [3-1] app=psql,db=postgres,client=[local],user=postgres LOG:  duration: 1.449 ms  statement: SELECT d.datname as "Name",
\t       pg_catalog.pg_get_userbyid(d.datdba) as "Owner",
\t       pg_catalog.pg_encoding_to_char(d.encoding) as "Encoding",
\t       d.datcollate as "Collate",
\t       d.datctype as "Ctype",
\t       pg_catalog.array_to_string(d.datacl, E'\\n') AS "Access privileges"
\tFROM pg_catalog.pg_database d
\tORDER BY 1;
2018-06-15 10:49:26.088 UTC [8420]: [4-1] app=psql,db=postgres,client=[local],user=postgres LOG:  disconnection: session time: 0:00:00.006 user=postgres database=postgres host=[local]
BAD PREFIX 10:49:31.140 UTC [8423]: [1-1] app=[unknown],db=[unknown],client=[local],user=[unknown] LOG:  connection received: host=[local]
""".splitlines(
        True
    )  # noqa

    log_line_prefix = "%m [%p]: [%l-1] app=%a,db=%d,client=%h,user=%u "
    records = list(parse(lines, prefix_fmt=log_line_prefix))

    assert isinstance(records[0], UnknownData)
    assert "\n" not in repr(records[0])
    record = records[1]
    assert "LOG" == record.severity


def test_group_lines():
    from pgtoolkit.log.parser import group_lines

    lines = """\
\tResult  (cost=0.00..0.01 rows=1 width=4) (actual time=1001.117..1001.118 rows=1 loops=1)
\t  Output: pg_sleep('1'::double precision)
2018-06-15 10:45:03.175 UTC [8357]: [7-1] app=psql,db=postgres,client=[local],user=postgres LOG:  duration: 1002.209 ms  statement: select pg_sleep(1);
2018-06-15 10:49:11.512 UTC [8357]: [8-1] app=psql,db=postgres,client=[local],user=postgres LOG:  duration: 0.223 ms  statement: show log_timezone;
2018-06-15 10:49:26.084 UTC [8420]: [2-1] app=[unknown],db=postgres,client=[local],user=postgres LOG:  connection authorized: user=postgres database=postgres
2018-06-15 10:49:26.088 UTC [8420]: [3-1] app=psql,db=postgres,client=[local],user=postgres LOG:  duration: 1.449 ms  statement: SELECT d.datname as "Name",
\t       pg_catalog.pg_get_userbyid(d.datdba) as "Owner",
\t       pg_catalog.pg_encoding_to_char(d.encoding) as "Encoding",
\t       d.datcollate as "Collate",
\t       d.datctype as "Ctype",
\t       pg_catalog.array_to_string(d.datacl, E'\\n') AS "Access privileges"
\tFROM pg_catalog.pg_database d
\tORDER BY 1;
2018-06-15 10:49:26.088 UTC [8420]: [4-1] app=psql,db=postgres,client=[local],user=postgres LOG:  disconnection: session time: 0:00:00.006 user=postgres database=postgres host=[local]
2018-06-15 10:49:31.140 UTC [8423]: [1-1] app=[unknown],db=[unknown],client=[local],user=[unknown] LOG:  connection received: host=[local]
""".splitlines(
        True
    )  # noqa

    groups = list(group_lines(lines))
    assert 7 == len(groups)


def test_prefix_parser():
    from pgtoolkit.log.parser import PrefixParser

    # log_line_prefix with all options.
    prefix_fmt = "%m [%p]: [%l-1] app=%a,db=%d,client=%h,user=%u,remote=%r,epoch=%n,timestamp=%t,tag=%i,error=%e,session=%c,start=%s,vxid=%v,xid=%x "  # noqa
    prefix = "2018-06-15 14:15:52.332 UTC [10011]: [2-1] app=[unknown],db=postgres,client=[local],user=postgres,remote=[local],epoch=1529072152.332,timestamp=2018-06-15 14:15:52 UTC,tag=authentication,error=00000,session=5b23ca18.271b,start=2018-06-15 14:15:52 UTC,vxid=3/7,xid=0 "  # noqa

    # Ensure each pattern matches.
    for pat in PrefixParser._status_pat.values():
        assert re.search(pat, prefix)

    parser = PrefixParser.from_configuration(prefix_fmt)
    assert "%m" in repr(parser)
    fields = parser.parse(prefix)

    assert 2018 == fields["timestamp"].year
    assert "application" in fields
    assert "user" in fields
    assert "database" in fields
    assert "remote_host" in fields
    assert 10011 == fields["pid"]
    assert 2 == fields["line_num"]


def test_prefix_parser_q():
    from pgtoolkit.log.parser import PrefixParser

    # log_line_prefix with all options.
    prefix_fmt = "%m [%p]: %q%u@%h "

    parser = PrefixParser.from_configuration(prefix_fmt)
    fields = parser.parse("2018-06-15 14:15:52.332 UTC [10011]: ")
    assert fields["user"] is None


def test_isodatetime():
    from pgtoolkit.log.parser import parse_isodatetime

    date = parse_isodatetime("2018-06-04 20:12:34.343 UTC")
    assert date
    assert 2018 == date.year
    assert 6 == date.month
    assert 4 == date.day
    assert 20 == date.hour
    assert 12 == date.minute
    assert 34 == date.second
    assert 343 == date.microsecond

    with pytest.raises(ValueError):
        parse_isodatetime("2018-06-000004")

    with pytest.raises(ValueError):
        parse_isodatetime("2018-06-04 20:12:34.343 CEST")


def test_record_stage1_ok():
    from pgtoolkit.log import Record

    lines = """\
2018-06-15 10:49:26.088 UTC [8420]: [3-1] app=psql,db=postgres,client=[local],user=postgres LOG:  duration: 1.449 ms  statement: SELECT d.datname as "Name",
\t       pg_catalog.array_to_string(d.datacl, E'\\n') AS "Access privileges"
\tFROM pg_catalog.pg_database d
\tORDER BY 1;
""".splitlines(
        True
    )  # noqa

    record = Record.parse_stage1(lines)
    assert "LOG" in repr(record)
    assert "\n" not in repr(record)
    assert 4 == len(record.raw_lines)
    assert "LOG" == record.severity
    assert 4 == len(record.message_lines)
    assert record.message_lines[0].startswith("duration: ")


def test_record_stage1_nok():
    from pgtoolkit.log import Record, UnknownData

    lines = ["pouet\n", "toto\n"]
    with pytest.raises(UnknownData) as ei:
        Record.parse_stage1(lines)
    assert "pouet\ntoto\n" in str(ei.value)


def test_record_stage2_ok(mocker):
    from pgtoolkit.log import Record

    record = Record(
        prefix="2018-06-15 10:49:26.088 UTC [8420]: [3-1] app=psql,db=postgres,client=[local],user=postgres ",  # noqa
        severity="LOG",
        message_lines=["message"],
        raw_lines=[],
    )

    prefix_parser = mocker.Mock(name="prefix_parser")
    prefix_parser.return_value = dict(remote_host="[local]")
    record.parse_stage2(prefix_parser)
    assert "[local]" == record.remote_host


def test_filters():
    from pgtoolkit.log import parse, NoopFilters

    lines = """\
stage1 LOG:  duration: 1002.209 ms  statement: select pg_sleep(1);
stage2 LOG:  duration: 0.223 ms  statement: show log_timezone;
stage3 LOG:  connection authorized: user=postgres database=postgres
""".splitlines(
        True
    )  # noqa

    class MyFilters(NoopFilters):
        def stage1(self, record):
            return record.prefix.startswith("stage1")

        def stage2(self, record):
            return record.prefix.startswith("stage2")

        def stage3(self, record):
            return record.prefix.startswith("stage3")

    log_line_prefix = "stage%p "
    filters = MyFilters()
    records = list(parse(lines, prefix_fmt=log_line_prefix, filters=filters))
    assert 0 == len(records)


def test_main(mocker, caplog, capsys):
    pkg = "pgtoolkit.log.__main__"
    mocker.patch(pkg + ".logging.basicConfig", autospec=True)
    open_ = mocker.patch(pkg + ".open_or_stdin", autospec=True)
    parse = mocker.patch(pkg + ".parse", autospec=True)

    from datetime import datetime
    from pgtoolkit.log import Record, UnknownData
    from pgtoolkit.log.__main__ import main

    open_.return_value = mocker.MagicMock()
    parse.return_value = [
        Record("prefix", "LOG", timestamp=datetime.utcnow()),
        UnknownData(["unknown line\n"]),
    ]
    log_line_prefix = "%m [%p]: "
    main(argv=[log_line_prefix], environ=dict())
    out, err = capsys.readouterr()
    assert "LOG" in out

    if isinstance(caplog.records, list):
        records = caplog.records
    else:  # Compat python pytest-capturelog for py26
        records = caplog.records()

    for record in records:
        if "unknown line" in record.message:
            break
    else:
        assert False, "Bad line not logged"


def test_main_ko(mocker):
    pkg = "pgtoolkit.log.__main__"
    mocker.patch(pkg + ".logging.basicConfig", autospec=True)
    open_ = mocker.patch(pkg + ".open_or_stdin", autospec=True)
    parse = mocker.patch(pkg + ".parse", autospec=True)

    from pgtoolkit.log import Record
    from pgtoolkit.log.__main__ import main

    open_.return_value = mocker.MagicMock()
    parse.return_value = [Record("prefix", "LOG", badentry=object())]
    assert 1 == main(argv=["%m"], environ=dict())
