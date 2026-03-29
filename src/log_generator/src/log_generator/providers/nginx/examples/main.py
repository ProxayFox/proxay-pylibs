"""Example nginx log generation script."""

from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    from log_generator.providers.nginx.pools import generate_log_entry, format_log_line
else:
    from ..pools import generate_log_entry, format_log_line

# # Format as combined log
# COMBINED_FORMAT = (
#     "$remote_addr - $remote_user [$time_local] "
#     '"$request" $status $body_bytes_sent '
#     '"$http_referer" "$http_user_agent"'
# )

# i = 0
# while i < 10:
#     # Generate a complete entry
#     entry = generate_log_entry()
#     print(format_log_line(entry, COMBINED_FORMAT))
#     i += 1
# # 203.0.113.47 - - [29/Mar/2026:06:55:48 +0000] "GET /api/v1/users?page=1 HTTP/2.0" 200 4523 "https://www.google.com/" "Mozilla/5.0 ..."

# # Or a custom JSON-ish format
# JSON_FORMAT = (
#     "$remote_addr|$time_iso8601|$request_method|$request_uri|"
#     "$status|$body_bytes_sent|$request_time|"
#     "$upstream_response_time|$upstream_cache_status|"
#     "$ssl_protocol|$ssl_cipher"
# )

# i = 0
# while i < 10:
#     # Generate a complete entry
#     entry = generate_log_entry()
#     print(format_log_line(entry, JSON_FORMAT))
#     i += 1

PRODUCTION_FORMAT = (
    '$remote_addr - $remote_user [$time_local] "$request" '
    '$status $body_bytes_sent "$http_referer" '
    '"$http_user_agent" "$http_x_forwarded_for" '
    "$request_length $bytes_sent "
    "$ssl_protocol/$ssl_cipher "
    "$ssl_session_reused $ssl_session_id "
)

i = 0
while i < 10:
    # Generate a complete entry
    entry = generate_log_entry()
    print(format_log_line(entry, PRODUCTION_FORMAT))
    i += 1
