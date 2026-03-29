"""Core HTTP module variable pools."""

from ..base import PoolMeta, PoolType, register_pool
from ..weighted import WeightedPool
from ..numeric import NumericPool, NumericDistribution

# ─── $request_method ───────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$request_method",
            description="HTTP request method",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "GET": 0.70,
            "POST": 0.15,
            "HEAD": 0.05,
            "PUT": 0.05,
            "DELETE": 0.02,
            "PATCH": 0.005,
            "OPTIONS": 0.01,
            "CONNECT": 0.01,
            "TRACE": 0.005,
        },
    )
)

# ─── $status ───────────────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$status",
            description="HTTP response status code",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            200: 0.50,
            201: 0.05,
            204: 0.03,
            206: 0.02,
            301: 0.04,
            302: 0.04,
            304: 0.06,
            400: 0.04,
            401: 0.03,
            403: 0.03,
            404: 0.08,
            405: 0.01,
            408: 0.01,
            429: 0.01,
            500: 0.02,
            502: 0.01,
            503: 0.01,
            504: 0.01,
        },
    )
)

# ─── $scheme ───────────────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$scheme",
            description="Request scheme (http or https)",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={"http": 0.15, "https": 0.85},
    )
)

# ─── $server_protocol ─────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$server_protocol",
            description="HTTP protocol version",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "HTTP/1.0": 0.05,
            "HTTP/1.1": 0.25,
            "HTTP/2.0": 0.50,
            "HTTP/3.0": 0.20,
        },
    )
)

# ─── $server_port ─────────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$server_port",
            description="Port of the server accepting the request",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={"80": 0.15, "443": 0.80, "8080": 0.03, "8443": 0.02},
    )
)

# ─── $pipe ─────────────────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$pipe",
            description="'p' if pipelined, '.' otherwise",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={".": 0.95, "p": 0.05},
    )
)

# ─── $https ────────────────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$https",
            description="'on' if HTTPS, empty string otherwise",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={"on": 0.85, "": 0.15},
    )
)

# ─── $request_length ──────────────────────────────────────────────
register_pool(
    NumericPool(
        meta=PoolMeta(
            nginx_variable="$request_length",
            description="Request length including headers and body",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.NUMERIC,
        ),
        distribution=NumericDistribution(
            kind="log_normal",
            mu=5.5,
            sigma=1.0,
            minimum=100,
            maximum=1_000_000,
            as_int=True,
        ),
    )
)

# ─── $body_bytes_sent ─────────────────────────────────────────────
register_pool(
    NumericPool(
        meta=PoolMeta(
            nginx_variable="$body_bytes_sent",
            description="Bytes sent to client, excluding headers",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.NUMERIC,
        ),
        distribution=NumericDistribution(
            kind="log_normal",
            mu=7.5,
            sigma=2.0,
            minimum=0,
            maximum=50_000_000,
            as_int=True,
        ),
    )
)

# ─── $bytes_sent ──────────────────────────────────────────────────
register_pool(
    NumericPool(
        meta=PoolMeta(
            nginx_variable="$bytes_sent",
            description="Total bytes sent to client",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.NUMERIC,
        ),
        distribution=NumericDistribution(
            kind="log_normal",
            mu=7.8,
            sigma=2.0,
            minimum=150,
            maximum=50_000_000,
            as_int=True,
        ),
    )
)

# ─── $request_time ────────────────────────────────────────────────
register_pool(
    NumericPool(
        meta=PoolMeta(
            nginx_variable="$request_time",
            description="Request processing time in seconds (ms precision)",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.NUMERIC,
        ),
        distribution=NumericDistribution(
            kind="log_normal",
            mu=-3.5,
            sigma=1.5,
            minimum=0.001,
            maximum=30.0,
            precision=3,
        ),
    )
)

# ─── $nginx_version ───────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$nginx_version",
            description="Nginx version string",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "1.24.0": 0.20,
            "1.25.1": 0.25,
            "1.25.3": 0.30,
            "1.26.0": 0.15,
            "1.27.0": 0.10,
        },
    )
)

# ─── $hostname ─────────────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$hostname",
            description="System hostname",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "web-prod-01": 0.25,
            "web-prod-02": 0.25,
            "web-prod-03": 0.25,
            "web-prod-04": 0.25,
        },
    )
)

# ─── $pid ──────────────────────────────────────────────────────────
register_pool(
    NumericPool(
        meta=PoolMeta(
            nginx_variable="$pid",
            description="PID of the worker process",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.NUMERIC,
        ),
        distribution=NumericDistribution(
            kind="uniform",
            low=1000,
            high=65535,
            as_int=True,
        ),
    )
)

# ─── $request_id ──────────────────────────────────────────────────
# (Handled separately as UUID — see composite definitions)
