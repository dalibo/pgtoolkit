from __future__ import annotations


class ParseError(Exception):
    def __init__(self, lineno: int, line: str, message: str) -> None:
        super().__init__(message)
        self.lineno = lineno
        self.line = line

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} at line {self.lineno}: {self.args[0]:.32}>"

    def __str__(self) -> str:
        return f"Bad line #{self.lineno} '{self.line.strip():.32}': {self.args[0]}"
