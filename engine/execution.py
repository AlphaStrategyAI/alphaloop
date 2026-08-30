from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Order:
    asset: str
    target_weight: float


class ExecutionPort(Protocol):
    def submit(self, orders: list[Order]) -> None:
        raise NotImplementedError


class Broker(ExecutionPort, Protocol):
    """Reserved live-execution seam for another product."""


class NotImplementedBroker:
    def submit(self, orders: list[Order]) -> None:
        raise NotImplementedError("order submission is outside alphaloop v1")
