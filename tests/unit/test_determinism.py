from pathlib import Path
import csv
import json
import random
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.lab.determinism import DeterminismManager, RunManifest


def test_initialize_sets_seeds_reproducibly():
    dm = DeterminismManager(seed=123)

    dm.initialize()
    py_1 = random.random()
    np_1 = np.random.rand()

    dm.initialize()
    py_2 = random.random()
    np_2 = np.random.rand()

    assert py_1 == py_2
    assert np_1 == np_2


def test_hash_config_is_stable():
    dm = DeterminismManager()
    a = dm.hash_config({"b": 2, "a": 1})
    b = dm.hash_config({"a": 1, "b": 2})
    assert a == b


def test_hash_data_file_and_directory(tmp_path):
    dm = DeterminismManager()

    file_path = tmp_path / "x.csv"
    file_path.write_text("a,b\n1,2\n", encoding="utf-8")
    file_hash = dm.hash_data(file_path)
    assert isinstance(file_hash, str)
    assert len(file_hash) == 16

    dir_path = tmp_path / "data"
    dir_path.mkdir()
    (dir_path / "a.csv").write_text("x\n1\n", encoding="utf-8")
    (dir_path / "b.csv").write_text("x\n2\n", encoding="utf-8")
    dir_hash = dm.hash_data(dir_path)
    assert isinstance(dir_hash, str)
    assert len(dir_hash) == 16


def test_manifest_contains_all_metadata(tmp_path):
    dm = DeterminismManager(seed=7)

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "a.csv").write_text("x\n1\n", encoding="utf-8")

    trades = tmp_path / "trades.csv"
    trades.write_text("ts,pnl\n1,2\n", encoding="utf-8")

    manifest = dm.create_manifest(
        run_id="r1",
        config={"foo": "bar"},
        data_path=data_dir,
        trades_csv=trades,
    )

    assert isinstance(manifest, RunManifest)
    assert manifest.run_id == "r1"
    assert manifest.seed == 7
    assert manifest.config_hash
    assert manifest.data_hash
    assert manifest.result_hash


def test_compare_runs_detects_determinism(tmp_path):
    dm = DeterminismManager(seed=42)

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "a.csv").write_text("x\n1\n", encoding="utf-8")

    trades_1 = tmp_path / "run1.csv"
    trades_2 = tmp_path / "run2.csv"
    payload = "ts,pnl\n1,1\n2,2\n"
    trades_1.write_text(payload, encoding="utf-8")
    trades_2.write_text(payload, encoding="utf-8")

    m1 = dm.create_manifest("r1", {"seed": 42}, data_dir, trades_1)
    m2 = dm.create_manifest("r2", {"seed": 42}, data_dir, trades_2)

    cmp = dm.compare_runs(m1, m2)
    assert cmp["same_seed"] is True
    assert cmp["same_config"] is True
    assert cmp["same_data"] is True
    assert cmp["same_result"] is True
    assert cmp["is_deterministic"] is True


def test_save_manifest_writes_json(tmp_path):
    dm = DeterminismManager(seed=1)
    m = RunManifest("rid", 1, "2026-01-01T00:00:00", "abc12345", "cfg", "data", "res")
    out = tmp_path / "manifest.json"

    dm.save_manifest(m, out)

    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["run_id"] == "rid"
    assert payload["seed"] == 1
