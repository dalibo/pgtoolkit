import shlex
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio

from pgtoolkit import ctl  # noqa: E402


def test__args_to_opts():
    opts = ctl._args_to_opts(
        {
            "encoding": "latin1",
            "auth_local": "trust",
            "show": True,
            "n": True,
            "L": "DIR",
        }
    )
    assert opts == [
        "-L DIR",
        "--auth-local=trust",
        "--encoding=latin1",
        "-n",
        "--show",
    ]


def test__wait_args_to_opts():
    assert ctl._wait_args_to_opts(False) == ["--no-wait"]
    assert ctl._wait_args_to_opts(True) == ["--wait"]
    assert ctl._wait_args_to_opts(42) == ["--wait", "--timeout=42"]


@pytest.fixture
def bindir(tmp_path: Path) -> Path:
    (tmp_path / "pg_ctl").touch(mode=0o777)
    with open(tmp_path / "pg_ctl", "w") as f:
        f.write("#!/bin/sh\necho 'pg_ctl (PostgreSQL) 11.10'")
    return tmp_path


def run_command_version_only(
    args: Sequence[str], **kwargs: Any
) -> ctl.CompletedProcess:
    try:
        executable, *opts = args
    except ValueError:
        pass
    else:
        if executable.endswith("/pg_ctl") and opts == ["--version"]:
            return subprocess.CompletedProcess(
                args, 0, stdout="pg_ctl (PostgreSQL) 11.10\n", stderr=""
            )
    pytest.fail(f"unexpectedly called with: {args}")


@pytest.fixture
def pgctl(bindir: Path) -> ctl.PGCtl:
    c = ctl.PGCtl(bindir, run_command=run_command_version_only)
    c.pg_ctl = Path("pg_ctl")
    return c


def test_version(pgctl: ctl.AsyncPGCtl) -> None:
    assert pgctl.version == 110010


def test_init_cmd(pgctl: ctl.PGCtl) -> None:
    assert pgctl.init_cmd(
        "data",
        auth_local="md5",
        data_checksums=True,
        g=True,
        X="wal",
    ) == shlex.split(
        "pg_ctl init -D data -o '-X wal --auth-local=md5 --data-checksums -g'"
    )


def test_start_cmd(pgctl: ctl.PGCtl) -> None:
    assert pgctl.start_cmd("data") == shlex.split("pg_ctl start -D data --wait")
    assert pgctl.start_cmd("data", wait=False) == shlex.split(
        "pg_ctl start -D data --no-wait"
    )
    assert pgctl.start_cmd(
        "data",
        wait=3,
        logfile="logfile",
    ) == shlex.split("pg_ctl start -D data --wait --timeout=3 --log=logfile")
    assert pgctl.start_cmd("data", k="/tmp/sockets") == shlex.split(
        "pg_ctl start -D data --wait -o '-k /tmp/sockets'"
    )


def test_stop_cmd(pgctl: ctl.PGCtl) -> None:
    assert pgctl.stop_cmd("data") == shlex.split("pg_ctl stop -D data --wait")
    assert pgctl.stop_cmd("data", wait=False) == shlex.split(
        "pg_ctl stop -D data --no-wait"
    )
    assert pgctl.stop_cmd(
        "data",
        wait=3,
        mode="fast",
    ) == shlex.split("pg_ctl stop -D data --wait --timeout=3 --mode=fast")


def test_restart_cmd(pgctl: ctl.PGCtl) -> None:
    assert pgctl.restart_cmd("data") == shlex.split("pg_ctl restart -D data --wait")
    assert pgctl.restart_cmd("data", wait=False) == shlex.split(
        "pg_ctl restart -D data --no-wait"
    )
    assert pgctl.restart_cmd(
        "data",
        wait=3,
        mode="fast",
    ) == shlex.split("pg_ctl restart -D data --wait --timeout=3 --mode=fast")
    assert pgctl.restart_cmd("data", k="/tmp/sockets") == shlex.split(
        "pg_ctl restart -D data --wait -o '-k /tmp/sockets'"
    )


def test_reload_cmd(pgctl: ctl.PGCtl) -> None:
    assert pgctl.reload_cmd("data") == shlex.split("pg_ctl reload -D data")


def test_status_cmd(pgctl: ctl.PGCtl) -> None:
    assert pgctl.status_cmd("data") == shlex.split("pg_ctl status -D data")


@pytest.mark.parametrize(
    "returncode, status",
    [
        [0, ctl.Status.running],
        [3, ctl.Status.not_running],
        [4, ctl.Status.unspecified_datadir],
    ],
)
def test_status(pgctl: ctl.PGCtl, returncode: int, status: ctl.Status) -> None:
    with patch.object(
        pgctl, "run_command", return_value=subprocess.CompletedProcess([], returncode)
    ) as run_command:
        actual = pgctl.status("data")
    run_command.assert_called_once_with(["pg_ctl", "status", "-D", "data"])
    assert actual == status


def test_status_returncode1(pgctl: ctl.PGCtl) -> None:
    with patch.object(
        pgctl, "run_command", return_value=subprocess.CompletedProcess([], 1)
    ) as run_command, pytest.raises(subprocess.CalledProcessError):
        pgctl.status("data")
    run_command.assert_called_once_with(["pg_ctl", "status", "-D", "data"])


@pytest_asyncio.fixture
async def apgctl(bindir: Path) -> ctl.AsyncPGCtl:
    async def run_command(args: Sequence[str], **kwargs: Any) -> ctl.CompletedProcess:
        return run_command_version_only(args, **kwargs)

    c = await ctl.AsyncPGCtl.get(bindir, run_command=run_command)
    c.pg_ctl = Path("pg_ctl")
    return c


@pytest.mark.asyncio
async def test_version_async(apgctl: ctl.AsyncPGCtl) -> None:
    assert apgctl.version == 110010


@pytest.mark.parametrize(
    "rc, status",
    [
        [0, ctl.Status.running],
        [3, ctl.Status.not_running],
        [4, ctl.Status.unspecified_datadir],
    ],
)
@pytest.mark.asyncio
async def test_status_async(
    apgctl: ctl.AsyncPGCtl, rc: int, status: ctl.Status
) -> None:
    with patch.object(
        apgctl, "run_command", return_value=subprocess.CompletedProcess([], rc)
    ) as run_command:
        actual = await apgctl.status("data")
    run_command.assert_called_once_with(["pg_ctl", "status", "-D", "data"])
    assert actual == status


@pytest.mark.asyncio
async def test_status_returncode1_async(apgctl: ctl.AsyncPGCtl) -> None:
    with patch.object(
        apgctl, "run_command", return_value=subprocess.CompletedProcess([], 1)
    ) as run_command, pytest.raises(subprocess.CalledProcessError):
        await apgctl.status("data")
    run_command.assert_called_once_with(["pg_ctl", "status", "-D", "data"])


def test_parse_controldata() -> None:
    lines = [
        "pg_control version number:            1100",
        "Catalog version number:               201809051",
        "Database system identifier:           6798427594087098476",
        "Database cluster state:               shut down",
        "pg_control last modified:             Tue 07 Jul 2020 01:08:58 PM CEST",
        "WAL block size:                       8192",
    ]
    controldata = ctl.parse_control_data(lines)
    assert controldata == {
        "Catalog version number": "201809051",
        "Database cluster state": "shut down",
        "Database system identifier": "6798427594087098476",
        "WAL block size": "8192",
        "pg_control last modified": "Tue 07 Jul 2020 01:08:58 PM CEST",
        "pg_control version number": "1100",
    }
