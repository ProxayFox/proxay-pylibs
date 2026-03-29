"""Response and sent_http_* variable pools."""

from ..base import PoolMeta, PoolType, register_pool
from ..weighted import WeightedPool
from ..numeric import NumericPool, NumericDistribution

# ─── $sent_http_content_length ────────────────────────────────────
register_pool(
    NumericPool(
        meta=PoolMeta(
            nginx_variable="$sent_http_content_length",
            description="Content-Length response header value",
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

# ─── $sent_http_cache_control ─────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$sent_http_cache_control",
            description="Cache-Control response header",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "public, max-age=3600": 0.20,
            "public, max-age=86400": 0.15,
            "public, max-age=31536000, immutable": 0.10,
            "no-cache": 0.15,
            "no-store": 0.10,
            "private, no-cache": 0.10,
            "max-age=0, must-revalidate": 0.10,
            "-": 0.10,
        },
    )
)

# ─── $sent_http_x_powered_by ──────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$sent_http_x_powered_by",
            description="X-Powered-By response header",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "-": 0.50,
            "Express": 0.15,
            "PHP/8.2": 0.10,
            "ASP.NET": 0.05,
            "Django": 0.05,
            "Flask": 0.05,
            "Next.js": 0.05,
            "Rails": 0.05,
        },
    )
)

# ─── $gzip_ratio ──────────────────────────────────────────────────
register_pool(
    NumericPool(
        meta=PoolMeta(
            nginx_variable="$gzip_ratio",
            description="Compression ratio achieved",
            module="ngx_http_gzip_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.NUMERIC,
        ),
        distribution=NumericDistribution(
            kind="normal",
            mu=3.5,
            sigma=1.5,
            minimum=1.0,
            maximum=15.0,
            precision=2,
        ),
    )
)
