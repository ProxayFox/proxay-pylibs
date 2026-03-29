"""Upstream module variable pools."""

from ..base import PoolMeta, PoolType, register_pool
from ..weighted import WeightedPool
from ..numeric import NumericPool, NumericDistribution
from ..network import IPv4Pool
from ..composite import CompositePool

# ─── $upstream_addr ───────────────────────────────────────────────
register_pool(
    IPv4Pool(
        meta=PoolMeta(
            nginx_variable="$upstream_addr",
            description="Upstream server address and port",
            module="ngx_http_upstream_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.NETWORK,
        ),
        cidrs={"127.0.0.0/8": 0.4, "10.0.10.0/24": 0.6},
    )
)

# ─── $upstream_status ─────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$upstream_status",
            description="Status code from upstream server",
            module="ngx_http_upstream_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            200: 0.60,
            201: 0.05,
            204: 0.03,
            301: 0.02,
            302: 0.02,
            304: 0.05,
            400: 0.04,
            401: 0.02,
            403: 0.02,
            404: 0.06,
            500: 0.04,
            502: 0.02,
            503: 0.02,
            504: 0.01,
        },
    )
)

# ─── $upstream_response_time ──────────────────────────────────────
register_pool(
    NumericPool(
        meta=PoolMeta(
            nginx_variable="$upstream_response_time",
            description="Time spent receiving response from upstream (seconds)",
            module="ngx_http_upstream_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.NUMERIC,
        ),
        distribution=NumericDistribution(
            kind="log_normal",
            mu=-3.0,
            sigma=1.5,
            minimum=0.001,
            maximum=30.0,
            precision=3,
        ),
    )
)

# ─── $upstream_connect_time ───────────────────────────────────────
register_pool(
    NumericPool(
        meta=PoolMeta(
            nginx_variable="$upstream_connect_time",
            description="Time to establish connection with upstream (seconds)",
            module="ngx_http_upstream_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.NUMERIC,
        ),
        distribution=NumericDistribution(
            kind="log_normal",
            mu=-6.0,
            sigma=1.0,
            minimum=0.000,
            maximum=5.0,
            precision=3,
        ),
    )
)

# ─── $upstream_header_time ────────────────────────────────────────
register_pool(
    NumericPool(
        meta=PoolMeta(
            nginx_variable="$upstream_header_time",
            description="Time to receive response header from upstream (seconds)",
            module="ngx_http_upstream_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.NUMERIC,
        ),
        distribution=NumericDistribution(
            kind="log_normal",
            mu=-4.0,
            sigma=1.2,
            minimum=0.001,
            maximum=30.0,
            precision=3,
        ),
    )
)

# ─── $upstream_bytes_received ─────────────────────────────────────
register_pool(
    NumericPool(
        meta=PoolMeta(
            nginx_variable="$upstream_bytes_received",
            description="Bytes received from upstream server",
            module="ngx_http_upstream_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.NUMERIC,
        ),
        distribution=NumericDistribution(
            kind="log_normal",
            mu=7.0,
            sigma=2.0,
            minimum=0,
            maximum=50_000_000,
            as_int=True,
        ),
    )
)

# ─── $upstream_bytes_sent ─────────────────────────────────────────
register_pool(
    NumericPool(
        meta=PoolMeta(
            nginx_variable="$upstream_bytes_sent",
            description="Bytes sent to upstream server",
            module="ngx_http_upstream_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.NUMERIC,
        ),
        distribution=NumericDistribution(
            kind="log_normal",
            mu=5.5,
            sigma=1.5,
            minimum=0,
            maximum=10_000_000,
            as_int=True,
        ),
    )
)

# ─── $upstream_cache_status ───────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$upstream_cache_status",
            description="Cache status: HIT, MISS, BYPASS, etc.",
            module="ngx_http_upstream_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "HIT": 0.45,
            "MISS": 0.30,
            "BYPASS": 0.10,
            "EXPIRED": 0.05,
            "STALE": 0.03,
            "UPDATING": 0.02,
            "REVALIDATED": 0.03,
            "-": 0.02,
        },
    )
)

# ─── $upstream_response_length ────────────────────────────────────
register_pool(
    NumericPool(
        meta=PoolMeta(
            nginx_variable="$upstream_response_length",
            description="Length of response from upstream",
            module="ngx_http_upstream_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.NUMERIC,
        ),
        distribution=NumericDistribution(
            kind="log_normal",
            mu=7.0,
            sigma=2.0,
            minimum=0,
            maximum=50_000_000,
            as_int=True,
        ),
    )
)
