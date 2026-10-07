"""PayloadCreate is the single validation gate shared by the API and the CLI."""

import pytest
from pydantic import ValidationError

from cache_service.schemas import MAX_ITEMS, MAX_STRING_LENGTH, PayloadCreate

SAMPLE = {
    "list_1": ["first string", "second string", "third string"],
    "list_2": ["other string", "another string", "last string"],
}


def test_accepts_spec_sample() -> None:
    payload = PayloadCreate.model_validate(SAMPLE)

    assert payload.list_1 == SAMPLE["list_1"]
    assert payload.list_2 == SAMPLE["list_2"]


def test_accepts_inputs_at_the_limits() -> None:
    longest = "x" * MAX_STRING_LENGTH

    payload = PayloadCreate(list_1=[longest] * MAX_ITEMS, list_2=[longest] * MAX_ITEMS)

    assert len(payload.list_1) == len(payload.list_2) == MAX_ITEMS


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        pytest.param({"list_1": ["a", "b"], "list_2": ["c"]}, "same length", id="unequal-lengths"),
        pytest.param({"list_1": [], "list_2": []}, "at least 1 item", id="empty-lists"),
        pytest.param({"list_1": ["a"]}, "Field required", id="missing-list"),
        pytest.param(
            {"list_1": ["a"] * (MAX_ITEMS + 1), "list_2": ["b"] * (MAX_ITEMS + 1)},
            f"at most {MAX_ITEMS} items",
            id="too-many-items",
        ),
        pytest.param(
            {"list_1": ["x" * (MAX_STRING_LENGTH + 1)], "list_2": ["y"]},
            f"at most {MAX_STRING_LENGTH} characters",
            id="string-too-long",
        ),
        pytest.param({"list_1": [1], "list_2": ["b"]}, "valid string", id="non-string-item"),
        # Valid JSON ("\ud800" escape) that SQLite cannot store; must be a 422, not a 500.
        pytest.param({"list_1": ["a\ud800"], "list_2": ["b"]}, "unicode", id="lone-surrogate"),
        pytest.param(
            {"list_1": ["a"], "list_2": ["b"], "list3": ["c"]}, "Extra inputs", id="unknown-key"
        ),
    ],
)
def test_rejects_invalid_body(body: dict[str, object], reason: str) -> None:
    with pytest.raises(ValidationError, match=reason):
        PayloadCreate.model_validate(body)
