from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.hardware import detect_hardware


class _FakeCuda:
    @staticmethod
    def is_available() -> bool:
        return True

    @staticmethod
    def get_device_name(index: int) -> str:
        _ = index
        return "NVIDIA RTX A3000M Laptop GPU"


class _FakeTorch:
    cuda = _FakeCuda()


def _verify_mock_probe() -> None:
    mocked = detect_hardware(torch_module=_FakeTorch(), system_name="Windows")
    assert mocked.is_windows is True
    assert mocked.is_darwin is False
    assert mocked.cuda_available is True
    assert mocked.cuda_device == "cuda:0"
    assert mocked.is_rtx_a3000m is True


def main() -> int:
    _verify_mock_probe()
    context = detect_hardware()
    payload = {
        "platform_system": context.platform_system,
        "is_windows": context.is_windows,
        "is_darwin": context.is_darwin,
        "torch_available": context.torch_available,
        "cuda_available": context.cuda_available,
        "cuda_device": context.cuda_device,
        "gpu_name": context.gpu_name,
        "is_rtx_a3000m": context.is_rtx_a3000m,
    }
    print(json.dumps(payload, indent=2))
    print("hardware-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
