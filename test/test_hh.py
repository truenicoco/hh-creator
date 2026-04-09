from decimal import Decimal
from pathlib import Path

import pytest

from hh_creator.hh import HandHistory, Position, Street
from hh_creator.util import ActionType


@pytest.mark.parametrize("file_name", ["hu1.hh", "hu2.hh"])
def test_hu_player_order(file_name: str) -> None:
    hh = HandHistory.from_json((Path(__file__).parent / file_name).read_text())
    streets = set()
    for action in hh.actions:
        if action.street in streets:
            continue
        streets.add(action.street)
        first_player_for_street = action.player
        if action.street <= Street.PRE_FLOP:
            assert first_player_for_street.position == Position.SB, action.street
        else:
            assert action.player.position == Position.BB, action.street


@pytest.mark.parametrize("file_name", ["fold_flop.hh", "fold_preflop.hh"])
def test_remaining_action(file_name: str) -> None:
    hh = HandHistory.from_json((Path(__file__).parent / "fold_flop.hh").read_text())
    assert hh.n_pseudo_actions() == 0


def test_allin_ante():
    hh = HandHistory(
        [
            Decimal("22.1"),
            Decimal("22.1"),
            Decimal("22.1"),
            Decimal("8.1"),
            Decimal("22.1"),
            Decimal("22.1"),
        ],
        ante=Decimal("0.125"),
    )
    hh.post_blinds_and_antes()
    hh.add_action(ActionType.FOLD)
    hh.add_action(ActionType.RAISE, Decimal("6.975"))
    hh.add_action(ActionType.FOLD)
    hh.add_action(ActionType.RAISE, Decimal("8.025"))
    min_raise = hh.minimum_raise()
    min_bet = min(
        min_raise + hh.current_player_amount_to_call() + hh.current_player_street_bet(),
        hh.current_player.stack,
    )
    adjusted = min_bet - hh.current_player_amount_to_call()
    hh.add_action(ActionType.RAISE, adjusted)
