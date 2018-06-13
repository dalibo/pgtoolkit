import pytest


def test_escaped_split():
    from pgtoolkit.pgpass import escapedsplit

    assert ['a', 'b'] == list(escapedsplit('a:b', ':'))
    assert ['a', ''] == list(escapedsplit('a:', ':'))
    assert ['a:'] == list(escapedsplit(r'a\:', ':'))
    assert ['a\\', ''] == list(escapedsplit(r'a\\:', ':'))

    with pytest.raises(ValueError):
        list(escapedsplit(r'', 'long-delim'))


def test_entry():
    from pgtoolkit.pgpass import PassEntry

    a = PassEntry.parse(r'/var/run/postgresql:5432:db:postgres:conf\:dentie\\')
    assert '/var/run/postgresql' == a.hostname
    assert 5432 == a.port
    assert 'db' == a.database
    assert 'postgres' == a.username
    assert 'conf:dentie\\' == a.password

    assert 'dentie\\' not in repr(a)
    assert r'conf\:dentie\\' in str(a)

    b = PassEntry(
        hostname='/var/run/postgresql',
        port=5432,
        database='db',
        username='postgres',
        password='newpassword',
    )

    entries = set([a])

    assert b in entries


def test_compare():
    from pgtoolkit.pgpass import PassComment, PassEntry

    a = PassEntry.parse(':*:*:*:confidentiel')
    b = PassEntry.parse('hostname:*:*:*:otherpassword')
    c = PassEntry.parse('hostname:5442:*:username:otherpassword')

    assert a < b
    assert c < b

    assert [c, a, b] == sorted([a, b, c])

    d = PassComment('# Comment')
    e = PassComment('# hostname:5432:*:*:password')

    assert 'Comment' in repr(d)

    # Preserve comment order.
    assert not d < e
    assert not e < d
    assert not d < a
    assert not a < d
    assert a != d

    assert e < a
    assert c < e


def test_file(mocker):
    from pgtoolkit.pgpass import parse, ParseError

    lines = [
        '# Comment for h2',
        'h2:*:*:postgres:confidentiel',
        '# h1:*:*:postgres:confidentiel',
        'h2:5432:*:postgres:confidentiel',
    ]

    pgpass = parse(lines)
    with pytest.raises(ParseError):
        pgpass.parse(['bad:line'])

    pgpass.sort()

    # Ensure more precise line first.
    assert 'h2:5432:' in str(pgpass.lines[0])
    # Ensure h1 line is before h2 line, even commented.
    assert '# h1:' in str(pgpass.lines[1])
    # Ensure comment is kept before h2:* line.
    assert 'Comment' in str(pgpass.lines[2])
    assert 'h2:*' in str(pgpass.lines[3])

    assert 2 == len(list(pgpass))

    pgpass.save(mocker.Mock(name='fo'))
