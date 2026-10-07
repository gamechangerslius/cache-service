import pytest

from cache_service.payloads import fingerprint, interleave, render_output

LIST_1 = ["first string", "second string", "third string"]
LIST_2 = ["other string", "another string", "last string"]


def test_interleave_alternates_starting_with_the_first_list() -> None:
    assert interleave(["a1", "a2"], ["b1", "b2"]) == ["a1", "b1", "a2", "b2"]


def test_interleave_rejects_lists_of_different_length() -> None:
    with pytest.raises(ValueError, match="shorter"):
        interleave(["a1", "a2"], ["b1"])


def test_render_output_matches_the_spec_sample() -> None:
    items = interleave([s.upper() for s in LIST_1], [s.upper() for s in LIST_2])

    assert render_output(items) == (
        "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
    )


def test_fingerprint_is_pinned() -> None:
    assert fingerprint(LIST_1, LIST_2) == (
        "db1643219a6c379b295897e1daa542e2a58690ab61fa70c673de661c46068a2f"
    )


def test_fingerprint_does_not_depend_on_the_sequence_type() -> None:
    assert fingerprint(tuple(LIST_1), tuple(LIST_2)) == fingerprint(LIST_1, LIST_2)


@pytest.mark.parametrize(
    ("first", "second"),
    [
        pytest.param((["a", "b"], ["c", "d"]), (["c", "d"], ["a", "b"]), id="swapped-lists"),
        pytest.param((["a", "b"], ["c", "d"]), (["b", "a"], ["d", "c"]), id="reordered-items"),
        pytest.param((["a,b"], ["c"]), (["a"], ["b,c"]), id="separator-inside-item"),
        pytest.param((["a"], ["b"]), (["A"], ["B"]), id="different-case"),
    ],
)
def test_fingerprint_distinguishes_different_inputs(
    first: tuple[list[str], list[str]], second: tuple[list[str], list[str]]
) -> None:
    assert fingerprint(*first) != fingerprint(*second)
