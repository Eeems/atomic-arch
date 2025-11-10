import sys


def bytes_to_stdout(line: bytes):
    _ = sys.stdout.buffer.write(line)
    _ = sys.stdout.flush()


def bytes_to_stderr(line: bytes):
    _ = sys.stderr.buffer.write(line)
    _ = sys.stderr.flush()
