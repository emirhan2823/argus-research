from pathlib import Path
import subprocess
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from argus_py.ml.feature_eng import extract_features, features_to_array
from argus_py.ml.signal_model import MLFeatures, SignalModel


def test_predict_without_model_returns_neutral():
    model = SignalModel()
    pred = model.predict(
        MLFeatures(
            rsi_14=50.0,
            macd_hist=0.0,
            bb_position=0.5,
            atr_pct=1.0,
            volume_ratio=1.0,
            fear_greed=50.0,
            funding_rate=0.0,
        )
    )
    assert pred.direction == "FLAT"
    assert pred.confidence == 0.5
    assert pred.expected_return == 0.0


def test_train_and_predict_on_synthetic_data():
    rng = np.random.default_rng(42)

    down_center = np.array([28.0, -1.2, 0.15, 2.5, 0.8, 20.0, 0.02], dtype=float)
    flat_center = np.array([50.0, 0.0, 0.5, 1.5, 1.0, 50.0, 0.0], dtype=float)
    up_center = np.array([72.0, 1.1, 0.85, 1.2, 1.3, 75.0, -0.01], dtype=float)

    down = down_center + rng.normal(0, [2, 0.2, 0.05, 0.2, 0.1, 3, 0.005], size=(50, 7))
    flat = flat_center + rng.normal(0, [2, 0.15, 0.05, 0.2, 0.1, 3, 0.005], size=(50, 7))
    up = up_center + rng.normal(0, [2, 0.2, 0.05, 0.2, 0.1, 3, 0.005], size=(50, 7))

    x = np.vstack([down, flat, up])
    y = np.array([0] * 50 + [1] * 50 + [2] * 50, dtype=int)

    model = SignalModel()
    model.train(x, y)

    up_pred = model.predict(MLFeatures(*up_center.tolist()))
    down_pred = model.predict(MLFeatures(*down_center.tolist()))

    assert up_pred.direction == "UP"
    assert down_pred.direction == "DOWN"
    assert up_pred.confidence >= 0.34
    assert down_pred.confidence >= 0.34


def test_save_load_roundtrip(tmp_path):
    x = np.array(
        [
            [30, -1.0, 0.2, 2.0, 0.8, 20, 0.01],
            [50, 0.0, 0.5, 1.5, 1.0, 50, 0.0],
            [70, 1.0, 0.8, 1.2, 1.3, 80, -0.01],
        ],
        dtype=float,
    )
    y = np.array([0, 1, 2], dtype=int)

    model = SignalModel()
    model.train(x, y)
    out_path = tmp_path / "signal_model_test.artifact"
    model.save(out_path)

    loaded = SignalModel(model_path=out_path)

    probe = MLFeatures(68, 0.9, 0.78, 1.3, 1.25, 76, -0.005)
    p1 = model.predict(probe)
    p2 = loaded.predict(probe)

    assert p1.direction == p2.direction
    assert abs(p1.confidence - p2.confidence) < 0.2


def test_feature_extraction_generates_valid_ranges():
    close = np.linspace(100, 120, 60)
    high = close + 1.0
    low = close - 1.0
    volume = np.linspace(1000, 1600, 60)

    feat = extract_features(close, high, low, volume, fear_greed=63.0, funding_rate=0.004)
    arr = features_to_array(feat)

    assert arr.shape == (7,)
    assert 0.0 <= feat.bb_position <= 1.0
    assert 0.0 <= feat.rsi_14 <= 100.0
    assert feat.volume_ratio > 0
    assert feat.atr_pct >= 0


def test_training_script_runs_end_to_end(tmp_path):
    csv_path = tmp_path / "train.csv"
    model_path = tmp_path / "model.out"

    csv_path.write_text(
        "rsi_14,macd_hist,bb_position,atr_pct,volume_ratio,fear_greed,funding_rate,outcome\n"
        "30,-1,0.2,2.0,0.8,20,0.01,0\n"
        "50,0,0.5,1.5,1.0,50,0.00,1\n"
        "70,1,0.8,1.2,1.3,80,-0.01,2\n"
        "31,-0.9,0.25,2.1,0.82,22,0.01,0\n"
        "51,0.1,0.48,1.6,0.98,49,0.00,1\n"
        "71,0.9,0.82,1.1,1.28,78,-0.01,2\n",
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        str(REPO_ROOT / "Scripts" / "train_ml_model.py"),
        "--input",
        str(csv_path),
        "--output",
        str(model_path),
    ]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)

    assert proc.returncode == 0, proc.stderr
    assert model_path.exists()
    assert "Model trained and saved" in proc.stdout
