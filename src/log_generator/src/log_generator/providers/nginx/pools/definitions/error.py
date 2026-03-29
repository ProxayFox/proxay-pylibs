"""Error log specific pools."""

from ..base import PoolMeta, PoolType, register_pool
from ..weighted import WeightedPool

# ─── Error severity levels ────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$error_level",
            description="Error log severity level",
            module="ngx_core_module",
            contexts=["error_log"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "debug": 0.00,  # Only if explicitly enabled
            "info": 0.05,
            "notice": 0.10,
            "warn": 0.30,
            "error": 0.40,
            "crit": 0.08,
            "alert": 0.05,
            "emerg": 0.02,
        },
    )
)

# ─── Error messages ───────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$error_message",
            description="Typical nginx error log messages",
            module="ngx_core_module",
            contexts=["error_log"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            'open() "/var/www/html/favicon.ico" failed (2: No such file or directory)': 0.15,
            'open() "/var/www/html/.env" failed (2: No such file or directory)': 0.05,
            "connect() failed (111: Connection refused) while connecting to upstream": 0.12,
            "upstream timed out (110: Connection timed out) while reading response header": 0.10,
            "upstream prematurely closed connection while reading response header": 0.08,
            "client intended to send too large body": 0.05,
            "SSL_do_handshake() failed": 0.04,
            "no live upstreams while connecting to upstream": 0.04,
            "recv() failed (104: Connection reset by peer)": 0.06,
            'directory index of "/var/www/html/" is forbidden': 0.04,
            "access forbidden by rule": 0.05,
            'rewrite or internal redirection cycle while processing "/"': 0.03,
            "client closed connection while waiting for request": 0.08,
            "worker_connections are not enough": 0.02,
            "could not build optimal types_hash": 0.01,
            "conflicting server name ignored": 0.02,
            "signal process started": 0.06,
        },
    )
)
