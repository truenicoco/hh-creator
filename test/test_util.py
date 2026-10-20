from decimal import Decimal

import pytest

import hh_creator.util as ut


@pytest.mark.parametrize(
    "in_,prec,out",
    [
        (Decimal("1.325"), 3, "1.325"),
        (2, 3, "2"),
        (Decimal("0.5"), 3, "0.5"),
        (Decimal("0.500"), 3, "0.5"),
        (Decimal(100), 3, "100"),  # not 1E+2BB
    ],
)
def test_format_amount(in_, prec, out: str):
    assert ut.amount_format(in_, prec) == out


@pytest.mark.parametrize(
    "in_,out",
    [
        (1000, "1k"),
        (1000000, "1M"),
        (1201459, "1.201M"),
    ],
)
def test_format_amount_blind(in_: float, out: str):
    assert ut.amount_format(in_) == out
