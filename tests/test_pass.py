from pathlib import Path

import pytest


def test_escaped_split():
    from pgtoolkit.pgpass import escapedsplit

    assert ["a", "b"] == list(escapedsplit("a:b", ":"))
    assert ["a", ""] == list(escapedsplit("a:", ":"))
    assert ["a:"] == list(escapedsplit(r"a\:", ":"))
    assert ["a\\", ""] == list(escapedsplit(r"a\\:", ":"))

    with pytest.raises(ValueError):
        list(escapedsplit(r"", "long-delim"))


def test_passfile_create():
    from pgtoolkit.pgpass import PassComment, PassEntry, PassFile

    pgpass = PassFile([PassComment("# Comment"), PassEntry.parse("foo:*:bar:baz:dude")])
    assert 2 == len(pgpass.lines)

    with pytest.raises(ValueError):
        PassFile("blah")


def test_entry():
    from pgtoolkit.pgpass import PassEntry

    a = PassEntry.parse(r"/var/run/postgresql:5432:db:postgres:conf\:dentie\\")
    assert "/var/run/postgresql" == a.hostname
    assert 5432 == a.port
    assert "db" == a.database
    assert "postgres" == a.username
    assert "conf:dentie\\" == a.password

    assert "dentie\\" not in repr(a)
    assert r"conf\:dentie\\" in str(a)

    b = PassEntry(
        hostname="/var/run/postgresql",
        port=5432,
        database="db",
        username="postgres",
        password="newpassword",
    )

    entries = set([a])

    assert b in entries


def test_compare():
    from pgtoolkit.pgpass import PassComment, PassEntry

    a = PassEntry.parse(":*:*:*:confidentiel")
    b = PassEntry.parse("hostname:*:*:*:otherpassword")
    c = PassEntry.parse("hostname:5442:*:username:otherpassword")
    d = PassEntry("hostname", "5442", "*", "username", "otherpassword")
    e = PassEntry("hostname", "5443", "*", "username", "otherpassword")

    assert a < b
    assert c < b
    assert a != b
    assert c == d
    assert c < e

    assert [c, a, b] == sorted([a, b, c])

    d = PassComment("# Comment")
    e = PassComment("# hostname:5432:*:*:password")

    assert "Comment" in repr(d)

    # Preserve comment order.
    assert not d < e
    assert not e < d
    assert not d < a
    assert not a < d
    assert a != d

    assert e < a
    assert c < e

    with pytest.raises(TypeError):
        a < 42
    with pytest.raises(TypeError):
        "meh" > a
    assert (a == [1, 2]) is False


def test_parse_lines(tmp_path):
    from pgtoolkit.pgpass import ParseError, parse

    lines = [
        "# Comment for h2",
        "h2:*:*:postgres:confidentiel",
        "# h1:*:*:postgres:confidentiel",
        "h2:5432:*:postgres:confidentiel",
    ]

    pgpass = parse(lines)
    with pytest.raises(ParseError):
        pgpass.parse(["bad:line"])

    pgpass.sort()

    # Ensure more precise line first.
    assert "h2:5432:" in str(pgpass.lines[0])
    # Ensure h1 line is before h2 line, even commented.
    assert "# h1:" in str(pgpass.lines[1])
    # Ensure comment is kept before h2:* line.
    assert "Comment" in str(pgpass.lines[2])
    assert "h2:*" in str(pgpass.lines[3])

    assert 2 == len(list(pgpass))

    passfile = tmp_path / "fo"
    with passfile.open("w") as fo:
        pgpass.save(fo)
    assert passfile.read_text().splitlines() == [
        "h2:5432:*:postgres:confidentiel",
        "# h1:*:*:postgres:confidentiel",
        "# Comment for h2",
        "h2:*:*:postgres:confidentiel",
    ]

    header = "#hostname:port:database:username:password"
    pgpass = parse([header])
    pgpass.sort()
    assert pgpass.lines == [header]


@pytest.mark.parametrize("pathtype", [str, Path])
def test_parse_file(pathtype, tmp_path):
    from pgtoolkit.pgpass import PassComment, parse

    fpath = tmp_path / "pgpass"
    fpath.touch()
    pgpass = parse(pathtype(fpath))
    pgpass.lines.append(PassComment("# Something"))
    pgpass.save()
    assert fpath.read_text() == "# Something\n"


def test_edit(tmp_path):
    from pgtoolkit.pgpass import PassComment, PassEntry, edit

    fpath = tmp_path / "pgpass"
    assert not fpath.exists()

    # Check we don't create an empty file.
    with edit(fpath):
        pass
    assert not fpath.exists()

    with edit(fpath) as passfile:
        passfile.lines.append(PassComment("# commented"))
    assert fpath.read_text() == "# commented\n"

    with edit(fpath) as passfile:
        passfile.lines.extend(
            [
                PassEntry("*", "5443", "*", "username", "otherpassword"),
                PassEntry("hostname", "5443", "*", "username", "password"),
            ]
        )
        passfile.sort()
    assert fpath.read_text().splitlines() == [
        "hostname:5443:*:username:password",
        "# commented",
        "*:5443:*:username:otherpassword",
    ]


def test_save_nofile():
    from pgtoolkit.pgpass import PassComment, PassFile

    pgpass = PassFile()
    pgpass.lines.append(PassComment("# Something"))
    with pytest.raises(ValueError):
        pgpass.save()


def test_matches():
    from pgtoolkit.pgpass import PassComment, PassEntry

    a = PassEntry(
        hostname="/var/run/postgresql",
        port=5432,
        database="db",
        username="postgres",
        password="newpassword",
    )
    assert a.matches(port=5432, database="db")
    with pytest.raises(AttributeError):
        assert a.matches(dbname="newpassword")
    assert not a.matches(port=5433)

    b = PassComment("# some non-entry comment")
    assert not b.matches(port=5432)

    c = PassComment("# hostname:5432:*:*:password")
    assert c.matches(port=5432)


def test_remove():
    from pgtoolkit.pgpass import parse

    lines = [
        "# Comment for h2",
        "h2:*:*:postgres:confidentiel",
        "# h1:*:*:postgres:confidentiel",
        "h2:5432:*:postgres:confidentiel",
        "h2:5432:*:david:Som3Password",
        "h2:5433:*:postgres:confidentiel",
    ]

    pgpass = parse(lines)

    with pytest.raises(ValueError):
        pgpass.remove()

    pgpass.remove(port=5432)
    assert 4 == len(pgpass.lines)

    # All matching entries are removed even commented ones
    pgpass = parse(lines)
    pgpass.remove(username="postgres")
    assert 2 == len(pgpass.lines)

    pgpass = parse(lines)
    pgpass.remove(port=5432, username="postgres")
    assert 5 == len(pgpass.lines)

    def filter(line):
        return line.username == "postgres"

    pgpass = parse(lines)
    pgpass.remove(filter=filter)
    assert 2 == len(pgpass.lines)

    # Only filter is taken into account
    pgpass = parse(lines)
    with pytest.warns(UserWarning):
        pgpass.remove(filter=filter, port=5432)
    assert 2 == len(pgpass.lines)

    # Error if attribute name is not valid
    pgpass = parse(lines)
    with pytest.raises(AttributeError):
        pgpass.remove(userna="postgres")
