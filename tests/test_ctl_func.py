import socket
import stat
from pathlib import Path

import pytest
import pytest_asyncio

from pgtoolkit import ctl, hba


@pytest.fixture(scope="module")
def pgctl() -> ctl.PGCtl:
    try:
        return ctl.PGCtl()
    except OSError as e:
        pytest.skip(str(e))


@pytest_asyncio.fixture(scope="module")
async def apgctl() -> ctl.AsyncPGCtl:
    try:
        return await ctl.AsyncPGCtl.get()
    except OSError as e:
        pytest.skip(str(e))


def test_pgctl(pgctl: ctl.PGCtl) -> None:
    assert pgctl.pg_ctl


def test_pgctl_async(apgctl: ctl.AsyncPGCtl) -> None:
    assert apgctl.pg_ctl


@pytest.fixture(scope="module")
def initdb(tmp_path_factory, pgctl: ctl.PGCtl) -> tuple[Path, Path, Path]:
    datadir = tmp_path_factory.mktemp("data")
    waldir = tmp_path_factory.mktemp("wal")
    pgctl.init(
        datadir,
        auth_local="scram-sha-256",
        data_checksums=True,
        g=True,
        X=waldir,
    )
    run_path = tmp_path_factory.mktemp("run")
    pid_path = run_path / "pid"
    with (datadir / "postgresql.conf").open("a") as f:
        f.write(f"\nunix_socket_directories = '{run_path}'")
        f.write(f"\nexternal_pid_file = '{pid_path}'")
    return datadir, waldir, pid_path


@pytest_asyncio.fixture(scope="module")
async def ainitdb(tmp_path_factory, apgctl: ctl.AsyncPGCtl) -> tuple[Path, Path, Path]:
    datadir = tmp_path_factory.mktemp("data")
    waldir = tmp_path_factory.mktemp("wal")
    await apgctl.init(
        datadir,
        auth_local="scram-sha-256",
        data_checksums=True,
        g=True,
        X=waldir,
    )
    run_path = tmp_path_factory.mktemp("run")
    pid_path = run_path / "pid"
    with (datadir / "postgresql.conf").open("a") as f:
        f.write(f"\nunix_socket_directories = '{run_path}'")
        f.write(f"\nexternal_pid_file = '{pid_path}'")
    return datadir, waldir, pid_path


def _check_initdb(datadir: Path, waldir: Path, pid_path: Path) -> None:
    assert (datadir / "PG_VERSION").exists()
    assert (waldir / "archive_status").is_dir()
    with (datadir / "pg_hba.conf").open() as f:
        pghba = hba.parse(f)
    assert next(iter(pghba)).method == "scram-sha-256"
    st_mode = datadir.stat().st_mode
    assert st_mode & stat.S_IRGRP
    assert st_mode & stat.S_IXGRP
    assert not st_mode & stat.S_IWGRP


def test_init(initdb: tuple[Path, Path, Path]) -> None:
    _check_initdb(*initdb)


@pytest.mark.asyncio
async def test_init_async(ainitdb: tuple[Path, Path, Path]) -> None:
    _check_initdb(*ainitdb)


@pytest.fixture
def tmp_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    with s:
        port = s.getsockname()[1]
    return port


def test_start_stop_status_restart_reload(
    initdb: tuple[Path, Path, Path], pgctl: ctl.PGCtl, tmp_port: int
) -> None:
    from psycopg2 import connect

    datadir, __, pidpath = initdb
    assert pgctl.status("invalid") == ctl.Status.unspecified_datadir
    assert pgctl.status(str(datadir)) == ctl.Status.not_running
    assert not pidpath.exists()
    pgctl.start(str(datadir), logfile=datadir / "logs", port=str(tmp_port))
    assert pidpath.exists()
    pid1 = pidpath.read_text()

    connection = connect(dbname="postgres", host="0.0.0.0", port=tmp_port)
    assert connection.info.server_version == pgctl.version

    assert pgctl.status(str(datadir)) == ctl.Status.running
    pgctl.restart(str(datadir), mode="immediate", wait=2)
    pid2 = pidpath.read_text()
    assert pid2 != pid1
    assert pgctl.status(str(datadir)) == ctl.Status.running
    pgctl.reload(str(datadir))
    pid3 = pidpath.read_text()
    assert pid3 == pid2
    assert pgctl.status(str(datadir)) == ctl.Status.running
    pgctl.stop(str(datadir), mode="smart")
    assert not pidpath.exists()
    assert pgctl.status(str(datadir)) == ctl.Status.not_running


@pytest.mark.asyncio
async def test_start_stop_status_restart_reload_async(
    ainitdb: tuple[Path, Path, Path], apgctl: ctl.AsyncPGCtl, tmp_port: int
) -> None:
    from psycopg2 import connect

    datadir, __, pidpath = ainitdb
    assert (await apgctl.status("invalid")) == ctl.Status.unspecified_datadir
    assert (await apgctl.status(str(datadir))) == ctl.Status.not_running
    assert not pidpath.exists()
    await apgctl.start(str(datadir), logfile=datadir / "logs", port=str(tmp_port))
    assert pidpath.exists()
    pid1 = pidpath.read_text()

    connection = connect(dbname="postgres", host="0.0.0.0", port=tmp_port)
    assert connection.info.server_version == apgctl.version

    assert (await apgctl.status(str(datadir))) == ctl.Status.running
    await apgctl.restart(str(datadir), mode="immediate", wait=2)
    pid2 = pidpath.read_text()
    assert pid2 != pid1
    assert (await apgctl.status(str(datadir))) == ctl.Status.running
    await apgctl.reload(str(datadir))
    pid3 = pidpath.read_text()
    assert pid3 == pid2
    assert (await apgctl.status(str(datadir))) == ctl.Status.running
    await apgctl.stop(str(datadir), mode="smart")
    assert not pidpath.exists()
    assert (await apgctl.status(str(datadir))) == ctl.Status.not_running


def test_controldata(initdb: tuple[Path, Path, Path], pgctl: ctl.PGCtl) -> None:
    datadir, __, __ = initdb
    controldata = pgctl.controldata(datadir=datadir)
    assert "Database block size" in controldata
    assert controldata["Database block size"] == "8192"
    assert "Database cluster state" in controldata


@pytest.mark.asyncio
async def test_controldata_async(
    ainitdb: tuple[Path, Path, Path], apgctl: ctl.AsyncPGCtl
) -> None:
    datadir, __, __ = ainitdb
    controldata = await apgctl.controldata(datadir=datadir)
    assert "Database block size" in controldata
    assert controldata["Database block size"] == "8192"
    assert "Database cluster state" in controldata
