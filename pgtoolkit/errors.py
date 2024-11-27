from __future__ import annotations


class ParseError(Exception):
    def __init__(self, lineno: int, line: str, message: str) -> None:
        self.message = message
        super().__init__(self.message)
        self.lineno = lineno
        self.line = line

    def __repr__(self) -> str:
        return "<%s at line %d: %.32s>" % (
            self.__class__.__name__,
            self.lineno,
            self.message,
        )

    def __str__(self) -> str:
        return "Bad line #{} '{:.32}': {}".format(
            self.lineno,
            self.line.strip(),
            self.message,
        )
