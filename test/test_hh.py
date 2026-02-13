from pathlib import Path

import pytest

from hh_creator.hh import HandHistory, Position, Street


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
