from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParseError(Exception):
    lineno: int
    line: str
    message: str

    def __str__(self) -> str:
        return "Bad line #{} '{:.32}': {}".format(
            self.lineno,
            self.line.strip(),
            self.message,
        )
