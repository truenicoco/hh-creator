from decimal import Decimal

import hh_creator.util as ut


def test_format_amount():
    assert ut.amount_format(Decimal("1.325"), 3) == "1.325"
    assert ut.amount_format(2, 3) == "2"
    assert ut.amount_format(Decimal(0.5), 3) == "0.5"
    assert ut.amount_format(Decimal("0.500"), 3) == "0.5"
    assert ut.amount_format(Decimal("100")) == "100"  # not 1E+2BB
