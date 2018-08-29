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


def test_matches():
    from pgtoolkit.pgpass import PassComment, PassEntry

    a = PassEntry(
        hostname='/var/run/postgresql',
        port=5432,
        database='db',
        username='postgres',
        password='newpassword',
    )
    assert a.matches(port=5432, database='db')
    with pytest.raises(AttributeError):
        assert a.matches(dbname='newpassword')
    assert not a.matches(port=5433)

    b = PassComment('# some non-entry comment')
    assert not b.matches(port=5432)

    c = PassComment('# hostname:5432:*:*:password')
    assert c.matches(port=5432)


def test_remove():
    from pgtoolkit.pgpass import parse
    lines = [
        '# Comment for h2',
        'h2:*:*:postgres:confidentiel',
        '# h1:*:*:postgres:confidentiel',
        'h2:5432:*:postgres:confidentiel',
        'h2:5432:*:david:Som3Password',
        'h2:5433:*:postgres:confidentiel',
    ]

    pgpass = parse(lines)

    with pytest.raises(ValueError):
        pgpass.remove()

    pgpass.remove(port=5432)
    assert 4 == len(pgpass.lines)

    # All matching entries are removed even commented ones
    pgpass = parse(lines)
    pgpass.remove(username='postgres')
    assert 2 == len(pgpass.lines)

    pgpass = parse(lines)
    pgpass.remove(port=5432, username='postgres')
    assert 5 == len(pgpass.lines)

    # Error if attribute name is not valid
    pgpass = parse(lines)
    with pytest.raises(AttributeError):
        pgpass.remove(userna='postgres')
