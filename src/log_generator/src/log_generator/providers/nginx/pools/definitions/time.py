"""Time-related variable pools."""

from ..base import PoolMeta, PoolType, register_pool
from ..temporal import TemporalPool

# ─── $time_local ──────────────────────────────────────────────────
register_pool(
    TemporalPool(
        meta=PoolMeta(
            nginx_variable="$time_local",
            description="Local time in Common Log Format",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.TEMPORAL,
        ),
        fmt="%d/%b/%Y:%H:%M:%S %z",
    )
)

# ─── $time_iso8601 ────────────────────────────────────────────────
register_pool(
    TemporalPool(
        meta=PoolMeta(
            nginx_variable="$time_iso8601",
            description="Local time in ISO 8601 format",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.TEMPORAL,
        ),
        fmt="%Y-%m-%dT%H:%M:%S%z",
    )
)

# ─── $msec ────────────────────────────────────────────────────────
register_pool(
    TemporalPool(
        meta=PoolMeta(
            nginx_variable="$msec",
            description="Time in seconds with millisecond resolution",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.TEMPORAL,
        ),
        fmt="epoch_ms",
        use_epoch=True,
    )
)
