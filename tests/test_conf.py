import pathlib
from datetime import timedelta
from io import StringIO
from textwrap import dedent

import pytest


def test_parse_value():
    from pgtoolkit.conf import parse_value

    # Booleans
    assert parse_value("on") is True
    assert parse_value("off") is False
    assert parse_value("true") is True
    assert parse_value("false") is False
    assert parse_value("yes") is True
    assert parse_value("'no'") is False
    assert parse_value("On") is True
    assert parse_value("TRUE") is True
    assert parse_value("fAlSe") is False

    # Numbers
    assert 10 == parse_value("10")
    assert "010" == parse_value("010")
    assert "010" == parse_value("'010'")
    assert 1.4 == parse_value("1.4")
    assert -2 == parse_value("-2")
    assert 0.2 == parse_value("0.2")
    assert 0 == parse_value("0")
    # Numbers, quoted
    assert "0" == parse_value("'0'")
    assert "2.3" == parse_value("'2.3'")

    # Strings
    assert "/a/path/to/file.conf" == parse_value(r"/a/path/to/file.conf")
    assert "0755.log" == parse_value(r"0755.log")
    assert "file_ending_with_B" == parse_value(r"file_ending_with_B")

    # Escaped quotes: double-quotes or backslash-quote are replaced by
    # single-quotes.
    assert "esc'aped string" == parse_value(r"'esc\'aped string'")
    # Expected values in the following assertions should match what
    # psycopg2.extensions.parse_dsn() (or libpq) recognizes.
    assert "host='127.0.0.1'" == parse_value("'host=''127.0.0.1'''")
    assert "user=foo password=se'cret" == parse_value("'user=foo password=se''cret'")
    assert "user=foo password=se''cret" == parse_value("user=foo password=se''cret")
    assert "user=foo password=secret'" == parse_value("'user=foo password=secret'''")
    assert (
        # this one does not work in parse_dsn()
        "user=foo password='secret"
        == parse_value("'user=foo password=''secret'")
    )
    assert "%m [%p] %q%u@%d " == parse_value(r"'%m [%p] %q%u@%d '")
    assert "124.7MB" == parse_value("124.7MB")
    assert "124.7ms" == parse_value("124.7ms")

    # Memory
    assert "1kB" == parse_value("1kB")
    assert "512MB" == parse_value("512MB")
    assert "64 GB" == parse_value(" 64 GB ")
    assert "5TB" == parse_value("5TB")

    # Time
    delta = parse_value("150 ms")
    assert 150000 == delta.microseconds
    delta = parse_value("24s ")
    assert 24 == delta.seconds
    delta = parse_value("' 5 min'")
    assert 300 == delta.seconds
    delta = parse_value("2 h")
    assert 7200 == delta.seconds
    delta = parse_value("5d")
    assert 5 == delta.days

    # Enums
    assert "md5" == parse_value("md5")

    # Errors
    with pytest.raises(ValueError):
        parse_value("'missing last quote")


def test_parser():
    from pgtoolkit.conf import parse, parse_string

    content = dedent(
        """\
    # This file consists of lines of the form:
    #
    #   name = value
    #
    # (The "=" is optional.)  Whitespace may be used.  Comments are introduced with
    # "#" anywhere on a line.  The complete list of parameter names and allowed
    # values can be found in the PostgreSQL documentation.
    #
    # The commented-out settings shown in this file represent the default values.
    # Re-commenting a setting is NOT sufficient to revert it to the default value;
    # you need to reload the server.

    # - Connection Settings -
    listen_addresses = '*'                  # comma-separated list of addresses;
                            # defaults to 'localhost'; use '*' for all
                            # (change requires restart)

    primary_conninfo = 'host=''example.com'' port=5432 dbname=mydb connect_timeout=10'
    port = 5432
    bonjour 'without equals'
    # bonjour_name = ''		# defaults to the computer name
    shared.buffers = 248MB
    #authentication_timeout = 2min      # will be overwritten by the one below
    #authentication_timeout = 1min		# 1s-600s
    # port = 5454  # commented value does not override previous (uncommented) one
    """
    )

    conf = parse_string(content, "/etc/postgres/postgresql.conf")

    assert conf.path == "/etc/postgres/postgresql.conf"

    assert "*" == conf.listen_addresses
    assert (
        str(conf.entries["listen_addresses"])
        == "listen_addresses = '*'  # comma-separated list of addresses;"
    )
    assert 5432 == conf.port
    assert (
        conf.primary_conninfo
        == "host='example.com' port=5432 dbname=mydb connect_timeout=10"
    )
    assert "without equals" == conf.bonjour
    assert "248MB" == conf["shared.buffers"]

    assert conf.entries["bonjour_name"].commented
    assert (
        str(conf.entries["bonjour_name"])
        == "#bonjour_name = ''  # defaults to the computer name"
    )
    assert conf.entries["authentication_timeout"].commented
    assert conf.entries["authentication_timeout"].value == timedelta(minutes=1)
    assert (
        str(conf.entries["authentication_timeout"])
        == "#authentication_timeout = '1 min'  # 1s-600s"
    )

    assert [(e.name, e.value) for e in conf if e.commented] == [
        ("name", "value"),
        ("bonjour_name", ""),
        ("authentication_timeout", timedelta(seconds=60)),
    ]

    dict_ = conf.as_dict()
    assert "*" == dict_["listen_addresses"]

    with pytest.raises(AttributeError):
        conf.inexistent

    with pytest.raises(KeyError):
        conf["inexistent"]

    with pytest.raises(ValueError):
        parse(["bad_line"])


