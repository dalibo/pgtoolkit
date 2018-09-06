import pytest

HBA_SAMPLE = """\
# CAUTION: Configuring the system for local "trust" authentication
# allows any local user to connect as any PostgreSQL user, including
# the database superuser.  If you do not trust all your local users,
# use another authentication method.


# TYPE  DATABASE        USER            ADDRESS                 METHOD

# "local" is for Unix domain socket connections only
local   all             all                                     trust
# IPv4 local connections:
host    all             all             127.0.0.1/32            trust
# IPv6 local connections:
host    all             all             ::1/128                 trust
# Allow replication connections from localhost, by a user with the
# replication privilege.
local   replication     all                                     trust
host replication  all        127.0.0.1  255.255.255.255         trust
host    replication     all             ::1/128                 trust

host all all all trust
"""


def test_comment():
    from pgtoolkit.hba import HBAComment

    comment = HBAComment('# toto')
    assert 'toto' in repr(comment)
    assert '# toto' == str(comment)


def test_parse_host_line():
    from pgtoolkit.hba import HBARecord

    record = HBARecord.parse("host    replication   all   ::1/128       trust")
    assert 'host' in repr(record)
    assert 'host' == record.conntype
    assert 'replication' == record.database
    assert 'all' == record.user
    assert '::1/128' == record.address
    assert 'trust' == record.method


def test_parse_local_line():
    from pgtoolkit.hba import HBARecord

    record = HBARecord.parse("local    all     all     trust")
    assert 'local' == record.conntype
    assert 'all' == record.database
    assert 'all' == record.user
    assert 'trust' == record.method

    with pytest.raises(AttributeError):
        record.address

    wanted = 'local   all             all                                     trust'  # noqa
    assert wanted == str(record)


def test_parse_auth_option():
    from pgtoolkit.hba import HBARecord

    record = HBARecord.parse(
        "local veryverylongdatabasenamethatdonotfit all ident map=omicron",
    )
    assert 'local' == record.conntype
    assert 'veryverylongdatabasenamethatdonotfit' == record.database
    assert 'all' == record.user
    assert 'ident' == record.method
    assert 'omicron' == record.map

    wanted = [
        'local', 'veryverylongdatabasenamethatdonotfit', 'all', 'ident',
        'map=omicron',
    ]
    assert wanted == str(record).split()


def test_parse_record_with_comment():
    from pgtoolkit.hba import HBARecord

    record = HBARecord.parse("local    all     all     trust  # My  comment")
    assert 'local' == record.conntype
    assert 'all' == record.database
    assert 'all' == record.user
    assert 'trust' == record.method
    assert 'My comment' == record.comment

    fields = str(record).split()
    assert ['local', 'all', 'all', 'trust', '#', 'My', 'comment'] == fields


def test_hba(mocker):
    from pgtoolkit.hba import parse

    lines = HBA_SAMPLE.splitlines(True)
    hba = parse(lines)
    entries = list(iter(hba))

    assert 7 == len(entries)

    hba.save(mocker.Mock(name='file'))


def test_parse_file(mocker):
    from pgtoolkit.hba import parse, HBAComment

    m = mocker.mock_open()
    try:
        mocker.patch('builtins.open', m)
    except Exception:
        mocker.patch('__builtin__.open', m)
    pgpass = parse('filename')
    pgpass.lines.append(HBAComment('# Something'))

    assert m.called
    pgpass.save()
    handle = m()
    handle.write.assert_called_with('# Something\n')

    # Also works for other string types
    m.reset_mock()
    pgpass = parse(u'filename')
    pgpass.lines.append(HBAComment('# Something'))
    assert m.called


def test_hba_error(mocker):
    from pgtoolkit.hba import parse, ParseError

    with pytest.raises(ParseError) as ei:
        parse(["lcal\n"])
    e = ei.value
    assert 'line #1' in str(e)
    assert repr(e)
