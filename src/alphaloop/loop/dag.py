"""
Hybrid DAG — static 6-node skeleton for the v0.7 research loop.

The design (docs/design/v07-hybrid-loop.md § 2.1) commits us to a
*static* skeleton (N1 → N2 → N3 → N4 → N5 → N6) with LLM-planner
freedom inside N1, N2, N5 only. This module defines:

- ``Node``            — a single stage with a name, dependencies, and a run-fn.
- ``HybridDAG``       — holds the 6 nodes, validates the DAG, and exposes a
                        topological execution order.

The actual stage implementations live in ``planner.py`` (N1/N2/N5),
``executor.py`` (N3), and ``aggregator.py`` (N4 + top-5 selection +
report.md). The DAG itself only knows *what runs after what*.

Design contract (design doc § 2.1, § 3.2):
- Static skeleton, deterministic order.
- Per-node body can be async or sync.
- Each node's body is injected at construction (DI-friendly for tests).
- The DAG validates acyclicity and missing-dependency errors at
  ``build()`` time so failures surface early.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable, Sequence


# A node body is any zero-arg callable that returns either ``None`` or
# an awaitable. We type as ``Callable[[], Any]`` to keep both sync and
# async bodies ergonomic; the runner awaits the result.
NodeBody = Callable[[], Any]


@dataclass
class Node:
    """A single stage in the hybrid DAG.

    Attributes:
        name:        Stable identifier ("n1_load_data", "n3_execute", ...).
        depends_on:  Names of nodes that must complete first. May be empty.
        run:         Callable with no required arguments. May be sync or
                     async. The runner awaits the result if awaitable.
        description: Human-readable label used in logs / report.md.
    """

    name: str
    depends_on: Sequence[str] = field(default_factory=tuple)
    run: NodeBody | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Node.name must be non-empty")
        # Coerce to tuple for hashability/serialization friendliness.
        self.depends_on = tuple(self.depends_on)


class CyclicDependencyError(ValueError):
    """Raised when the DAG contains a cycle (no valid topo order)."""


class MissingDependencyError(ValueError):
    """Raised when a node depends on a name not declared in the DAG."""


class HybridDAG:
    """Static 6-node DAG container for the v0.7 research loop.

    The canonical v0.7 nodes are registered by ``default_nodes()``.
    Tests can construct a DAG with arbitrary nodes via ``__init__`` +
    ``add()`` for unit-testing individual stages.
    """

    def __init__(self, nodes: Iterable[Node] = ()) -> None:
        self._nodes: dict[str, Node] = {}
        for n in nodes:
            self.add(n)

    # ----- mutation ---------------------------------------------------

    def add(self, node: Node) -> None:
        if node.name in self._nodes:
            raise ValueError(f"Duplicate node name: {node.name!r}")
        self._nodes[node.name] = node

    # ----- access -----------------------------------------------------

    def get(self, name: str) -> Node:
        if name not in self._nodes:
            raise KeyError(f"Unknown node: {name!r}")
        return self._nodes[name]

    def names(self) -> list[str]:
        return list(self._nodes.keys())

    def __iter__(self):
        return iter(self._nodes.values())

    def __len__(self) -> int:
        return len(self._nodes)

    # ----- validation + topo sort -------------------------------------

    def validate(self) -> None:
        """Validate the DAG: missing deps + acyclic.

        Raises ``MissingDependencyError`` if any node depends on an
        undeclared name, ``CyclicDependencyError`` if a cycle exists.
        """
        all_names = set(self._nodes.keys())
        for node in self._nodes.values():
            for dep in node.depends_on:
                if dep not in all_names:
                    raise MissingDependencyError(
                        f"Node {node.name!r} depends on unknown node {dep!r}"
                    )
        # Acyclic check via topo sort (raises on cycle).
        self.topological_order()

    def topological_order(self) -> list[str]:
        """Return node names in a valid topological execution order.

        Uses Kahn's algorithm. Raises ``CyclicDependencyError`` if a
        cycle exists (some nodes would never become ready).
        """
        # Build reverse adjacency: dep -> [nodes that depend on it].
        # Plus per-node remaining-dependency counters.
        remaining: dict[str, int] = {}
        dependents: dict[str, list[str]] = {n: [] for n in self._nodes}
        for node in self._nodes.values():
            remaining[node.name] = len(node.depends_on)
            for dep in node.depends_on:
                dependents[dep].append(node.name)

        ready = [n for n, c in remaining.items() if c == 0]
        # Deterministic order: sort by name so two DAGs with the same
        # structure always produce the same order.
        ready.sort()
        order: list[str] = []
        while ready:
            name = ready.pop(0)
            order.append(name)
            for child in dependents[name]:
                remaining[child] -= 1
                if remaining[child] == 0:
                    # Insert preserving sort order on next pass.
                    ready.append(child)
                    ready.sort()

        if len(order) != len(self._nodes):
            cycle_nodes = [n for n, c in remaining.items() if c > 0]
            raise CyclicDependencyError(
                f"DAG has a cycle involving: {sorted(cycle_nodes)}"
            )
        return order

    # ----- convenience -----------------------------------------------

    def validate_and_order(self) -> list[str]:
        """Shortcut: validate then return topo order."""
        self.validate()
        return self.topological_order()


def default_nodes(
    *,
    n1_body: NodeBody,
    n2_body: NodeBody,
    n3_body: NodeBody,
    n4_body: NodeBody,
    n5_body: NodeBody,
    n6_body: NodeBody,
) -> HybridDAG:
    """Construct the canonical v0.7 6-node DAG.

    Each ``*_body`` is the runnable stage injected by the runner. The
    DAG itself does not call them — the runner iterates the topological
    order and invokes ``Node.run`` for each.
    """
    dag = HybridDAG()
    dag.add(
        Node(
            name="n1_load_data",
            depends_on=(),
            run=n1_body,
            description="Load data snapshot (LLM plan)",
        )
    )
    dag.add(
        Node(
            name="n2_plan",
            depends_on=("n1_load_data",),
            run=n2_body,
            description="Plan strategies (LLM plan)",
        )
    )
    dag.add(
        Node(
            name="n3_execute",
            depends_on=("n2_plan",),
            run=n3_body,
            description="Execute backtests (multiprocessing)",
        )
    )
    dag.add(
        Node(
            name="n4_diagnose",
            depends_on=("n3_execute",),
            run=n4_body,
            description="Diagnose (7 checks incl. Q7 LLM judge)",
        )
    )
    dag.add(
        Node(
            name="n5_aggregate",
            depends_on=("n4_diagnose",),
            run=n5_body,
            description="Aggregate top-5 + report.md (LLM report)",
        )
    )
    dag.add(
        Node(
            name="n6_commit",
            depends_on=("n5_aggregate",),
            run=n6_body,
            description="Commit artifacts (git + manifest)",
        )
    )
    return dag


__all__ = [
    "Node",
    "NodeBody",
    "HybridDAG",
    "CyclicDependencyError",
    "MissingDependencyError",
    "default_nodes",
]