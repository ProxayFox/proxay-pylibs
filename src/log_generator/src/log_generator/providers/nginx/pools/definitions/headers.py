"""HTTP header variable pools: $http_user_agent, $http_referer, etc."""

from ..base import PoolMeta, PoolType, register_pool
from ..weighted import WeightedPool

# ─── $http_user_agent ─────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$http_user_agent",
            description="Client User-Agent header",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            # Chrome - Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36": 0.18,
            # Chrome - Mac
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36": 0.12,
            # Chrome - Linux
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36": 0.05,
            # Safari - Mac
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.10 Safari/605.1.15": 0.15,
            # Safari - iPhone
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 "
            "Mobile/15E148 Safari/604.1": 0.10,
            # Edge
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0": 0.06,
            # Firefox
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) "
            "Gecko/20100101 Firefox/136.0": 0.04,
            "Mozilla/5.0 (X11; Linux x86_64; rv:136.0) "
            "Gecko/20100101 Firefox/136.0": 0.02,
            # Chrome - Android
            "Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/134.0.0.0 Mobile Safari/537.36": 0.08,
            # Bots
            "Mozilla/5.0 (compatible; Googlebot/2.1; "
            "+http://www.google.com/bot.html)": 0.05,
            "Mozilla/5.0 (compatible; bingbot/2.0; "
            "+http://www.bing.com/bingbot.htm)": 0.03,
            "Mozilla/5.0 (compatible; AhrefsBot/7.0; "
            "+http://ahrefs.com/robot/)": 0.02,
            # Programmatic
            "curl/8.5.0": 0.03,
            "python-requests/2.31.0": 0.03,
            "Go-http-client/2.0": 0.02,
            "-": 0.02,
        },
    )
)

# ─── $http_referer ────────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$http_referer",
            description="Referer header value",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "-": 0.35,
            "https://www.google.com/": 0.15,
            "https://www.bing.com/": 0.05,
            "https://example.com/": 0.15,
            "https://example.com/products": 0.10,
            "https://example.com/blog": 0.05,
            "https://t.co/abc123": 0.03,
            "https://www.facebook.com/": 0.03,
            "https://www.reddit.com/": 0.03,
            "android-app://com.google.android.gm/": 0.02,
            "https://duckduckgo.com/": 0.02,
            "https://example.com/dashboard": 0.02,
        },
    )
)

# ─── $http_accept_encoding ────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$http_accept_encoding",
            description="Accept-Encoding header",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "gzip, deflate, br": 0.50,
            "gzip, deflate, br, zstd": 0.20,
            "gzip, deflate": 0.15,
            "gzip": 0.08,
            "identity": 0.02,
            "*": 0.03,
            "-": 0.02,
        },
    )
)

# ─── $http_accept_language ────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$http_accept_language",
            description="Accept-Language header",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "en-US,en;q=0.9": 0.40,
            "en-GB,en;q=0.9": 0.10,
            "de-DE,de;q=0.9,en;q=0.8": 0.08,
            "fr-FR,fr;q=0.9,en;q=0.8": 0.07,
            "es-ES,es;q=0.9,en;q=0.8": 0.06,
            "ja-JP,ja;q=0.9,en;q=0.8": 0.05,
            "zh-CN,zh;q=0.9,en;q=0.8": 0.08,
            "pt-BR,pt;q=0.9,en;q=0.8": 0.04,
            "ko-KR,ko;q=0.9,en;q=0.8": 0.03,
            "*": 0.05,
            "-": 0.04,
        },
    )
)

# ─── $http_host ───────────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$http_host",
            description="Host header value",
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

# ─── $http_x_forwarded_for ────────────────────────────────────────
# (Typically generated dynamically from $remote_addr — see composite)

# ─── $http_x_forwarded_proto ──────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$http_x_forwarded_proto",
            description="X-Forwarded-Proto header",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={"https": 0.85, "http": 0.15},
    )
)

# ─── $http_x_request_id ──────────────────────────────────────────
# (UUID — see composite definitions)

# ─── $content_type ────────────────────────────────────────────────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$content_type",
            description="Content-Type of the response",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "text/html; charset=utf-8": 0.25,
            "application/json": 0.25,
            "text/css": 0.08,
            "application/javascript": 0.10,
            "image/png": 0.06,
            "image/jpeg": 0.06,
            "image/webp": 0.04,
            "image/svg+xml": 0.02,
            "application/pdf": 0.02,
            "font/woff2": 0.03,
            "application/octet-stream": 0.02,
            "text/plain": 0.03,
            "application/xml": 0.02,
            "-": 0.02,
        },
    )
)

# ─── $sent_http_content_type (same pool, different variable) ──────
register_pool(
    WeightedPool(
        meta=PoolMeta(
            nginx_variable="$sent_http_content_type",
            description="Content-Type header in response",
            module="ngx_http_core_module",
            contexts=["http", "server", "location"],
            pool_type=PoolType.WEIGHTED,
        ),
        choices={
            "text/html; charset=utf-8": 0.25,
            "application/json": 0.25,
            "text/css": 0.08,
            "application/javascript": 0.10,
            "image/png": 0.06,
            "image/jpeg": 0.06,
            "image/webp": 0.04,
            "image/svg+xml": 0.02,
            "application/pdf": 0.02,
            "font/woff2": 0.03,
            "application/octet-stream": 0.02,
            "text/plain": 0.03,
            "application/xml": 0.02,
            "-": 0.02,
        },
    )
)
