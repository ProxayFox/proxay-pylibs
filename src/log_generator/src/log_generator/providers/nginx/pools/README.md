# Log Generator - Nginx Pools README

```text
pools/
├── __init__.py
├── base.py              # Abstract base + pool registry
├── weighted.py          # WeightedPool for enums
├── numeric.py           # NumericPool for distributions
├── temporal.py          # TemporalPool for time variables
├── composite.py         # CompositePool for derived variables
├── network.py           # NetworkPool for IPs/ports
├── counter.py           # CounterPool for monotonic values
├── conditional.py       # ConditionalPool (e.g., SSL only if HTTPS)
├── definitions/
│   ├── __init__.py
│   ├── core.py          # $request_method, $status, $scheme, etc.
│   ├── request.py       # $request_uri, $args, $query_string, etc.
│   ├── response.py      # $body_bytes_sent, $bytes_sent, etc.
│   ├── connection.py    # $remote_addr, $remote_port, $connection, etc.
│   ├── upstream.py      # $upstream_addr, $upstream_status, etc.
│   ├── ssl.py           # $ssl_protocol, $ssl_cipher, etc.
│   ├── headers.py       # $http_user_agent, $http_referer, etc.
│   ├── time.py          # $time_local, $time_iso8601, $msec, etc.
│   └── error.py         # Error log severity, messages, etc.
```
