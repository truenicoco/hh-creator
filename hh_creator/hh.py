import json
import logging
from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Union

from poker.constants import PokerEnum

from hh_creator.util import BLINDS, ActionType, IncrementableEnum


class Position(PokerEnum):
    UTG = "UTG", "under the gun"
    UTG1 = "UTG1", "utg+1", "utg + 1"
    UTG2 = "UTG2", "utg+2", "utg + 2"
    UTG3 = "UTG3", "utg+3", "utg + 3"
    UTG4 = "UTG4", "utg+4", "utg + 4"
    HJ = "HJ", "hijack", "utg+5", "utg + 5"
    CO = "CO", "cutoff", "cut off"
    BTN = "BTN", "bu", "button"
    SB = "SB", "small blind"
    BB = "BB", "big blind"


POSITIONS = {
    2: [Position.SB, Position.BB],
    3: [Position.SB, Position.BB, Position.BTN],
    4: [Position.SB, Position.BB, Position.UTG, Position.BTN],
    5: [Position.SB, Position.BB, Position.UTG, Position.CO, Position.BTN],
    6: [Position.SB, Position.BB, Position.UTG, Position.HJ, Position.CO, Position.BTN],
    7: [
        Position.SB,
        Position.BB,
        Position.UTG,
        Position.UTG1,
        Position.HJ,
        Position.CO,
        Position.BTN,
    ],
    8: [
        Position.SB,
        Position.BB,
        Position.UTG,
        Position.UTG1,
        Position.UTG2,
        Position.HJ,
        Position.CO,
        Position.BTN,
    ],
    9: [
        Position.SB,
        Position.BB,
        Position.UTG,
        Position.UTG1,
        Position.UTG2,
        Position.UTG3,
        Position.HJ,
        Position.CO,
        Position.BTN,
    ],
    10: [
        Position.SB,
        Position.BB,
        Position.UTG,
        Position.UTG1,
        Position.UTG2,
        Position.UTG3,
        Position.UTG4,
        Position.HJ,
        Position.CO,
        Position.BTN,
    ],
}


class HandHistoryException(Exception):
    def __init__(self, message=""):
        self.message = message

    def __str__(self):
        return f"{self.__class__.__name__}: {self.message}"


class InvalidAction(HandHistoryException):
    pass


class InvalidAmount(HandHistoryException):
    pass


class Street(IncrementableEnum):
    ANTE = 0
    PRE_FLOP = 1
    FLOP = 2
    TURN = 3
    RIVER = 4
    SHOWDOWN = 5


@dataclass
class Action:
    street: Union[Street, None] = None
    player: Union["Player", None] = None
    action_type: Union[ActionType, None] = None
    amount: Decimal = Decimal("0")
    added_to_pot: Decimal = Decimal("0")


@dataclass
class Player:
    position: Position
    hand_history: "HandHistory"
    actions: List[Action] = field(default_factory=list)
    stack: Decimal = Decimal("100")

    def __post_init__(self):
        self.initial_stack = self.stack

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"{self.position} ({self.stack})"

    def __eq__(self, other):
        return self.position == other.position

    def street_bet(self, street=None):
        if street is None:
            street = self.hand_history.current_street
        return sum(
            [
                a.added_to_pot
                for a in self.actions
                if a.street == street and a.action_type != ActionType.ANTE
            ]
        )

    def has_not_played_for_street(self, street):
        return len([a for a in self.actions if a.street == street]) == 0

    def has_folded(self):
        if len(self.actions) == 0:
            return False
        return self.actions[-1].action_type == ActionType.FOLD

    def add_action(self, action):
        self.actions.append(action)
        self.stack -= action.added_to_pot
        log.debug(f"{self.position} now has {self.stack}")

    def at_action(self, cursor):
        if cursor is None:
            return self
        else:
            hh = self.hand_history.at_action(cursor)
            return hh.get_player_by_position(self.position)
            # return [
            #     p
            #     for p in .players
            #     if p.position == self.position
            # ][0]

    def invested_in_pot(self):
        return sum(a.added_to_pot for a in self.actions)

    @property
    def last_action(self):
        if self.actions:
            return self.actions[-1]
        else:
            return Action()


