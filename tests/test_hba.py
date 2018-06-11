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
    from pgtoolkit.hba import HBAEntry

    entry = HBAEntry.parse("host    replication   all   ::1/128         trust")
    assert 'host' in repr(entry)
    assert 'host' == entry.conntype
    assert 'replication' == entry.database
    assert 'all' == entry.user
    assert '::1/128' == entry.address
    assert 'trust' == entry.method


def test_parse_local_line():
    from pgtoolkit.hba import HBAEntry

    entry = HBAEntry.parse("local    all     all     trust")
    assert 'local' == entry.conntype
    assert 'all' == entry.database
    assert 'all' == entry.user
    assert 'trust' == entry.method

    with pytest.raises(AttributeError):
        entry.address

    wanted = 'local   all             all                                     trust'  # noqa
    assert wanted == str(entry)


def test_parse_auth_option():
    from pgtoolkit.hba import HBAEntry

    entry = HBAEntry.parse(
        "local veryverylongdatabasenamethatdonotfit all ident map=omicron",
    )
    assert 'local' == entry.conntype
    assert 'veryverylongdatabasenamethatdonotfit' == entry.database
    assert 'all' == entry.user
    assert 'ident' == entry.method
    assert 'omicron' == entry.map

    wanted = [
        'local', 'veryverylongdatabasenamethatdonotfit', 'all', 'ident',
        'map=omicron',
    ]
    assert wanted == str(entry).split()


def test_parse_entry_with_comment():
    from pgtoolkit.hba import HBAEntry

    entry = HBAEntry.parse("local    all     all     trust  # My  comment")
    assert 'local' == entry.conntype
    assert 'all' == entry.database
    assert 'all' == entry.user
    assert 'trust' == entry.method
    assert 'My comment' == entry.comment

    fields = str(entry).split()
    assert ['local', 'all', 'all', 'trust', '#', 'My', 'comment'] == fields


def test_hba(mocker):
    from pgtoolkit.hba import parse

    lines = HBA_SAMPLE.splitlines(True)
    hba = parse(lines)
    entries = list(iter(hba))

    assert 7 == len(entries)

    hba.save(mocker.Mock(name='file'))


def test_hba_error(mocker):
    from pgtoolkit.hba import parse, ParseError

    with pytest.raises(ParseError) as ei:
        parse(["lcal\n"])
    e = ei.value
    assert 'line #1' in str(e)
    assert repr(e)