def test_configuration_fields():
    """Configuration fields (the ones from dataclass definition) can be changed."""
    from pgtoolkit.conf import Configuration

    cfg = Configuration(path="my/postgresql.conf")
    assert cfg.path == "my/postgresql.conf"
    cfg.path = "changed/to/postgres.conf"
    assert cfg.path == "changed/to/postgres.conf"
    assert "path" not in cfg and "path" not in cfg.entries


def test_configuration_multiple_entries():
    from pgtoolkit.conf import Configuration

    conf = Configuration()
    list(
        conf.parse(
            [
                "port=5432\n",
                "# port=5423\n",
                "port=5433  # the real one!!\n",
            ]
        )
    )
    assert conf["port"] == 5433
    fo = StringIO()
    conf.save(fo)
    out = fo.getvalue().strip().splitlines()
    assert out == [
        "port=5432",
        "# port=5423",
        "port=5433  # the real one!!",
    ]


def test_parser_includes_require_an_absolute_file_path():
    from pgtoolkit.conf import ParseError, parse

    lines = ["include = 'foo.conf'\n"]
    with pytest.raises(ParseError, match="cannot process include directives"):
        parse(lines)


def test_parser_includes_string_with_absolute_file_path(tmp_path: pathlib.Path):
    from pgtoolkit.conf import parse

    included = tmp_path / "included.conf"
    included.write_text("shared_buffers = 123MG\nmax_connections=45\n")

    lines = [f"include = '{included}'", "cluster_name=foo"]
    conf = parse(lines)
    assert conf.as_dict() == {
        "cluster_name": "foo",
        "max_connections": 45,
        "shared_buffers": "123MG",
    }


def test_parser_includes():
    from pgtoolkit.conf import parse

    fpath = pathlib.Path(__file__).parent / "data" / "postgres.conf"
    conf = parse(str(fpath))
    assert conf.as_dict() == {
        "authentication_timeout": timedelta(seconds=120),
        "autovacuum_work_mem": -1,
        "bonjour": False,
        "bonsoir": True,
        "checkpoint_completion_target": 0.9,
        "cluster_name": "pgtoolkit",
        "listen_addresses": "*",
        "log_line_prefix": "%m %q@%d",
        "log_rotation_age": timedelta(days=1),
        "max_connections": 100,
        "my": True,
        "mymy": False,
        "mymymy": True,
        "pg_stat_statements.max": 10000,
        "pg_stat_statements.track": "all",
        "port": 5432,
        "shared_buffers": "248MB",
        "shared_preload_libraries": "pg_stat_statements",
        "ssl": True,
        "unix_socket_permissions": "0777",
        "wal_level": "hot_standby",
        "some_guc": "2.30",
    }
    assert "include" not in conf
    assert "include_if_exists" not in conf
    assert "include_dir" not in conf

    # Make sure original file is preserved on save (i.e. includes do not
    # interfere).
    fo = StringIO()
    conf.save(fo)
    lines = fo.getvalue().strip().splitlines()
    assert lines[:8] == [
        "include_dir = 'conf.d'",
        "#include_dir = 'conf.11.d'",
        "include = 'postgres-my.conf'",
        "#------------------------------------------------------------------------------",
        "# CONNECTIONS AND AUTHENTICATION",
        "#------------------------------------------------------------------------------",
        "# - Connection Settings -",
        "listen_addresses = '*'                  # comma-separated list of addresses;",
    ]
    assert lines[-5:] == [
        "# Add settings for extensions here",
        "pg_stat_statements.max = 10000",
        "pg_stat_statements.track = all",
        "",
        "some_guc = '2.30'",
    ]