class HandHistory:
    def __init__(
        self,
        stacks: Union[List[Decimal], None] = None,
        small_blind: Decimal = Decimal("0.5"),
        ante: Decimal = Decimal("0."),
        big_blind: Union[Decimal, None] = None,
        bb_ante: Union[Decimal, None] = None,
        n_straddle: int = 0,
    ):
        self.small_blind = small_blind
        if big_blind is None:
            big_blind = 2 * small_blind
        self.big_blind = big_blind
        self.actions: List[Action] = []
        self.ante = ante
        self.bb_ante = bb_ante

        self.players = []

        if stacks is not None:
            self.set_stacks(stacks)

        self.current_street = Street.ANTE
        self.current_player: Union[Player, None] = None
        self.total_pot = Decimal("0")

        self._blinds_posted = False

        self.winner: Union[Player, None] = None

        self.n_straddle = n_straddle
        self.largest_blind = 0

    def set_stacks(self, stacks: List[Decimal]):
        for stack, pos in zip(stacks, POSITIONS[len(stacks)]):
            self.players.append(
                Player(position=pos, stack=Decimal(stack), hand_history=self)
            )

    def post_blinds_and_antes(self):
        self.current_player = self.players[0]
        if self.ante:
            for _ in range(len(self.players)):
                self.add_action(ActionType.ANTE, self.ante)
        if self.bb_ante:
            self.add_action(ActionType.ANTE, Decimal(0))
            self.add_action(ActionType.ANTE, self.bb_ante)
            for _ in range(len(self.players) - 2):
                self.add_action(ActionType.ANTE, Decimal(0))

        self.current_street = Street.PRE_FLOP
        self.add_action(ActionType.SB, min(self.small_blind, self.current_player.stack))
        self.add_action(ActionType.BB, min(self.big_blind, self.current_player.stack))

        for _ in range(self.n_straddle):
            self.add_action(
                ActionType.STRADDLE,
                min(self.last_action.amount * 2, self.current_player.stack),
            )

        self.largest_blind = self.last_action.amount

        self._blinds_posted = True

    def get_player_by_position(self, position: Position):
        for p in self.players:
            if p.position == position:
                return p

    def _non_folded_players_after_current(self):
        start = self.players.index(self.current_player) + 1
        players = self.players[start:] + self.players[:start]
        players = [p for p in players if not p.has_folded()]
        return players

    def _next_player(self):
        players = self._non_folded_players_after_current()
        if len(players) == 1:
            self.winner = players[0]
            self.current_player = None
            log.info(f"{self.winner} wins because everybody has folded")
            return
        for player in players:
            if player.stack <= 0:
                continue
            if (
                self.current_street == Street.PRE_FLOP
                and player.last_action.action_type in BLINDS
                and self.total_amount_to_call == self.largest_blind
                and self.actions[-1].player != player
            ):
                self.current_player = player
                break
            if player.has_not_played_for_street(self.current_street):
                self.current_player = player
                break
            if player.street_bet(self.current_street) < self.total_amount_to_call:
                self.current_player = player
                break
        else:
            self._next_street()

    def _next_street(self):
        # HU special case
        if len(self.players) == 2 and self.current_street == Street.PRE_FLOP:
            self.players = self.players[::-1]
        self.current_street = self.current_street.next()
        if self.current_street == Street.SHOWDOWN:
            log.info("No more action possible, showdown time")
            self.current_player = None
            return
        self.current_player = self.players[-1]
        possible_players = self._non_folded_players_after_current()
        if sum(p.stack > 0 for p in possible_players) == 1:
            self.current_player = None
            self.current_street = Street.SHOWDOWN
            return
        self._next_player()

    @property
    def central_pot(self):
        tot = self.total_pot
        if self.current_street == Street.PRE_FLOP:
            tot += sum(p.street_bet(Street.ANTE) for p in self.players)
        # else:
        #     tot = self.side_pots()[0].amount
        return tot - sum(p.street_bet(self.current_street) for p in self.players)

    @property
    def total_amount_to_call(self):
        res = 0
        if self.current_street == Street.PRE_FLOP:
            res += self.largest_blind
        for a in reversed(self.actions):
            if a.street != self.current_street:
                break
            if a.action_type == ActionType.RAISE:
                res += a.amount
            if a.action_type == ActionType.BET:
                return res + a.amount
            # if a.action_type == ActionType.BET:
            #     if all(  # everybody limps, BB bets preflop special case
            #         (
            #             a.street == Street.PRE_FLOP,
            #             len(a.player.actions) > 1,
            #             a.player.actions[-2].action_type in BLINDS,
            #         )
            #     ):
            #         return res + a.amount + self.largest_blind
            #     return res + a.amount
            #
            # if a.action_type in BLINDS and a.amount == self.largest_blind:
            #     res += a.amount
        if self.current_street == Street.PRE_FLOP:
            res = max(res, self.largest_blind)
        return res

    @property
    def last_action(self):
        if self.actions:
            return self.actions[-1]

    def possible_action_types(self):
        player = self.current_player
        if player is None:
            return []
        actions = [ActionType.FOLD]
        to_call = self.current_player_amount_to_call()
        if to_call == 0:
            actions.append(ActionType.RAISE)
            actions.append(ActionType.BET)
            actions.append(ActionType.CHECK)
        else:
            actions.append(ActionType.CALL)
            if player.stack > to_call and player.stack > self.minimum_raise():
                actions.append(ActionType.RAISE)
        return actions

    def add_action(self, action_type: ActionType, amount: Union[None, Decimal] = None):
        if self._blinds_posted and action_type not in self.possible_action_types():
            raise InvalidAction
        if action_type == ActionType.BET:
            if amount < self.big_blind:
                raise InvalidAmount("Bet is less than BB")
            added_to_pot = amount
        elif action_type == ActionType.CALL:
            added_to_pot = self.current_player_amount_to_call()
            amount = added_to_pot
        elif action_type == ActionType.RAISE:
            if amount < self.minimum_raise():
                raise InvalidAmount("Raise is too small")
            added_to_pot = amount + self.current_player_amount_to_call()
        elif action_type in BLINDS + [ActionType.ANTE]:
            added_to_pot = amount
        else:
            added_to_pot = Decimal(0)

        if added_to_pot > self.current_player.stack:
            raise InvalidAmount

        log.info(
            f"Action #{len(self.actions) + 1} ({self.current_street}): "
            f"{self.current_player}: {action_type}, "
            f"amount={amount}, added_to_pot={added_to_pot}, "
            # f"side_pots={self.side_pots}"
        )

        action = Action(
            street=self.current_street,
            player=self.current_player,
            amount=amount,
            action_type=action_type,
            added_to_pot=added_to_pot,
        )
        self.actions.append(action)
        self.current_player.add_action(action)

        self.total_pot += added_to_pot

        self._next_player()
        log.debug(
            f"Total amount to call: {self.total_amount_to_call}, "
            f"total pot:{self.total_pot}, central_pot:{self.central_pot}, "
            f"side_pots: {self.side_pots()}, current_street:{self.current_street}"
        )

    def remove_last_action(self):
        action = self.actions.pop()
        action.player.stack += action.added_to_pot
        action.player.actions.pop()
        self.total_pot -= action.added_to_pot
        self.current_player = action.player
        self.current_street = action.street
        self.winner = None

    def current_player_street_bet(self):
        return self.current_player.street_bet(self.current_street)

    def current_player_amount_to_call(self):
        return min(
            self.total_amount_to_call - self.current_player_street_bet(),
            self.current_player.stack,
        )

    def has_editable_actions(self):
        return len(self.editable_actions()) > 0

    def minimum_raise(self):
        for action in reversed(self.actions):
            if action.street != self.current_street:
                return self.big_blind
            if action.action_type in (
                ActionType.BET,
                ActionType.RAISE,
                ActionType.BB,
                ActionType.STRADDLE,
            ):
                return action.amount

    def editable_actions(self):
        return [
            a
            for a in self.actions
            if a.action_type
            not in (ActionType.ANTE, ActionType.BB, ActionType.SB, ActionType.STRADDLE)
        ]

    def at_action(self, cursor):
        if cursor is None:
            return self
        copy = deepcopy(self)
        if cursor == -1:
            while len(copy.actions):
                copy.remove_last_action()
            return copy
        while len(copy.editable_actions()) > cursor:
            copy.remove_last_action()
        return copy

    def side_pots(self, at_street_begin=False):
        if at_street_begin:
            street = self.current_street
            i = 0
            hh = self.at_action(0)
            while hh.current_street != street:
                hh = self.at_action(i)
                i += 1
        else:
            hh = self
        side_players = [
            SidePotPlayer(p.position, p.invested_in_pot())
            for p in hh.players
            if not p.has_folded()
        ]
        dead_players = [
            SidePotPlayer(p.position, p.invested_in_pot())
            for p in hh.players
            if p.invested_in_pot() > 0 and p.has_folded()
        ]
        side_pots = []
        while side_players:
            min_ = min([p.investment for p in side_players])
            pot = Decimal(0)
            for p in side_players:
                if p.position == Position.BB and self.bb_ante:
                    p.investment -= self.bb_ante
                    pot += self.bb_ante
                p.investment -= min_
                pot += min_
            dead_amounts = []
            for p in dead_players:
                removed = min(min_, p.investment)
                dead_amounts.append(SidePotPlayer(p.position, removed, False))
                p.investment -= removed
                pot += removed
            side_pots.append(
                SidePot(
                    players=[
                        SidePotPlayer(p.position, min_, True) for p in side_players
                    ],
                    amount=pot,
                    folded=dead_amounts,
                )
            )
            dead_players = [p for p in dead_players if p.investment > 0]
            side_players = [p for p in side_players if p.investment > 0]
        if dead_players:
            log.warning("Dead chips remaining")

        return side_pots

    @classmethod
    def from_dict(cls, obj):
        hh = cls()
        for k in "ante", "big_blind", "small_blind", "n_straddle", "bb_ante":
            setattr(hh, k, obj[k])
        hh.set_stacks(obj["players"])
        hh.post_blinds_and_antes()
        for action in obj["actions"]:
            action_type = ActionType(action["type"])
            if action_type in BLINDS + [ActionType.ANTE]:
                continue
            hh.add_action(action_type, action["amount"])
        return hh

    def to_json(self):
        return json.dumps(self, cls=HHJSONEncoder)

    def to_dict(self):
        return json.loads(self.to_json(), object_hook=json_hook)

    @classmethod
    def from_json(cls, string):
        obj = json.loads(string, object_hook=json_hook)
        return cls.from_dict(obj)

    def n_pseudo_actions(self):
        # used by replayer to delay apparition of turn and river
        if self.last_action is None:
            return 0
        return Street.RIVER - self.last_action.street

    def play_length(self):
        return 2 + len(self.editable_actions()) + self.n_pseudo_actions()


