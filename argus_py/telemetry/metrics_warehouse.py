from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import json
import sqlite3

import pandas as pd

try:
    import redis as redis_mod  # type: ignore
except Exception:  # pragma: no cover
    redis_mod = None


@dataclass(frozen=True)
class MetricPoint:
    key: str
    value: float
    ts_utc: str
    source: str
    tags: Dict[str, Any]


@dataclass(frozen=True)
class WarehouseWriteResult:
    hot_written: bool
    warm_written: bool
    cold_written: bool
    warnings: List[str]


class MetricsWarehouse:
    """
    Multi-tier metrics storage:
    - Hot: Redis (best effort)
    - Warm: Parquet partition files (fallback to JSONL if parquet engine unavailable)
    - Cold: SQLite (authoritative)
    """

    def __init__(
        self,
        *,
        redis_url: Optional[str] = None,
        warm_dir: Path = Path("runs/year2/warehouse/warm"),
        cold_db: Path = Path("runs/year2/warehouse/cold/metrics.sqlite3"),
    ) -> None:
        self.warm_dir = Path(warm_dir)
        self.warm_dir.mkdir(parents=True, exist_ok=True)
        self.cold_db = Path(cold_db)
        self.cold_db.parent.mkdir(parents=True, exist_ok=True)
        self.redis_url = redis_url
        self._redis = self._connect_redis(redis_url)
        self._init_sqlite()

    def write(self, point: MetricPoint) -> WarehouseWriteResult:
        self._validate_point(point)
        warnings: List[str] = []

        hot_ok = self._write_hot(point, warnings)
        warm_ok = self._write_warm(point, warnings)
        cold_ok = self._write_cold(point, warnings)

        return WarehouseWriteResult(
            hot_written=hot_ok,
            warm_written=warm_ok,
            cold_written=cold_ok,
            warnings=warnings,
        )

    def read_cold(self, key: str, limit: int = 200) -> List[MetricPoint]:
        with sqlite3.connect(self.cold_db) as conn:
            rows = conn.execute(
                """
                SELECT key, value, ts_utc, source, tags_json
                FROM metrics
                WHERE key = ?
                ORDER BY ts_utc DESC
                LIMIT ?
                """,
                (key, int(limit)),
            ).fetchall()

        out: List[MetricPoint] = []
        for k, v, ts, src, tags_json in rows:
            tags = json.loads(tags_json) if tags_json else {}
            out.append(MetricPoint(key=str(k), value=float(v), ts_utc=str(ts), source=str(src), tags=tags))
        return out

    def read_hot(self, key: str) -> Optional[MetricPoint]:
        if self._redis is None:
            return None
        raw = self._redis.get(f"argus:metric:{key}")
        if not raw:
            return None
        payload = json.loads(raw)
        return MetricPoint(
            key=str(payload["key"]),
            value=float(payload["value"]),
            ts_utc=str(payload["ts_utc"]),
            source=str(payload["source"]),
            tags=dict(payload.get("tags") or {}),
        )

    def _write_hot(self, point: MetricPoint, warnings: List[str]) -> bool:
        if self._redis is None:
            warnings.append("hot_store_unavailable: redis not configured or dependency missing")
            return False
        try:
            payload = {
                "key": point.key,
                "value": point.value,
                "ts_utc": point.ts_utc,
                "source": point.source,
                "tags": point.tags,
            }
            self._redis.set(f"argus:metric:{point.key}", json.dumps(payload), ex=3600)
            return True
        except Exception as exc:  # pragma: no cover
            warnings.append(f"hot_store_write_failed: {exc}")
            return False

    def _write_warm(self, point: MetricPoint, warnings: List[str]) -> bool:
        date_part = point.ts_utc[:10]
        partition_dir = self.warm_dir / f"date={date_part}"
        partition_dir.mkdir(parents=True, exist_ok=True)
        parquet_path = partition_dir / "metrics.parquet"

        row = {
            "key": point.key,
            "value": point.value,
            "ts_utc": point.ts_utc,
            "source": point.source,
            "tags_json": json.dumps(point.tags, ensure_ascii=True),
        }
        df = pd.DataFrame([row])

        try:
            if parquet_path.exists():
                prev = pd.read_parquet(parquet_path)
                merged = pd.concat([prev, df], axis=0, ignore_index=True)
                merged.to_parquet(parquet_path, index=False)
            else:
                df.to_parquet(parquet_path, index=False)
            return True
        except Exception as exc:
            fallback = partition_dir / "metrics.parquet.unavailable.jsonl"
            with fallback.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=True) + "\n")
            warnings.append(f"warm_store_parquet_unavailable: {exc}")
            return True

    def _write_cold(self, point: MetricPoint, warnings: List[str]) -> bool:
        try:
            with sqlite3.connect(self.cold_db) as conn:
                conn.execute(
                    """
                    INSERT INTO metrics (key, value, ts_utc, source, tags_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        point.key,
                        point.value,
                        point.ts_utc,
                        point.source,
                        json.dumps(point.tags, ensure_ascii=True),
                    ),
                )
                conn.commit()
            return True
        except Exception as exc:
            warnings.append(f"cold_store_write_failed: {exc}")
            return False

    def _init_sqlite(self) -> None:
        with sqlite3.connect(self.cold_db) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    value REAL NOT NULL,
                    ts_utc TEXT NOT NULL,
                    source TEXT NOT NULL,
                    tags_json TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_key_ts ON metrics(key, ts_utc)")
            conn.commit()

    def _validate_point(self, point: MetricPoint) -> None:
        if not point.key.strip():
            raise ValueError("metric key cannot be empty")
        if not point.source.strip():
            raise ValueError("metric source cannot be empty")
        try:
            datetime.fromisoformat(point.ts_utc.replace("Z", "+00:00"))
        except Exception as exc:
            raise ValueError(f"invalid ts_utc format: {point.ts_utc}") from exc

    def _connect_redis(self, redis_url: Optional[str]):
        if not redis_url or redis_mod is None:
            return None
        try:
            client = redis_mod.Redis.from_url(redis_url, decode_responses=True)
            client.ping()
            return client
        except Exception:
            return None


def make_metric_point(
    key: str,
    value: float,
    source: str,
    tags: Optional[Dict[str, Any]] = None,
) -> MetricPoint:
    return MetricPoint(
        key=str(key),
        value=float(value),
        ts_utc=datetime.now(timezone.utc).isoformat(),
        source=str(source),
        tags=dict(tags or {}),
    )


__all__ = [
    "MetricPoint",
    "WarehouseWriteResult",
    "MetricsWarehouse",
    "make_metric_point",
]
