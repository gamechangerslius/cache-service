import asyncio
from collections import Counter
from collections.abc import Iterable


class SpyTransformer:
    def __init__(self, *, delay: float = 0, fail_on: Iterable[str] = ()) -> None:
        self.calls: Counter[str] = Counter()
        self.delay = delay
        self.fail_on = set(fail_on)
        self.active = 0
        self.max_active = 0

    async def __call__(self, text: str, /) -> str:
        self.calls[text] += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(self.delay)
        finally:
            self.active -= 1
        if text in self.fail_on:
            raise RuntimeError(f"cannot transform {text!r}")
        return text.upper()
