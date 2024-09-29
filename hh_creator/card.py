import itertools
import logging
from dataclasses import dataclass
from functools import total_ordering
from pathlib import Path
from typing import List, Union, TYPE_CHECKING

from deuces import Card as DeucesCard
from deuces import Evaluator
from poker.constants import PokerEnum
from PyQt5 import Qt, QtCore, QtWidgets

from . import config
from .util import Image

if TYPE_CHECKING:
    from .player import PlayerItemGroup


class Suit(PokerEnum):
    CLUBS = "♣", "c", "clubs", "Trefle"
    DIAMONDS = "♦", "d", "diamonds", "Carreau"
    HEARTS = "♥", "h", "hearts", "Coeur"
    SPADES = "♠", "s", "spades", "Pique"

    def one_letter_format(self):
        return str(self._value_[1])


class Rank(PokerEnum):
    DEUCE = "2", 2
    THREE = "3", 3
    FOUR = "4", 4
    FIVE = "5", 5
    SIX = "6", 6
    SEVEN = "7", 7
    EIGHT = "8", 8
    NINE = "9", 9
    TEN = "T", 10
    JACK = "J", 11
    QUEEN = "Q", 12
    KING = "K", 13
    ACE = "A", 14

    @classmethod
    def difference(cls, first, second):
        """Tells the numerical difference between two ranks."""

        # so we always get a Rank instance even if string were passed in
        first, second = cls(first), cls(second)
        rank_list = list(cls)
        return abs(rank_list.index(first) - rank_list.index(second))

    def next(self):
        return Rank(self._value_[1] + 1)

    def prev(self):
        return Rank(self._value_[1] - 1)

    def one_letter_format(self):
        return str(self._value_[0])


class CardLook(QtWidgets.QGraphicsItemGroup):
    instances = []

    def __init__(
        self,
        scale_factor=config.config["look"].getfloat("player_card_scale"),
        crop_bottom=False,
        *a,
        **kw,
    ):
        root = Path("cards_cut") if crop_bottom else Path("cards")
        super().__init__(*a, **kw)
        self.scale_factor = scale_factor
        self.faces = {
            (rank, suit): Image.get(
                root / f"{rank.one_letter_format()}{suit.one_letter_format()}"
            )
            for rank in Rank
            for suit in Suit
        }
        for k in self.faces.values():
            self.addToGroup(k)
            k.setVisible(False)
            k.setScale(scale_factor)
        self.back = Image.get(root / "back-red")
        self.back.setScale(scale_factor)
        self.scale_factor = scale_factor
        self.addToGroup(self.back)
        self.instances.append(self)

    def _update_look(self):
        if self._rank is None or self._suit is None:
            self.back.setVisible(True)
            return
        self.back.setVisible(False)
        for (rank, suit), item in self.faces.items():
            item.setVisible((rank, suit) == (self._rank, self._suit))

    def boundingRect(self):
        rect_f = super().boundingRect()
        scaled = Qt.QRectF(*(x * self.scale_factor for x in rect_f.getCoords()))
        return scaled

    @classmethod
    def change_back(cls, color):
        config.config["look"]["card-back"] = color
        config.save_config()
        for i in cls.instances:
            visible = i.back.isVisible()
            i.back.deleteLater()
            pos = i.back.scenePos()
            i.back = Image.get(Path("cards") / f"back-{color}")
            i.back.setScale(i.scale_factor)
            i.back.setPos(pos)
            i.back.setVisible(visible)
            i.addToGroup(i.back)

    def hide_face(self):
        self.back.setVisible(True)

    def discover(self):
        if self._rank is not None and self._suit is not None:
            self.back.setVisible(False)


class CardItem(CardLook):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._suit: Union[Suit, None] = None
        self._rank: Union[Rank, None] = None
        self._update_look()

    @property
    def suit(self):
        return self._suit

    @suit.setter
    def suit(self, suit):
        self._suit = suit
        self._update_look()

    @property
    def rank(self):
        return self._rank

    @rank.setter
    def rank(self, rank):
        self._rank = rank
        self._update_look()

    def wheelEvent(self, event: QtWidgets.QGraphicsSceneWheelEvent):
        log.debug("Wheel on card")
        mw = self.scene().parent()
        if mw.state != mw.State.ACTIONS:
            return
        if self.rank is not None:
            attr = "next" if event.delta() > 0 else "prev"
            try:
                self.rank = getattr(self.rank, attr)()
            except ValueError:
                pass

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        mw = self.scene().parent()
        if mw.state != mw.State.ACTIONS:
            return
        if event.button() != QtCore.Qt.LeftButton:
            return
        log.debug("Left click on card")
        if self.rank is None:
            self.rank = Rank.DEUCE
        if self.suit is None:
            self.suit = Suit.CLUBS
        elif self.suit is Suit.CLUBS:
            self.suit = Suit.DIAMONDS
        elif self.suit is Suit.DIAMONDS:
            self.suit = Suit.HEARTS
        elif self.suit is Suit.HEARTS:
            self.suit = Suit.SPADES
        else:
            self.suit = None

    def contextMenuEvent(self, event: QtWidgets.QGraphicsSceneContextMenuEvent):
        mw = self.scene().parent()
        if mw.state != mw.State.ACTIONS:
            return
        menu = QtWidgets.QMenu()
        if self.suit is not None and self.rank is not None:
            action = QtWidgets.QAction("Inconnue")
            action.triggered.connect(lambda: setattr(self, "suit", None))
            actions = [action]
        else:
            actions = []
        for suit in Suit:
            action = QtWidgets.QAction(str(suit))
            action.triggered.connect(lambda e, s=suit: setattr(self, "suit", s))
            actions.append(action)

        for rank in Rank:
            action = QtWidgets.QAction(str(rank))
            action.triggered.connect(lambda e, r=rank: setattr(self, "rank", r))
            actions.append(action)

        menu.addActions(actions)
        menu.exec(event.screenPos())

    def deuces_format(self):
        try:
            return f"{self.rank.one_letter_format()}{self.suit.one_letter_format()}"
        except AttributeError:
            return "xx"

    def to_deuces(self):
        return DeucesCard.new(self.deuces_format())

    @classmethod
    def reset(cls):
        for c in cls.instances:
            c.rank = None
            c.suit = None


@total_ordering
@dataclass
class Hand:
    cards: List[CardItem]
    board: List[CardItem]

    def __gt__(self, other: "Hand"):
        return self.deuces_score() < other.deuces_score()

    def __eq__(self, other: "Hand"):
        return self.deuces_score() == other.deuces_score()

    def deuces_score(self):
        return evaluator.evaluate(
            [c.to_deuces() for c in self.cards], [c.to_deuces() for c in self.board]
        )


def get_winners(player_items: List["PlayerItemGroup"], board: List["CardItem"]):
    scores = []
    for player in player_items:
        if player.n_cards == 2:
            scores.append(Hand(cards=player.card_items[:2], board=board).deuces_score())
        else:
            all_scores = []
            for c1, c2 in itertools.combinations(player.card_items, 2):
                for b1, b2, b3 in itertools.combinations(board, 3):
                    all_scores.append(
                        Hand(cards=[c1, c2, b1, b2, b3], board=[]).deuces_score()
                    )
            scores.append(min(all_scores))

    min_ = min(scores)
    winners = [p for p, s in zip(player_items, scores) if s == min_]
    return winners


evaluator = Evaluator()


log = logging.getLogger(__name__)
