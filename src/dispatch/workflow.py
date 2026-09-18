"""Workflow primitives independent of Textual widgets."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


async def run_batch(targets: Sequence[T], discover: Callable[[T], Awaitable[R]], limit: int = 10) -> list[R]:
    semaphore = asyncio.Semaphore(limit)

    async def limited(target: T) -> R:
        async with semaphore:
            return await discover(target)

    return list(await asyncio.gather(*(limited(target) for target in targets)))
