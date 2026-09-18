"""Workflow primitives independent of Textual widgets."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
import inspect
from typing import TypeVar, cast

T = TypeVar("T")
R = TypeVar("R")


async def run_batch(
    targets: Sequence[T],
    discover: Callable[[T], Awaitable[R]],
    limit: int = 10,
    on_result: Callable[[R], object] | None = None,
) -> list[R]:
    semaphore = asyncio.Semaphore(limit)

    async def limited(target: T) -> R:
        async with semaphore:
            return await discover(target)

    async def indexed(index: int, target: T) -> tuple[int, R]:
        return index, await limited(target)

    results: list[R | None] = [None] * len(targets)
    for completed in asyncio.as_completed([indexed(index, target) for index, target in enumerate(targets)]):
        index, result = await completed
        results[index] = result
        if on_result is not None:
            callback_result = on_result(result)
            if inspect.isawaitable(callback_result):
                await callback_result
    return cast(list[R], results)
