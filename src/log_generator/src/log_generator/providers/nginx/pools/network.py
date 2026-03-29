"""Network pool for IP addresses, ports, and socket-related variables."""

import random
import ipaddress
from typing import Any
from .base import BasePool, PoolMeta


class IPv4Pool(BasePool):
    """Generates random IPs from weighted CIDR blocks."""

    def __init__(self, meta: PoolMeta, cidrs: dict[str, float]):
        super().__init__(meta)
        self.cidrs = cidrs
        self._networks = list(cidrs.keys())
        self._weights = list(cidrs.values())

    def generate(self, context: dict[str, Any] | None = None) -> str:
        cidr = random.choices(self._networks, weights=self._weights, k=1)[0]
        network = ipaddress.IPv4Network(cidr)
        # Random host within network
        offset = random.randint(0, network.num_addresses - 1)
        return str(network.network_address + offset)

    def get_config(self) -> dict[str, Any]:
        return {"type": "ipv4", "cidrs": self.cidrs}


class PortPool(BasePool):
    """Generates realistic port numbers."""

    def __init__(self, meta: PoolMeta, low: int = 1024, high: int = 65535):
        super().__init__(meta)
        self.low = low
        self.high = high

    def generate(self, context: dict[str, Any] | None = None) -> str:
        return str(random.randint(self.low, self.high))

    def get_config(self) -> dict[str, Any]:
        return {"type": "port", "range": [self.low, self.high]}
