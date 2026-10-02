"""DEMO / TESTING ONLY.

Mounted only when FAULT_INJECTION_ENABLED=true.
Do not publish these routes through a public ingress.
"""

import asyncio
import os
import signal
import time

from fastapi import APIRouter, HTTPException

from app.logging_config import get_logger

router = APIRouter(prefix="/debug", tags=["debug"])
logger = get_logger()

DEMO_NOTICE = "DEMO / TESTING ONLY"
MAX_SLOW_SECONDS = 10
MAX_MEMORY_MB = 64
MAX_CPU_SECONDS = 5


def terminate_process() -> None:
    """Stop the API process so Kubernetes can restart the container."""
    os.kill(os.getpid(), signal.SIGTERM)


@router.post("/error")
def forced_error() -> None:
    logger.error(
        f"{DEMO_NOTICE}: forced server error",
        extra={"endpoint": "POST /debug/error", "status_code": 500},
    )
    raise HTTPException(status_code=500, detail=f"{DEMO_NOTICE}: forced server error")


@router.post("/slow")
async def slow(seconds: float = 2) -> dict[str, object]:
    if seconds < 0 or seconds > MAX_SLOW_SECONDS:
        raise HTTPException(
            status_code=400,
            detail=f"{DEMO_NOTICE}: seconds must be between 0 and {MAX_SLOW_SECONDS}",
        )
    logger.warning(
        f"{DEMO_NOTICE}: delaying response",
        extra={"endpoint": "POST /debug/slow", "status_code": 200},
    )
    await asyncio.sleep(seconds)
    return {"status": "ok", "notice": DEMO_NOTICE, "delayed_seconds": seconds}


@router.post("/memory")
async def memory(megabytes: int = 32) -> dict[str, object]:
    if megabytes < 1 or megabytes > MAX_MEMORY_MB:
        raise HTTPException(
            status_code=400,
            detail=f"{DEMO_NOTICE}: megabytes must be between 1 and {MAX_MEMORY_MB}",
        )

    def allocate() -> int:
        blob = bytearray(megabytes * 1024 * 1024)
        for index in range(0, len(blob), 4096):
            blob[index] = 1
        checksum = blob[0] + blob[-1]
        del blob
        return checksum

    logger.warning(
        f"{DEMO_NOTICE}: allocating bounded memory",
        extra={"endpoint": "POST /debug/memory", "status_code": 200},
    )
    checksum = await asyncio.to_thread(allocate)
    return {
        "status": "ok",
        "notice": DEMO_NOTICE,
        "megabytes": megabytes,
        "checksum": checksum,
    }


@router.post("/cpu")
async def cpu(seconds: float = 2) -> dict[str, object]:
    if seconds <= 0 or seconds > MAX_CPU_SECONDS:
        raise HTTPException(
            status_code=400,
            detail=f"{DEMO_NOTICE}: seconds must be between 0 and {MAX_CPU_SECONDS}",
        )

    def burn() -> int:
        deadline = time.perf_counter() + seconds
        value = 0
        while time.perf_counter() < deadline:
            value = (value + 1) % 1_000_003
        return value

    logger.warning(
        f"{DEMO_NOTICE}: generating bounded CPU load",
        extra={"endpoint": "POST /debug/cpu", "status_code": 200},
    )
    await asyncio.to_thread(burn)
    return {"status": "ok", "notice": DEMO_NOTICE, "seconds": seconds}


@router.post("/crash")
def crash() -> dict[str, str]:
    logger.error(
        f"{DEMO_NOTICE}: terminating API process",
        extra={"endpoint": "POST /debug/crash", "status_code": 500},
    )
    terminate_process()
    return {"status": "terminating", "notice": DEMO_NOTICE}
