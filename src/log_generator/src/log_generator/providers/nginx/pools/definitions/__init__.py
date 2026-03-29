"""Load all nginx pool definitions so they self-register on import."""

from . import connection, core, error, headers, request, response, ssl, time, upstream

__all__ = [
    "connection",
    "core",
    "error",
    "headers",
    "request",
    "response",
    "ssl",
    "time",
    "upstream",
]
