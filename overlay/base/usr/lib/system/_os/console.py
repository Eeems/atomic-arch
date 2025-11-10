import sys


def bytes_to_stdout(line: bytes):
    _ = sys.stdout.buffer.write(line)
    _ = sys.stdout.flush()


def bytes_to_stderr(line: bytes):
    _ = sys.stderr.buffer.write(line)
    _ = sys.stderr.flush()


def bytes_to_iec(size_bytes: int) -> str:
    units = ["KiB", "MiB", "GiB", "TiB", "PiB"]
    size = float(size_bytes)
    res = str(size_bytes)
    while size >= 1024.0 and units:
        size /= 1024.0
        unit = units.pop(0)
        res = f"{size:.2f} {unit}"
    return res
