"""SSL module variable pools — conditional on $scheme == 'https'."""

import random

from ..base import PoolMeta, PoolType, register_pool
from ..composite import CompositePool
from ..weighted import WeightedPool
from ..conditional import ConditionalPool
from ..numeric import NumericPool, NumericDistribution


_HEX_DIGITS = "0123456789abcdef"


# ─── Helper: wrap in conditional ──────────────────────────────────
def _ssl_conditional(meta: PoolMeta, inner) -> ConditionalPool:
    return ConditionalPool(
        meta=meta,
        inner_pool=inner,
        condition_var="$scheme",
        condition_values={"https"},
        default="-",
    )


def _build_ssl_session_id(ctx: dict[str, str]) -> str:
    """Generate a synthetic hexadecimal TLS session id."""
    return "".join(random.choices(_HEX_DIGITS, k=32))


# ─── $ssl_protocol ────────────────────────────────────────────────
register_pool(
    _ssl_conditional(
        PoolMeta(
            nginx_variable="$ssl_protocol",
            description="SSL/TLS protocol version",
            module="ngx_http_ssl_module",
            contexts=["http", "server"],
            pool_type=PoolType.CONDITIONAL,
            conditional_on="$scheme",
        ),
        WeightedPool(
            meta=PoolMeta("$ssl_protocol", "", "", [], PoolType.WEIGHTED),
            choices={
                "TLSv1": 0.02,
                "TLSv1.1": 0.03,
                "TLSv1.2": 0.45,
                "TLSv1.3": 0.50,
            },
        ),
    )
)

# ─── $ssl_cipher ──────────────────────────────────────────────────
register_pool(
    _ssl_conditional(
        PoolMeta(
            nginx_variable="$ssl_cipher",
            description="SSL cipher used",
            module="ngx_http_ssl_module",
            contexts=["http", "server"],
            pool_type=PoolType.CONDITIONAL,
            conditional_on="$scheme",
        ),
        WeightedPool(
            meta=PoolMeta("$ssl_cipher", "", "", [], PoolType.WEIGHTED),
            choices={
                "TLS_AES_256_GCM_SHA384": 0.25,
                "TLS_AES_128_GCM_SHA256": 0.20,
                "TLS_CHACHA20_POLY1305_SHA256": 0.15,
                "ECDHE-RSA-AES256-GCM-SHA384": 0.15,
                "ECDHE-RSA-AES128-GCM-SHA256": 0.10,
                "ECDHE-ECDSA-AES256-GCM-SHA384": 0.08,
                "ECDHE-ECDSA-AES128-GCM-SHA256": 0.05,
                "DHE-RSA-AES256-GCM-SHA384": 0.02,
            },
        ),
    )
)

# ─── $ssl_ciphers ─────────────────────────────────────────────────
# (The full list offered by server — typically static, not logged)

# ─── $ssl_curves ──────────────────────────────────────────────────
register_pool(
    _ssl_conditional(
        PoolMeta(
            nginx_variable="$ssl_curves",
            description="Client-supported SSL curves",
            module="ngx_http_ssl_module",
            contexts=["http", "server"],
            pool_type=PoolType.CONDITIONAL,
            conditional_on="$scheme",
        ),
        WeightedPool(
            meta=PoolMeta("$ssl_curves", "", "", [], PoolType.WEIGHTED),
            choices={
                "X25519:prime256v1:secp384r1": 0.50,
                "prime256v1:secp384r1:secp521r1": 0.25,
                "X25519:prime256v1": 0.15,
                "X25519": 0.10,
            },
        ),
    )
)

# ─── $ssl_session_reused ──────────────────────────────────────────
register_pool(
    _ssl_conditional(
        PoolMeta(
            nginx_variable="$ssl_session_reused",
            description="Whether SSL session was reused ('r') or not ('.')",
            module="ngx_http_ssl_module",
            contexts=["http", "server"],
            pool_type=PoolType.CONDITIONAL,
            conditional_on="$scheme",
        ),
        WeightedPool(
            meta=PoolMeta("$ssl_session_reused", "", "", [], PoolType.WEIGHTED),
            choices={"r": 0.60, ".": 0.40},
        ),
    )
)

# ─── $ssl_session_id ──────────────────────────────────────────────
register_pool(
    _ssl_conditional(
        PoolMeta(
            nginx_variable="$ssl_session_id",
            description="Hexadecimal SSL session identifier",
            module="ngx_http_ssl_module",
            contexts=["http", "server"],
            pool_type=PoolType.CONDITIONAL,
            conditional_on="$scheme",
        ),
        CompositePool(
            meta=PoolMeta(
                "$ssl_session_id",
                "",
                "",
                [],
                PoolType.COMPOSITE,
            ),
            builder=_build_ssl_session_id,
        ),
    )
)

# ─── $ssl_early_data ──────────────────────────────────────────────
register_pool(
    _ssl_conditional(
        PoolMeta(
            nginx_variable="$ssl_early_data",
            description="'1' if TLS 1.3 early data was used",
            module="ngx_http_ssl_module",
            contexts=["http", "server"],
            pool_type=PoolType.CONDITIONAL,
            conditional_on="$scheme",
        ),
        WeightedPool(
            meta=PoolMeta("$ssl_early_data", "", "", [], PoolType.WEIGHTED),
            choices={"1": 0.10, "": 0.90},
        ),
    )
)

# ─── $ssl_server_name ─────────────────────────────────────────────
register_pool(
    _ssl_conditional(
        PoolMeta(
            nginx_variable="$ssl_server_name",
            description="SNI server name from TLS handshake",
            module="ngx_http_ssl_module",
            contexts=["http", "server"],
            pool_type=PoolType.CONDITIONAL,
            conditional_on="$scheme",
        ),
        WeightedPool(
            meta=PoolMeta("$ssl_server_name", "", "", [], PoolType.WEIGHTED),
            choices={
                "example.com": 0.40,
                "api.example.com": 0.30,
                "cdn.example.com": 0.15,
                "admin.example.com": 0.15,
            },
        ),
    )
)
