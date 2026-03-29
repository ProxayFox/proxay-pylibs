"""Connection and network variable pools."""

from ..base import PoolMeta, PoolType, register_pool
from ..network import IPv4Pool, PortPool
from ..counter import CounterPool
from ..numeric import NumericPool, NumericDistribution

# ─── $remote_addr ─────────────────────────────────────────────────
register_pool(
    IPv4Pool(
        meta=PoolMeta(
            nginx_variable="$remote_addr",
            description="Client IP address",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.NETWORK,
        ),
        cidrs={
            "10.0.0.0/8": 0.10,  # Internal
            "172.16.0.0/12": 0.05,  # Internal
            "192.168.0.0/16": 0.05,  # Internal
            "203.0.113.0/24": 0.15,  # Example range (documentation)
            "198.51.100.0/24": 0.15,  # Example range
            "100.0.0.0/8": 0.10,  # Various public
            "52.0.0.0/8": 0.10,  # AWS-like
            "104.0.0.0/8": 0.10,  # Cloudflare-like
            "151.0.0.0/8": 0.10,  # European ISPs
            "73.0.0.0/8": 0.10,  # US residential
        },
    )
)

# ─── $remote_port ─────────────────────────────────────────────────
register_pool(
    PortPool(
        meta=PoolMeta(
            nginx_variable="$remote_port",
            description="Client port",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.NETWORK,
        ),
        low=1024,
        high=65535,
    )
)

# ─── $server_addr ─────────────────────────────────────────────────
register_pool(
    IPv4Pool(
        meta=PoolMeta(
            nginx_variable="$server_addr",
            description="Server address that accepted the request",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.NETWORK,
        ),
        cidrs={"10.0.1.0/28": 0.5, "10.0.2.0/28": 0.5},
    )
)

# ─── $connection ──────────────────────────────────────────────────
register_pool(
    CounterPool(
        meta=PoolMeta(
            nginx_variable="$connection",
            description="Connection serial number",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.COUNTER,
        ),
        start=100000,
        step=1,
    )
)

# ─── $connection_requests ─────────────────────────────────────────
register_pool(
    NumericPool(
        meta=PoolMeta(
            nginx_variable="$connection_requests",
            description="Number of requests on current connection",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.NUMERIC,
        ),
        distribution=NumericDistribution(
            kind="exponential",
            lambd=0.3,
            minimum=1,
            maximum=100,
            as_int=True,
        ),
    )
)
