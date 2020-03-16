import codecs
from datetime import datetime, tzinfo
from functools import partial


def test_octal_encoding():
    __import__('pgtoolkit.log')

    encoded = "#011my#012line"
    assert "\tmy\nline" == codecs.decode(encoded, 'syslog-octal')

    decoded = "tab\tline\r\n"
    assert "tab#011line#015#012" == codecs.encode(decoded, 'syslog-octal')


def test_process_syslog():
    from pgtoolkit.log.syslog import SyslogPreprocessor

    lines = """\
Mar 13 09:28:26 socle-dev0 postgresql-12-main[22163]: [1] [22163]: [1-1] db=,user=,app=,client= LOG:  automatic vacuum of table "postgres.pg_catalog.pg_default_acl": index scans: 1
Mar 13 09:28:26 socle-dev0 postgresql-12-main[22163]: [2] #011pages: 0 removed, 2 remain, 0 skipped due to pins, 0 skipped frozen
Mar 13 09:28:26 socle-dev0 postgresql-12-main[22163]: [3] #011tuples: 120 removed, 39 remain, 0 are dead but not yet removable, oldest xmin: 843
""".splitlines(True)  # noqa

    processor = SyslogPreprocessor(syslog_sequence_numbers=False)
    processed = list(processor.process(lines))
    assert len(lines) == len(processed)
    assert processed[1].startswith('\t')


def test_process_syslog_seq():
    from pgtoolkit.log.syslog import SyslogPreprocessor

    lines = """\
Mar 13 09:28:26 socle-dev0 postgresql-12-main[22163]: [8-1] [22163]: [1-1] db=,user=,app=,client= LOG:  automatic vacuum of table "postgres.pg_catalog.pg_default_acl": index scans: 1
Mar 13 09:28:26 socle-dev0 postgresql-12-main[22163]: [8-2] #011pages: 0 removed, 2 remain, 0 skipped due to pins, 0 skipped frozen
Mar 13 09:28:26 socle-dev0 postgresql-12-main[22163]: [8-3] #011tuples: 120 removed, 39 remain, 0 are dead but not yet removable, oldest xmin: 843
Mar 13 09:28:26 socle-dev0 postgresql-12-main[22163]: [8-4] #011buffer usage: 43 hits, 1 misses, 4 dirtied
Mar 13 09:28:26 socle-dev0 postgresql-12-main[22163]: [8-5] #011avg read rate: 4.620 MB/s, avg write rate: 18.480 MB/s
Mar 13 09:28:26 socle-dev0 postgresql-12-main[22163]: [8-6] #011system usage: CPU: user: 0.00 s, system: 0.00 s, elapsed: 0.00 s

Mar 13 09:28:26 socle-dev0 postgresql-12-main[22163]: [9-1] [22163]: [2-1] db=,user=,app=,client= LOG:  automatic analyze of table "postgres.pg_catalog.pg_default_acl" system usage: CPU: user: 0.00 s, system: 0.00 s, elapsed: 0.00 s
""".splitlines(True)  # noqa

    processor = SyslogPreprocessor(syslog_sequence_numbers=True)
    processed = list(processor.process(lines))
    assert len(lines) == len(processed)
    assert processed[1].startswith('\t')


def test_datetime():
    from pgtoolkit.log.syslog import parse_syslog_datetime

    class MyTZ(tzinfo):
        pass

    mytz = MyTZ()
    date = parse_syslog_datetime(
        'Mar 13 09:28:26',
        year=2020, tzinfo=mytz,
    )
    assert 2020 == date.year
    assert 3 == date.month
    assert 13 == date.day
    assert 9 == date.hour
    assert 28 == date.minute
    assert 26 == date.second
    assert date.tzinfo is mytz


def test_parse_stage2():
    from pgtoolkit.log.syslog import SyslogLine, parse_syslog_datetime
    from pgtoolkit.log import Record

    line = SyslogLine(
        "message",
        pid="123",
        timestamp="Mar 13 09:28:26",
        date_parser=partial(parse_syslog_datetime, year=2020)
    )
    record = Record("prefix", "LOG")
    line.parse_stage2(record)

    assert 123 == record.pid
    assert datetime(2020, 3, 13, 9, 28, 26) == record.timestamp
