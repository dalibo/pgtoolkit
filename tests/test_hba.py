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
host    all             u0,u1           127.0.0.1/32            trust
# IPv6 local connections:
host    all             +group,u2       ::1/128                 trust
# Allow replication connections from localhost, by a user with the
# replication privilege.
local   replication     all                                     trust
host replication  all        127.0.0.1  255.255.255.255         trust
host    replication     all             ::1/128                 trust

host all all all trust
"""


def test_comment():
    from pgtoolkit.hba import HBAComment

    comment = HBAComment("# toto")
    assert "toto" in repr(comment)
    assert "# toto" == str(comment)


def test_parse_host_line():
    from pgtoolkit.hba import HBARecord

    record = HBARecord.parse("host    replication   all   ::1/128       trust")
    assert "host" in repr(record)
    assert "host" == record.conntype
    assert "replication" == record.database
    assert ["replication"] == record.databases
    assert "all" == record.user
    assert ["all"] == record.users
    assert "::1/128" == record.address
    assert "trust" == record.method

    # This is not actually a public API. But let's keep it stable.
    values = record.common_values
    assert "trust" in values


def test_parse_local_line():
    from pgtoolkit.hba import HBARecord

    record = HBARecord.parse("local    all     all     trust")
    assert "local" == record.conntype
    assert "all" == record.database
    assert ["all"] == record.users
    assert "trust" == record.method

    with pytest.raises(AttributeError):
        record.address

    wanted = (
        "local   all             all                                     trust"  # noqa
    )
    assert wanted == str(record)


def test_parse_auth_option():
    from pgtoolkit.hba import HBARecord

    record = HBARecord.parse(
        "local veryverylongdatabasenamethatdonotfit all ident map=omicron",
    )
    assert "local" == record.conntype
    assert "veryverylongdatabasenamethatdonotfit" == record.database
    assert ["all"] == record.users
    assert "ident" == record.method
    assert "omicron" == record.map

    wanted = [
        "local",
        "veryverylongdatabasenamethatdonotfit",
        "all",
        "ident",
        'map="omicron"',
    ]
    assert wanted == str(record).split()


def test_parse_record_with_comment():
    from pgtoolkit.hba import HBARecord

    record = HBARecord.parse("local    all     all     trust  # My  comment")
    assert "local" == record.conntype
    assert "all" == record.database
    assert ["all"] == record.users
    assert "trust" == record.method
    assert "My comment" == record.comment

    fields = str(record).split()
    assert ["local", "all", "all", "trust", "#", "My", "comment"] == fields


def test_parse_invalid_connection_type():
    from pgtoolkit.hba import HBARecord

    with pytest.raises(ValueError, match="Unknown connection type 'pif'"):
        HBARecord.parse("pif    all     all")


def test_parse_record_with_backslash():
    from pgtoolkit.hba import HBARecord

    record = HBARecord.parse(
        r'host all all all ldap ldapserver=host.local ldapprefix="DOMAINE\"'
    )
    assert record.ldapprefix == "DOMAINE\\"


def test_parse_record_with_double_quoting():
    from pgtoolkit.hba import HBARecord

    record = HBARecord.parse(
        r'host all all all radius radiusservers="server1,server2" radiussecrets="""secret one"",""secret two"""'
    )
    assert record.radiussecrets == '""secret one"",""secret two""'


def test_parse_record_blank_in_quotes():
    from pgtoolkit.hba import HBARecord

    record = HBARecord.parse(
        r"host all all all ldap ldapserver=ldap.example.net"
        r' ldapbasedn="dc=example, dc=net"'
        r' ldapsearchfilter="(|(uid=$username)(mail=$username))"'
    )
    assert record.ldapserver == "ldap.example.net"
    assert record.ldapbasedn == "dc=example, dc=net"
    assert record.ldapsearchfilter == "(|(uid=$username)(mail=$username))"


def test_hba(mocker):
    from pgtoolkit.hba import parse

    lines = HBA_SAMPLE.splitlines(True)
    hba = parse(lines)
    entries = list(iter(hba))

    assert 7 == len(entries)

    hba.save(mocker.Mock(name="file"))


def test_hba_create():
    from pgtoolkit.hba import HBA, HBAComment, HBARecord

    hba = HBA(
        [
            HBAComment("# a comment"),
            HBARecord(
                conntype="local",
                database="all",
                user="all",
                method="trust",
            ),
        ]
    )
    assert 2 == len(hba.lines)

    r = hba.lines[1]
    assert ["all"] == r.databases

    # Should be a list
    with pytest.raises(ValueError):
        HBA("blah")


def test_parse_file(mocker):
    from pgtoolkit.hba import HBAComment, parse

    m = mocker.mock_open()
    try:
        mocker.patch("builtins.open", m)
    except Exception:
        mocker.patch("__builtin__.open", m)
    pgpass = parse("filename")
    pgpass.lines.append(HBAComment("# Something"))

    assert m.called
    pgpass.save()
    handle = m()
    handle.write.assert_called_with("# Something\n")

    # Also works for other string types
    m.reset_mock()
    pgpass = parse("filename")
    pgpass.lines.append(HBAComment("# Something"))
    assert m.called


def test_hba_error(mocker):
    from pgtoolkit.hba import ParseError, parse

    with pytest.raises(ParseError) as ei:
        parse(["lcal all all\n"])
    e = ei.value
    assert "line #1" in str(e)
    assert repr(e)

    with pytest.raises(ParseError) as ei:
        parse(["local incomplete\n"])


def test_remove():

    from pgtoolkit.hba import parse

    lines = HBA_SAMPLE.splitlines(True)
    hba = parse(lines)

    with pytest.raises(ValueError):
        hba.remove()

    hba.remove(database="replication")
    entries = list(iter(hba))
    assert 4 == len(entries)

    hba = parse(lines)
    hba.remove(filter=lambda r: r.database == "replication")
    entries = list(iter(hba))
    assert 4 == len(entries)

    hba = parse(lines)
    hba.remove(conntype="host", database="replication")
    entries = list(iter(hba))
    assert 5 == len(entries)

    # Works even for fields that may not be valid for all records
    # `address` is not valid for `local` connection type
    hba = parse(lines)
    hba.remove(address="127.0.0.1/32")
    entries = list(iter(hba))
    assert 6 == len(entries)

    def filter(r):
        return r.conntype == "host" and r.database == "replication"

    hba = parse(lines)
    hba.remove(filter=filter)
    entries = list(iter(hba))
    assert 5 == len(entries)

    # Only filter is taken into account
    hba = parse(lines)
    with pytest.warns(UserWarning):
        hba.remove(filter=filter, database="replication")
    entries = list(iter(hba))
    assert 5 == len(entries)

    # Error if attribute name is not valid
    hba = parse(lines)
    with pytest.raises(AttributeError):
        hba.remove(foo="postgres")


def test_merge():
    import os

    from pgtoolkit.hba import parse

    sample = """\
    # comment
    host replication all all trust
    # other comment
    host replication  all        127.0.0.1  255.255.255.255         trust
    # Comment should be kept
    host all all all trust"""
    lines = sample.splitlines(True)
    hba = parse(lines)

    other_sample = """\
    # line with no address
    local   all             all                                     trust
    # comment before 1.2.3.4 line
    host replication all 1.2.3.4 trust
    # method changed to 'peer'
    # second comment
    host all all all peer
    """
    other_lines = other_sample.splitlines(True)
    other_hba = parse(other_lines)
    hba.merge(other_hba)

    expected_sample = """\
    # comment
    host replication all all trust
    # other comment
    host replication  all        127.0.0.1  255.255.255.255         trust
    # Comment should be kept
    # method changed to 'peer'
    # second comment
    host all all all peer
    # line with no address
    local   all             all                                     trust
    # comment before 1.2.3.4 line
    host replication all 1.2.3.4 trust
    """
    expected_lines = expected_sample.splitlines(True)
    expected_hba = parse(expected_lines)

    def r(hba):
        return os.linesep.join([str(line) for line in hba.lines])

    assert r(hba) == r(expected_hba)
