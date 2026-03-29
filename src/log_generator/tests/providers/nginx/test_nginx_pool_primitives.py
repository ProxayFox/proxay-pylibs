"""Direct coverage for NGINX pool primitives and lazy exports."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from log_generator.providers.nginx import NGINX_PROVIDER
from log_generator.providers.nginx.pools import (
    CompositePool,
    ConditionalPool,
    CounterPool,
    IPv4Pool,
    NumericDistribution,
    NumericPool,
    PortPool,
    TemporalPool,
    WeightedPool,
    __dir__ as pools_dir,
    __getattr__ as pools_getattr,
    all_pools,
    get_pool,
)
from log_generator.providers.nginx.pools.base import PoolMeta, PoolType


def _meta(name: str, pool_type: PoolType) -> PoolMeta:
    return PoolMeta(
        nginx_variable=name,
        description="test pool",
        module="test",
        contexts=["http"],
        pool_type=pool_type,
    )


@pytest.mark.unit
def test_nginx_provider_exposes_preset_details() -> None:
    details = NGINX_PROVIDER.preset_details()

    assert details
    assert any(name == "production" for name, _, _ in details)
    assert NGINX_PROVIDER.shipped_formats


@pytest.mark.unit
def test_pools_dunder_getattr_and_dir_cover_valid_and_invalid_names() -> None:
    weighted_cls = pools_getattr("WeightedPool")

    assert weighted_cls is WeightedPool
    assert "WeightedPool" in pools_dir()

    with pytest.raises(AttributeError, match="no attribute"):
        pools_getattr("NotARealPool")


@pytest.mark.unit
def test_pool_registry_access_and_repr_are_available() -> None:
    pool = get_pool("$remote_addr")

    assert "$remote_addr" in all_pools()
    assert "var=$remote_addr" in repr(pool)


@pytest.mark.unit
def test_composite_pool_get_config_reports_builder_name() -> None:
    pool = CompositePool(
        _meta("$composite", PoolType.COMPOSITE), lambda ctx: ctx.get("v", "-")
    )

    assert pool.generate({"v": "ok"}) == "ok"
    assert pool.get_config()["type"] == "composite"


@pytest.mark.unit
def test_conditional_pool_get_config_includes_inner_pool() -> None:
    inner = WeightedPool(_meta("$weighted", PoolType.WEIGHTED), {"yes": 1.0})
    pool = ConditionalPool(
        _meta("$conditional", PoolType.CONDITIONAL),
        inner,
        condition_var="$scheme",
        condition_values={"https"},
        default="-",
    )

    assert pool.generate({"$scheme": "http"}) == "-"
    config = pool.get_config()
    assert config["type"] == "conditional"
    assert config["inner"]["type"] == "weighted"


@pytest.mark.unit
def test_counter_pool_get_config_reflects_state() -> None:
    pool = CounterPool(_meta("$counter", PoolType.COUNTER), start=10, step=5)

    assert pool.generate() == "10"
    assert pool.get_config() == {"type": "counter", "current": 15, "step": 5}


@pytest.mark.unit
def test_network_pools_expose_config() -> None:
    ip_pool = IPv4Pool(_meta("$ip", PoolType.NETWORK), {"203.0.113.0/24": 1.0})
    port_pool = PortPool(_meta("$port", PoolType.NETWORK), low=8080, high=8080)

    assert ip_pool.get_config()["type"] == "ipv4"
    assert port_pool.generate() == "8080"
    assert port_pool.get_config() == {"type": "port", "range": [8080, 8080]}


@pytest.mark.unit
def test_numeric_pool_covers_int_and_unknown_distribution_paths() -> None:
    int_pool = NumericPool(
        _meta("$int", PoolType.NUMERIC),
        NumericDistribution(kind="uniform", low=5.0, high=5.0, as_int=True),
    )
    assert int_pool.generate() == "5"
    assert int_pool.get_config()["type"] == "numeric"

    bad_pool = NumericPool(
        _meta("$bad", PoolType.NUMERIC),
        NumericDistribution(kind="mystery"),  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="Unknown distribution"):
        bad_pool.generate()


@pytest.mark.unit
def test_temporal_pool_covers_epoch_ms_and_config() -> None:
    pool = TemporalPool(
        _meta("$msec", PoolType.TEMPORAL), fmt="epoch_ms", use_epoch=True
    )
    rendered = pool.generate(
        {"_timestamp": datetime(2026, 3, 29, 7, 31, 26, tzinfo=timezone.utc)}
    )

    assert rendered.endswith(".000")
    assert pool.get_config() == {
        "type": "temporal",
        "fmt": "epoch_ms",
        "use_epoch": True,
    }


@pytest.mark.unit
def test_temporal_pool_covers_epoch_seconds_path() -> None:
    pool = TemporalPool(_meta("$sec", PoolType.TEMPORAL), fmt="epoch", use_epoch=True)

    rendered = pool.generate(
        {"_timestamp": datetime(2026, 3, 29, 7, 31, 26, tzinfo=timezone.utc)}
    )

    assert rendered.isdigit()


@pytest.mark.unit
def test_weighted_pool_get_config_reports_choices() -> None:
    pool = WeightedPool(_meta("$weighted", PoolType.WEIGHTED), {"a": 1.0})

    assert pool.generate() == "a"
    assert pool.get_config() == {"type": "weighted", "choices": {"a": 1.0}}