def test_parser_includes_loop(tmp_path):
    from pgtoolkit.conf import parse

    pgconf = tmp_path / "postgres.conf"
    with pgconf.open("w") as f:
        f.write(f"include = '{pgconf.absolute()}'\n")

    with pytest.raises(RuntimeError, match="loop detected"):
        parse(str(pgconf))


def test_parser_includes_notfound(tmp_path):
    from pgtoolkit.conf import parse

    pgconf = tmp_path / "postgres.conf"
    with pgconf.open("w") as f:
        f.write("include = 'missing.conf'\n")
    missing_conf = tmp_path / "missing.conf"
    msg = f"file '{missing_conf}', included from '{pgconf}', not found"
    with pytest.raises(FileNotFoundError, match=msg):
        parse(str(pgconf))

    pgconf = tmp_path / "postgres.conf"
    with pgconf.open("w") as f:
        f.write("include_dir = 'conf.d'\n")
    missing_conf = tmp_path / "conf.d"
    msg = f"directory '{missing_conf}', included from '{pgconf}', not found"
    with pytest.raises(FileNotFoundError, match=msg):
        parse(str(pgconf))


def test_parse_string_include(tmp_path):
    from pgtoolkit.conf import ParseError, parse_string

    with pytest.raises(
        ParseError,
        match="cannot process include directives referencing a relative path",
    ):
        parse_string("work_mem=1MB\ninclude = x\n")


def test_entry_edit():
    from pgtoolkit.conf import Entry

    entry = Entry("port", "1234")
    assert entry.value == 1234
    entry.value = "9876"
    assert entry.value == 9876


def test_entry_constructor_parse_value():
    from pgtoolkit.conf import Entry

    entry = Entry("var", "'1.2'")
    assert entry.value == "1.2"
    entry = Entry("var", "1234")
    assert entry.value == 1234
    # If value come from the parsing of a file (ie. raw_line is provided) value should
    # not be parsed and be kept as is
    entry = Entry("var", "'1.2'", raw_line="var = '1.2'")
    assert entry.value == "'1.2'"


def test_serialize_entry():
    from pgtoolkit.conf import Entry

    e = Entry("grp.setting", True)

    assert "grp.setting" in repr(e)
    assert "grp.setting = on" == str(e)

    assert "'2kB'" == Entry("var", "2kB").serialize()
    assert "2048" == Entry("var", 2048).serialize()
    assert "var = 0" == str(Entry("var", 0))
    assert "var = 15" == str(Entry("var", 15))
    assert "var = 0.1" == str(Entry("var", 0.1))
    assert "var = 'enum'" == str(Entry("var", "enum"))
    assert "addrs = '*'" == str(Entry("addrs", "*"))
    assert "var = 'sp ced'" == str(Entry("var", "sp ced"))
    assert "var = 'quo''ed'" == str(Entry("var", "quo'ed"))
    assert "var = 'quo''ed'' and space'" == str(Entry("var", "quo'ed' and space"))

    assert r"'quo\'ed'" == Entry("var", r"quo\'ed").serialize()
    e = Entry("var", "app=''foo'' host=192.168.0.8")
    assert e.serialize() == "'app=''foo'' host=192.168.0.8'"
    assert str(e) == "var = 'app=''foo'' host=192.168.0.8'"

    e = Entry(
        "primary_conninfo",
        "port=5432 password=pa'sw0'd dbname=postgres",
    )
    assert (
        str(e) == "primary_conninfo = 'port=5432 password=pa''sw0''d dbname=postgres'"
    )

    assert "var = 'quoted'" == str(Entry("var", "'quoted'"))

    assert "'1d'" == Entry("var", timedelta(days=1)).serialize()
    assert "'1h'" == Entry("var", timedelta(minutes=60)).serialize()
    assert "'61 min'" == Entry("var", timedelta(minutes=61)).serialize()
    e = Entry("var", timedelta(microseconds=12000))
    assert "'12 ms'" == e.serialize()

    assert "  # Comment" in str(Entry("var", 1, comment="Comment"))


