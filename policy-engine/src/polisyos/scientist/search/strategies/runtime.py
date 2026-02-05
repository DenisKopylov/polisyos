"""Runtime helpers for Torch-backed search strategies."""

from __future__ import annotations

import os

from loguru import logger


def apply_torch_runtime_settings(torch_module) -> str:
    """
    Apply Torch runtime limits from environment variables.

    Returns:
        Preferred torch device name.
    """
    num_threads = int(os.getenv("SCIENTIST_TORCH_NUM_THREADS", "4"))
    interop_threads = int(os.getenv("SCIENTIST_TORCH_NUM_INTEROP_THREADS", "1"))
    device = os.getenv("SCIENTIST_TORCH_DEVICE", "cpu").lower()

    try:
        torch_module.set_num_threads(max(1, num_threads))
    except Exception:
        pass
    try:
        torch_module.set_num_interop_threads(max(1, interop_threads))
    except Exception:
        pass

    logger.info(
        "Torch runtime configured: device={} threads={} interop_threads={}",
        device,
        num_threads,
        interop_threads,
    )
    return device

