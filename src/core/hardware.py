"""Hardware capability detection for Darwin/Windows runtimes."""

from __future__ import annotations

import platform
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HardwareContext:
    platform_system: str
    is_windows: bool
    is_darwin: bool
    torch_available: bool
    cuda_available: bool
    cuda_device: str
    gpu_name: str | None
    is_rtx_a3000m: bool


def detect_hardware(*, torch_module: Any | None = None, system_name: str | None = None) -> HardwareContext:
    system = (system_name or platform.system()).strip()
    normalized = system.lower()
    is_windows = normalized == "windows"
    is_darwin = normalized == "darwin"

    if torch_module is None:
        try:
            import torch as torch_module  # type: ignore[no-redef]
        except Exception:
            torch_module = None

    torch_available = torch_module is not None
    cuda_available = False
    cuda_device = "cpu"
    gpu_name: str | None = None

    if torch_module is not None:
        cuda_obj = getattr(torch_module, "cuda", None)
        is_available = getattr(cuda_obj, "is_available", None)
        if callable(is_available):
            try:
                cuda_available = bool(is_available())
            except Exception:
                cuda_available = False

        if cuda_available:
            cuda_device = "cuda:0"
            get_device_name = getattr(cuda_obj, "get_device_name", None)
            if callable(get_device_name):
                try:
                    gpu_name = str(get_device_name(0))
                except Exception:
                    gpu_name = None

    gpu_name_norm = (gpu_name or "").lower()
    is_rtx_a3000m = "rtx a3000m" in gpu_name_norm or "rtx a3000" in gpu_name_norm

    return HardwareContext(
        platform_system=system,
        is_windows=is_windows,
        is_darwin=is_darwin,
        torch_available=torch_available,
        cuda_available=cuda_available,
        cuda_device=cuda_device,
        gpu_name=gpu_name,
        is_rtx_a3000m=is_rtx_a3000m,
    )


DEFAULT_HARDWARE_CONTEXT = detect_hardware()