def test_save():
    from pgtoolkit.conf import parse

    conf = parse(["listen_addresses = *"])
    conf["primary_conninfo"] = "user=repli password=pa'sw0'd"
    fo = StringIO()
    conf.save(fo)
    out = fo.getvalue()
    assert "listen_addresses = *" in out
    assert "primary_conninfo = 'user=repli password=pa''sw0''d'" in out


def test_edit():
    from pgtoolkit.conf import Configuration

    conf = Configuration()
    list(
        conf.parse(
            [
                "#bonjour = off # advertise server via Bonjour\n",
                "#bonjour_name = ''  # defaults to computer name\n",
            ]
        )
    )

    conf.listen_addresses = "*"
    assert "listen_addresses" in conf
    assert "*" == conf.listen_addresses

    assert "port" not in conf
    conf["port"] = 5432
    assert 5432 == conf.port

    conf["port"] = "5433"
    assert 5433 == conf.port

    conf["primary_conninfo"] = "'port=5432 host=''example.com'''"
    assert conf.primary_conninfo == "port=5432 host='example.com'"

    with StringIO() as fo:
        conf.save(fo)
        lines = fo.getvalue().splitlines()

    assert lines == [
        "#bonjour = off # advertise server via Bonjour",
        "#bonjour_name = ''  # defaults to computer name",
        "listen_addresses = '*'",
        "port = 5433",
        "primary_conninfo = 'port=5432 host=''example.com'''",
    ]

    conf["port"] = 5454
    conf["log_line_prefix"] = "[%p]: [%l-1] db=%d,user=%u,app=%a,client=%h "
    conf["bonjour_name"] = "pgserver"
    conf["track_activity_query_size"] = 32768
    with StringIO() as fo:
        conf.save(fo)
        lines = fo.getvalue().splitlines()

    assert lines == [
        "#bonjour = off # advertise server via Bonjour",
        "bonjour_name = 'pgserver'  # defaults to computer name",
        "listen_addresses = '*'",
        "port = 5454",
        "primary_conninfo = 'port=5432 host=''example.com'''",
        "log_line_prefix = '[%p]: [%l-1] db=%d,user=%u,app=%a,client=%h '",
        "track_activity_query_size = 32768",
    ]

    with pytest.raises(ValueError, match="cannot add an include directive"):
        conf["include_if_exists"] = "file.conf"

    with conf.edit() as entries:
        entries.add(
            "external_pid_file",
            "/tmp/11-main.pid",
            comment="write an extra PID file",
        )
        del entries["log_line_prefix"]
        entries["port"].value = "54"
        entries["bonjour"].value = True

    assert conf.port == 54
    assert conf.entries["port"].value == 54

    with StringIO() as fo:
        conf.save(fo)
        lines = fo.getvalue().splitlines()

    expected_lines = [
        "bonjour = on  # advertise server via Bonjour",
        "bonjour_name = 'pgserver'  # defaults to computer name",
        "listen_addresses = '*'",
        "port = 54",
        "primary_conninfo = 'port=5432 host=''example.com'''",
        "track_activity_query_size = 32768",
        "external_pid_file = '/tmp/11-main.pid'  # write an extra PID file",
    ]
    assert lines == expected_lines

    with pytest.raises(ValueError):
        with conf.edit() as entries:
            entries["port"].value = "'invalid"
    assert lines == expected_lines


def test_edit_included_value(tmp_path: pathlib.Path) -> None:
    from pgtoolkit.conf import parse

    included = tmp_path / "included.conf"
    included.write_text("foo = true\nbar= off\n")
    base = tmp_path / "postgresql.conf"
    lines = ["bonjour = on", f"include = {included}", "cluster_name=test"]
    base.write_text("\n".join(lines) + "\n")

    conf = parse(base)
    with pytest.warns(UserWarning, match="entry 'foo' not directly found"):
        with conf.edit() as entries:
            entries["foo"].value = False
            entries["bar"].commented = True

    out = tmp_path / "postgresql-new.conf"
    conf.save(out)
    newlines = out.read_text().splitlines()
    assert newlines == lines + ["foo = off"]

    conf = parse(out)
    assert conf["foo"] is False


def test_configuration_iter():
    from pgtoolkit.conf import Configuration

    conf = Configuration()
    conf.port = 5432
    conf.log_timezone = "Europe/Paris"
    assert [e.name for e in conf] == ["port", "log_timezone"]