@dataclass
class SidePotPlayer:
    position: Position
    investment: Decimal
    live: bool = True


@dataclass
class SidePot:
    players: List[SidePotPlayer]
    amount: Decimal
    folded: List[SidePotPlayer]

    def get_player_by_position(self, position: Position):
        for p in self.players:
            if p.position == position:
                return p

    def contributors(self):
        return self.players + self.folded


class HHJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return {"decimal": str(o)}
        if isinstance(o, HandHistory):
            return o.__dict__
        if isinstance(o, Player):
            return o.initial_stack
        if isinstance(o, Action):
            return {
                "type": o.action_type,
                "amount": o.amount,
            }
        if isinstance(o, ActionType):
            return str(o)
        if isinstance(o, Position):
            return str(o)


def json_hook(o):
    keys = o.keys()
    if len(keys) == 1 and "decimal" in keys:
        return Decimal(o["decimal"])
    return o


# def str_list(list_):
#     return "\n".join(str(el) for el in list_)


def test():
    logging.basicConfig(level=logging.DEBUG)
    hh = HandHistory(
        stacks=[Decimal(10), Decimal(50), Decimal(10), Decimal(10)],
        small_blind=Decimal("0.5"),
        big_blind=Decimal(1),
        # ante=Decimal("0.1"),
    )
    hh.post_blinds_and_antes()
    print(hh.side_pots())
    # hh.add_action(ActionType.RAISE, Decimal(49))
    # hh.add_action(ActionType.RAISE, Decimal(1))
    print(hh.possible_action_types())
    # hh.add_action(ActionType.BET, Decimal(2))
    # hh.add_action(ActionType.RAISE, Decimal(2))

    # hh = HandHistory(
    #     stacks=[
    #         Decimal(100),
    #         # Decimal(100),
    #         # Decimal(100),
    #         Decimal(100),
    #     ],
    #     small_blind=Decimal("0.5"),
    #     big_blind=Decimal(1),
    #     # n_straddle=2
    #     # ante=Decimal("0.2"),
    # )
    # hh.post_blinds_and_antes()
    # hh.add_action(ActionType.CALL)
    # hh.add_action(ActionType.BET, Decimal(1))
    # hh.set_stacks()
    # hh.post_blinds_and_antes()
    # hh.add_action(ActionType.CALL)
    # hh.add_action(ActionType.CALL)
    # hh.add_action(ActionType.CALL)
    # hh.add_action(ActionType.BET, Decimal(5))
    #
    # from pprint import pprint
    #
    # # pprint(hh.serialize())
    #
    # d = json.loads(json.dumps(hh, cls=HHJSONEncoder), object_hook=json_hook)
    # pprint(d)
    #
    # logging.basicConfig(level=logging.DEBUG)
    #
    # hh = HandHistory.from_dict(d)

    # hh.add_action(ActionType.RAISE, Decimal(99))
    # hh.add_action(ActionType.CALL)
    # hh.add_action(ActionType.CALL)

    # hh.add_action(ActionType.FOLD)
    # hh.add_action(ActionType.RAISE, Decimal(9))
    # hh.add_action(ActionType.CALL)
    # hh.add_action(ActionType.CALL)
    # hh.add_action(ActionType.CALL)
    # hh.add_action(ActionType.FOLD)

    # print(hh.possible_action_types())
    # print(hh.current_street)
    # print(hh.current_player)
    # print(hh.minimum_raise())
    # hh.add_action(ActionType.RAISE, hh.minimum_raise())
    # hh.add_action(ActionType.RAISE, hh.minimum_raise())
    # hh.add_action(ActionType.RAISE, hh.minimum_raise())
    # hh.add_action(ActionType.RAISE, hh.minimum_raise())
    # hh.add_action(ActionType.CALL)
    # hh.add_action(ActionType.CALL)
    # hh.add_action(ActionType.CALL)
    # hh.add_action(ActionType.CHECK, hh.minimum_raise())
    # hh.add_action(ActionType.BET, Decimal("5.42"))
    # hh.add_action(ActionType.FOLD)
    # hh.add_action(ActionType.CALL)
    # hh.add_action(ActionType.RAISE, hh.minimum_raise())
    # hh.add_action(ActionType.RAISE, hh.minimum_raise())
    # hh.add_action(ActionType.RAISE, hh.minimum_raise())
    # hh.add_action(ActionType.RAISE, hh.minimum_raise())
    # hh.add_action(ActionType.CALL)
    # hh.add_action(ActionType.CALL)
    # print(hh.players)


log = logging.getLogger(__name__)

if __name__ == "__main__":
    test()
