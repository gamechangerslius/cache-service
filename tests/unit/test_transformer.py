import time

import pytest

from cache_service.transformer import SimulatedTransformer


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("first string", "FIRST STRING"),
        ("", ""),
        ("Mixed Case 123!", "MIXED CASE 123!"),
        # Python's full Unicode case mapping can change the length of a string.
        ("straße", "STRASSE"),
    ],
)
async def test_uppercases_text(text: str, expected: str) -> None:
    transformer = SimulatedTransformer(latency_seconds=0)

    assert await transformer(text) == expected


async def test_waits_for_the_configured_latency() -> None:
    latency = 0.05
    transformer = SimulatedTransformer(latency_seconds=latency)

    started = time.perf_counter()
    await transformer("text")

    # A small tolerance for the event loop's clock resolution.
    assert time.perf_counter() - started >= latency * 0.9
