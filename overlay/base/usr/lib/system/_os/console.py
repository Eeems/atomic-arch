import sys


def bytes_to_stdout(line: bytes):
    print(line.decode("utf-8"), end="")


def bytes_to_stderr(line: bytes):
    print(line.decode("utf-8"), file=sys.stderr, end="")
