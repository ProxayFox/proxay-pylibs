"""Example nginx log generation script."""

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    from log_generator.providers.nginx.pools import (
        all_pools,
        format_log_line,
        generate_log_entry,
    )
else:
    from ..pools import all_pools, format_log_line, generate_log_entry

DEFAULT_FORMAT: str = (
    "$remote_addr - $remote_user [$time_local] "
    '"$request" $status $body_bytes_sent '
    '"$http_referer" "$http_user_agent" "$gzip_ratio"'
)

JSON_FORMAT: str = (
    "$remote_addr|$time_iso8601|$request_method|$request_uri|"
    "$status|$body_bytes_sent|$request_time|"
    "$upstream_response_time|$upstream_cache_status|"
    "$ssl_protocol|$ssl_cipher"
)

EXAMPLE_FORMAT: str = (
    '$remote_addr - $remote_user [$time_local] "$request" '
    '$status $body_bytes_sent "$http_referer" '
    '"$http_user_agent" "$http_x_forwarded_for" '
    "$request_length $bytes_sent "
    "$ssl_protocol/$ssl_cipher "
    "$ssl_session_reused $ssl_session_id "
)

PRODUCTION_FORMAT: str = EXAMPLE_FORMAT

SHIPPED_FORMATS: tuple[tuple[str, str], ...] = (
    ("Default Format Example", DEFAULT_FORMAT),
    ("JSON Format Example", JSON_FORMAT),
    ("Example Format Example", EXAMPLE_FORMAT),
)

PRINT: list[tuple[str, str]] = [
    *SHIPPED_FORMATS,
    ("Example Format with All Variables", " ".join(all_pools().keys())),
    ("Example Format with All Variables (JSON)", "|".join(all_pools().keys())),
]


def main() -> None:
    """Print a few synthetic example-style log lines."""
    for fmt_name, fmt in PRINT:
        print("\n" + "=" * 80)
        print(f"Format: {fmt_name}")
        print("=" * 80)
        i = 0
        while i < 5:
            entry = generate_log_entry()
            rendered = format_log_line(entry, fmt)
            print(rendered)
            i += 1


if __name__ == "__main__":
    main()
