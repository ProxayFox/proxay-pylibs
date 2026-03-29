"""Log entry generator — orchestrates all pools with shared context."""

from datetime import datetime, timezone
from typing import Any

from .base import all_pools


# Define generation order (dependency-aware)
GENERATION_ORDER = [
    # 1. Independent base values first
    "$scheme",
    "$request_method",
    "$server_protocol",
    "$server_port",
    "$server_name",
    "$hostname",
    "$nginx_version",
    "$pid",
    "$pipe",
    # 2. Network
    "$remote_addr",
    "$remote_port",
    "$server_addr",
    "$connection",
    "$connection_requests",
    # 3. Request components (uri before request_uri before request)
    "$uri",
    "$args",
    "$request_uri",  # composite: needs $uri + $args
    "$request",  # composite: needs $request_method + $request_uri + $server_protocol
    "$is_args",  # composite: needs $args
    "$request_length",
    "$host",
    "$remote_user",
    "$request_id",
    "$document_root",
    # 4. Headers
    "$http_user_agent",
    "$http_referer",
    "$http_host",
    "$http_accept_encoding",
    "$http_accept_language",
    "$http_x_forwarded_for",
    "$http_x_forwarded_proto",
    # 5. SSL (conditional on $scheme)
    "$ssl_protocol",
    "$ssl_cipher",
    "$ssl_curves",
    "$ssl_session_reused",
    "$ssl_session_id",
    "$ssl_early_data",
    "$ssl_server_name",
    # 6. Upstream
    "$upstream_addr",
    "$upstream_status",
    "$upstream_response_time",
    "$upstream_connect_time",
    "$upstream_header_time",
    "$upstream_cache_status",
    "$upstream_bytes_received",
    "$upstream_bytes_sent",
    "$upstream_response_length",
    # 7. Response
    "$status",
    "$body_bytes_sent",
    "$bytes_sent",
    "$request_time",
    "$gzip_ratio",
    "$content_type",
    "$sent_http_content_type",
    "$sent_http_content_length",
    "$sent_http_cache_control",
    # 8. Time (last — uses shared timestamp)
    "$time_local",
    "$time_iso8601",
    "$msec",
]


def generate_log_entry(
    variables: list[str] | None = None,
    timestamp: datetime | None = None,
) -> dict[str, str]:
    """Generate a complete log entry with all requested variables.

    Args:
        variables: List of variable names to generate. If None, generates all.
        timestamp: Override timestamp. If None, uses now().

    Returns:
        Dict mapping variable name -> generated value.
    """
    pools = all_pools()
    ts = timestamp or datetime.now(timezone.utc)
    context: dict[str, Any] = {"_timestamp": ts}

    requested = set(variables) if variables else set(pools.keys())

    # Generate in dependency order
    for var in GENERATION_ORDER:
        if var in requested and var in pools:
            value = pools[var].generate(context)
            context[var] = value

    # Generate any remaining that weren't in the order list
    for var in requested:
        if var not in context and var in pools:
            context[var] = pools[var].generate(context)

    # Filter out internal keys
    return {k: v for k, v in context.items() if k.startswith("$")}


def format_log_line(
    entry: dict[str, str],
    log_format: str,
) -> str:
    """Format a generated entry using an nginx log_format string.

    Args:
        entry: Dict from generate_log_entry()
        log_format: nginx log_format string like
            '$remote_addr - $remote_user [$time_local] "$request" $status'

    Returns:
        Formatted log line string.
    """
    line = log_format
    # Sort by length descending to avoid partial replacements
    for var in sorted(entry, key=lambda variable: len(variable), reverse=True):
        line = line.replace(var, entry[var])
    return line
