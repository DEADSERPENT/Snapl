import pytest
from app.codec import decode, encode


@pytest.mark.parametrize("n", [1, 10, 61, 62, 125, 999_999, 10_000_000])
def test_roundtrip(n):
    assert decode(encode(n)) == n


def test_zero():
    assert encode(0) == "0"


def test_short_codes_stay_short():
    # base62 of 1 million fits in 4 characters
    assert len(encode(1_000_000)) <= 4


def test_uniqueness():
    codes = [encode(i) for i in range(1000)]
    assert len(codes) == len(set(codes))
