class ParseError(Exception):
    def __init__(self, lineno: int, line: str, message: str) -> None:
        super().__init__(message)
        self.lineno = lineno
        self.line = line

    def __repr__(self) -> str:
        return "<%s at line %d: %.32s>" % (
            self.__class__.__name__,
            self.lineno,
            self.args[0],
        )

    def __str__(self) -> str:
        return "Bad line #{} '{:.32}': {}".format(
            self.lineno,
            self.line.strip(),
            self.args[0],
        )
