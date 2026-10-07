"""Payload generation rules, independent of HTTP and storage."""

import hashlib
import json
from collections.abc import Iterable, Sequence

OUTPUT_SEPARATOR = ", "


def interleave(first: Sequence[str], second: Sequence[str]) -> list[str]:
    """Return ``[first[0], second[0], first[1], second[1], ...]``.

    ``strict`` makes a length mismatch an error instead of silently dropping the tail.
    """
    return [item for pair in zip(first, second, strict=True) for item in pair]


def render_output(items: Iterable[str]) -> str:
    return OUTPUT_SEPARATOR.join(items)


def fingerprint(list_1: Sequence[str], list_2: Sequence[str]) -> str:
    """Identify a payload request by its inputs.

    Hashing the inputs (not the output) lets a repeated request be recognised before
    anything is transformed. JSON keeps item and list boundaries, so ``["a,b"], ["c"]``
    and ``["a"], ["b,c"]`` differ, and its ASCII-only output always encodes.

    Changing this canonical form orphans every stored payload: repeats would no longer
    match and would get new identifiers.
    """
    canonical = json.dumps([list(list_1), list(list_2)], separators=(",", ":"))
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()
