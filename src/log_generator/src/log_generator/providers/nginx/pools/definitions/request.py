"""Request URI and path variable pools."""

from ..base import PoolMeta, PoolType, register_pool
from ..weighted import WeightedPool
from ..composite import CompositePool
from ..numeric import NumericPool, NumericDistribution
import uuid
from typing import Any

# ─── $uri / $document_uri ─────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$uri",
            description="Current URI in request (normalized, no args)",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "/": 0.15,
            "/index.html": 0.08,
            "/api/v1/users": 0.08,
            "/api/v1/products": 0.06,
            "/api/v1/orders": 0.04,
            "/api/v2/health": 0.05,
            "/api/v1/auth/login": 0.04,
            "/api/v1/auth/logout": 0.02,
            "/products": 0.04,
            "/products/detail": 0.03,
            "/blog": 0.03,
            "/blog/post-1": 0.02,
            "/about": 0.02,
            "/contact": 0.02,
            "/static/css/main.css": 0.04,
            "/static/js/app.js": 0.04,
            "/static/img/logo.png": 0.03,
            "/favicon.ico": 0.05,
            "/robots.txt": 0.03,
            "/sitemap.xml": 0.02,
            "/.env": 0.02,
            "/wp-admin": 0.02,
            "/wp-login.php": 0.02,
            "/phpmyadmin": 0.01,
            "/admin": 0.02,
            "/dashboard": 0.03,
        },
    )
)

# ─── $args / $query_string ────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$args",
            description="Query string arguments",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "": 0.50,
            "page=1": 0.08,
            "page=2": 0.04,
            "page=1&limit=20": 0.05,
            "q=search+term": 0.05,
            "id=123": 0.04,
            "id=456&format=json": 0.03,
            "sort=date&order=desc": 0.04,
            "utm_source=google&utm_medium=cpc": 0.05,
            "utm_source=twitter": 0.03,
            "callback=jsonp_callback": 0.02,
            "lang=en": 0.03,
            "debug=true": 0.02,
            "token=abc123def456": 0.02,
        },
    )
)


# ─── $request_uri (uri + args) ────────────────────────────────────
def _build_request_uri(ctx: dict[str, Any]) -> str:
    uri = ctx.get("$uri", "/")
    args = ctx.get("$args", "")
    return f"{uri}?{args}" if args else uri


register_pool(
    CompositePool(
        meta=PoolMeta(
            nginx_variable="$request_uri",
            description="Full original request URI with arguments",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.COMPOSITE,
        ),
        builder=_build_request_uri,
    )
)


# ─── $request (full request line) ─────────────────────────────────
def _build_request_line(ctx: dict[str, Any]) -> str:
    method = ctx.get("$request_method", "GET")
    uri = ctx.get("$request_uri", "/")
    proto = ctx.get("$server_protocol", "HTTP/1.1")
    return f"{method} {uri} {proto}"


register_pool(
    CompositePool(
        meta=PoolMeta(
            nginx_variable="$request",
            description="Full original request line",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.COMPOSITE,
        ),
        builder=_build_request_line,
    )
)

# ─── $host ────────────────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$host",
            description="Host name from request line, Host header, or server_name",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "example.com": 0.40,
            "www.example.com": 0.20,
            "api.example.com": 0.20,
            "cdn.example.com": 0.10,
            "admin.example.com": 0.10,
        },
    )
)

# ─── $server_name ─────────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$server_name",
            description="Server name of the virtual host",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "example.com": 0.40,
            "api.example.com": 0.30,
            "cdn.example.com": 0.15,
            "admin.example.com": 0.15,
        },
    )
)

# ─── $remote_user ─────────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$remote_user",
            description="Authenticated username from Basic auth",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "-": 0.80,
            "admin": 0.05,
            "deploy": 0.03,
            "api_user": 0.05,
            "monitor": 0.03,
            "john": 0.02,
            "service_account": 0.02,
        },
    )
)


# ─── $request_id ──────────────────────────────────────────────────
def _build_request_id(ctx: dict[str, Any]) -> str:
    return uuid.uuid4().hex


register_pool(
    CompositePool(
        meta=PoolMeta(
            nginx_variable="$request_id",
            description="Unique request identifier (16 random hex bytes)",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.COMPOSITE,
        ),
        builder=_build_request_id,
    )
)

# ─── $document_root ───────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$document_root",
            description="Root directive value for current request",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "/var/www/html": 0.40,
            "/usr/share/nginx/html": 0.30,
            "/srv/www": 0.15,
            "/opt/app/public": 0.15,
        },
    )
)


# ─── $is_args ─────────────────────────────────────────────────────
def _build_is_args(ctx: dict[str, Any]) -> str:
    return "?" if ctx.get("$args", "") else ""


register_pool(
    CompositePool(
        meta=PoolMeta(
            nginx_variable="$is_args",
            description="'?' if request has args, empty otherwise",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.COMPOSITE,
        ),
        builder=_build_is_args,
    )
)
