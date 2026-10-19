import pytest

from ai_research_trends.preprocessing.text import reconstruct_abstract


def test_reconstruct_abstract_orders_positions() -> None:
    assert reconstruct_abstract({"world": [1], "Hello": [0], "again": [2]}) == "Hello world again"
    assert reconstruct_abstract(None) is None


def test_reconstruct_abstract_rejects_duplicate_positions() -> None:
    with pytest.raises(ValueError, match="Duplicate abstract position"):
        reconstruct_abstract({"one": [0], "two": [0]})


@pytest.mark.parametrize(
    "value",
    ["not-an-object", {"token": "0"}, {"token": [True]}, {"token": [-1]}],
)
def test_reconstruct_abstract_rejects_malformed_indexes(value) -> None:
    with pytest.raises(ValueError):
        reconstruct_abstract(value)
