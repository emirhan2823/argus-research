from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict


@dataclass
class ProfileResult:
    name: str
    calls: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.calls if self.calls > 0 else 0.0


class Profiler:
    def __init__(self):
        self.results: Dict[str, ProfileResult] = {}

    @contextmanager
    def measure(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - start) * 1000.0

            if name not in self.results:
                self.results[name] = ProfileResult(name)
            result = self.results[name]
            result.calls += 1
            result.total_ms += elapsed
            result.min_ms = min(result.min_ms, elapsed)
            result.max_ms = max(result.max_ms, elapsed)

    def report(self) -> str:
        lines = ["=== Performance Profile ==="]
        for name, result in sorted(self.results.items(), key=lambda x: -x[1].total_ms):
            lines.append(
                f"{name}: {result.calls} calls, avg={result.avg_ms:.2f}ms, total={result.total_ms:.0f}ms"
            )
        return "\n".join(lines)
