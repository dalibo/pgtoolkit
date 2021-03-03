from datetime import datetime, timedelta
import json
import sys
from pathlib import Path
from typing import (
    Any,
    Generic,
    IO,
    NoReturn,
    Optional,
    TypeVar,
    Union,
    overload,
)


def format_timedelta(delta: timedelta) -> str:
    values = [
        (delta.days, "d"),
        (delta.seconds, "s"),
        (delta.microseconds, "us"),
    ]
    values = ["%d%s" % v for v in values if v[0]]
    if values:
        return " ".join(values)
    else:
        return "0s"


class JSONDateEncoder(json.JSONEncoder):
    def default(self, obj: Union[timedelta, datetime, object]) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, timedelta):
            return format_timedelta(obj)
        return super().default(obj)


def open_or_stdin(filename: str, stdin: IO[str] = sys.stdin) -> IO[str]:
    if filename == "-":
        fo = stdin
    else:
        fo = open(filename)
    return fo


T = TypeVar("T")


class PassthroughManager(Generic[T]):
    def __init__(self, ret: T) -> None:
        self.ret = ret

    def __enter__(self) -> T:
        return self.ret

    def __exit__(self, *a: Any) -> None:
        pass


@overload
def open_or_return(fo_or_path: None, mode: str = "r") -> NoReturn:
    ...


@overload
def open_or_return(fo_or_path: str, mode: str = "r") -> IO[str]:
    ...


@overload
def open_or_return(fo_or_path: Path, mode: str = "r") -> IO[str]:
    ...


@overload
def open_or_return(fo_or_path: IO[str], mode: str = "r") -> PassthroughManager[IO[str]]:
    ...


def open_or_return(
    fo_or_path: Optional[Union[str, Path, IO[str]]], mode: str = "r"
) -> Union[IO[str], PassthroughManager[IO[str]]]:
    # Returns a context manager around a file-object for fo_or_path. If
    # fo_or_path is a file-object, the context manager keeps it open. If it's a
    # path, the file is opened with mode and will be closed upon context exit.
    # If fo_or_path is None, a ValueError is raised.

    if fo_or_path is None:
        raise ValueError("No file-like object nor path provided")
    if isinstance(fo_or_path, str):
        return open(fo_or_path, mode)
    if isinstance(fo_or_path, Path):
        return fo_or_path.open(mode)

    # Skip default file context manager. This allows to always use with
    # statement and don't care about closing the file. If the file is opened
    # here, it will be closed properly. Otherwise, it will be kept open thanks
    # to PassthroughManager.
    return PassthroughManager(fo_or_path)


class Timer:
    def __enter__(self) -> "Timer":
        self.start = datetime.utcnow()
        return self

    def __exit__(self, *a: Any) -> None:
        self.delta = datetime.utcnow() - self.start
