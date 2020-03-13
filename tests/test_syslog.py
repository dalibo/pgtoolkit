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
