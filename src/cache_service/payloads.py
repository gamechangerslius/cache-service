import hashlib
import json
from collections.abc import Iterable, Sequence

OUTPUT_SEPARATOR = ", "


def interleave(first: Sequence[str], second: Sequence[str]) -> list[str]:
    return [item for pair in zip(first, second, strict=True) for item in pair]


def render_output(items: Iterable[str]) -> str:
    return OUTPUT_SEPARATOR.join(items)


def fingerprint(list_1: Sequence[str], list_2: Sequence[str]) -> str:
    canonical = json.dumps([list(list_1), list(list_2)], separators=(",", ":"))
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()
