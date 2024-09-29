import logging
from decimal import Decimal
from typing import Union

from PyQt5 import QtCore, QtGui, QtWidgets

from . import config, hh
from .animations import Animations
from .card import CardItem
from .dialog import ActionWidget
from .text import NameItem, StackItem, TextItem
from .util import Image


class PlayerItemGroup(QtWidgets.QGraphicsItemGroup):
    def __init__(self, id, n_cards=4, *a, **kw):
        super().__init__(*a, **kw)

        self.card_items = []
        self._n_cards = n_cards
        for _ in range(4):
            self.card_items.append(CardItem(crop_bottom=True))

        self.bet_item = TextItem(
            hide_if_empty=True,
            content_is_number=True,
            point_size=config.config["text"].getint("player_bet_size"),
            color=config.config["text"].get("player_bet_color"),
        )
        self.action_widget = ActionWidget(self, None)
        self.stack_item = StackItem()
        self.name_item = NameItem()

        self._adjust_positions()
        self._place_cards()

        self.id = id
        self.active = True
        self.has_button = False
        self.hh_position: Union[None, hh.Position] = None

        self.addToGroup(self.bet_item)
        self.addToGroup(self.seat_item)
        self.addToGroup(self.name_item)
        self.addToGroup(self.stack_item)
        self.addToGroup(self.action_widget_item)

    def __repr__(self):
        return (
            f"<PlayerItemGroup #{self.id}: {self.name_item.content} {self.hh_position}>"
        )

    @property
    def n_cards(self):
        return self._n_cards

    @n_cards.setter
    def n_cards(self, n):
        self._n_cards = n
        self._place_cards()

    def _identify_item(self, event):
        below = self.scene().itemAt(event.scenePos(), self.scene().transform)
        log.debug(f"Below item: {below}")
        group = below.group()
        log.debug(f"Below group: {group}")
        if group in (self, self.scene()):
            log.debug(f"Passing event to {below}")
            return below
        else:
            log.debug(f"Passing event to {group}")
            return group

    def _place_cards(self):
        seat_rect = self.seat_item.boundingRect()

        cards_width = self.card_items[0].boundingRect().width() + 60 * (
            self.n_cards - 1
        )
        for i, card in enumerate(self.card_items):
            card.setPos(seat_rect.width() / 2 - cards_width / 2 + 60 * i, -91)
            card.setVisible(i < self.n_cards)

    def _adjust_positions(self):
        log.debug("Positioning player items")
        self.seat_item = Image.get("seat")
        self.seat_item.setPos(0, 0)
        seat_rect = self.seat_item.boundingRect()

        self.name_item.set_center(seat_rect.width() / 2, seat_rect.height() / 3)
        self.stack_item.set_center(seat_rect.width() / 2, seat_rect.height() * 2.2 / 3)

        self.action_widget_item = QtWidgets.QGraphicsProxyWidget()
        self.action_widget_item.setWidget(self.action_widget)
        self.action_widget_item.setFlag(self.ItemIgnoresTransformations)

        # TODO: really center widgets, need to hook to main window resize event
        w = self.action_widget.width()
        self.action_widget_item.setPos(
            (seat_rect.width() / 2) - (w / 2), seat_rect.height()
        )

        for c in self.card_items:
            self.addToGroup(c)

        self.action_widget_item.setZValue(10)

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, active):
        if active:
            self.setOpacity(1)
        else:
            self.setOpacity(0.5)
        self._active = active

    def reset(self):
        self.bet_item.content = 0
        self.name_item.content = ""
        self.hh_position = None
        self.stack_item.stack = 0
        self.action_widget_item.setVisible(False)
        self.addToGroup(self.action_widget_item)

    def hide_actions_widget(self):
        self.action_widget_item.setVisible(False)

    def animate_stack_to_bet(self, amount, street_bet_amount=0, target=None):
        if target is None:
            target = self.bet_item

        Animations.text(
            source=self.stack_item.stack_item,
            target=target,
            content=amount,
            duration=config.config["animation"].getint("stack_to_bet_duration"),
            scene=self.scene(),
            callbacks=[lambda: setattr(self.bet_item, "content", street_bet_amount)],
            target_font=True,
        )

    def sync_with_hh(self, hand_history):
        log.debug("Syncing player with HH")
        hh_player = hand_history.get_player_by_position(self.hh_position)

        # if hand_history.current_player is not None:
        street_bet = hh_player.street_bet()
        if street_bet != self.bet_item.content:
            amount = street_bet - self.bet_item.content
            if amount > 0:
                self.animate_stack_to_bet(amount, street_bet)
            else:
                self.bet_item.content = street_bet
        self.stack_item.stack = hh_player.stack

        last_hh_action = hand_history.last_action
        if last_hh_action is None:
            return

        last_player_action = hh_player.last_action
        if last_player_action is None:
            return

        if last_hh_action.player == hh_player or (
            last_player_action.action_type in hh.BLINDS
            and last_hh_action.action_type in hh.BLINDS
        ):
            self.stack_item.action = str(last_player_action.action_type)
        if last_player_action.action_type == hh.ActionType.FOLD:
            self.hide_cards()
        else:
            self.show_cards()

    def show_cards(self):
        for i, c in enumerate(self.card_items):
            c.setVisible(i < self.n_cards)

    def hide_cards(self):
        for c in self.card_items:
            c.setVisible(False)

    def show_actions_widget(self, hand_history: hh.HandHistory):
        possible = hand_history.possible_action_types()
        if hh.ActionType.RAISE in possible:
            min_raise = hand_history.minimum_raise()
            min_bet = min(
                min_raise
                + hand_history.current_player_amount_to_call()
                + hand_history.current_player_street_bet(),
                self.stack_item.stack,
            )
            log.debug(f"Min raise is {min_raise} → min pseudobet is {min_bet}")
        else:
            min_bet = hand_history.largest_blind
        max_bet = self.stack_item.stack + hand_history.current_player_street_bet()
        self.action_widget.set_min_max_step(min_bet, max_bet, hand_history.small_blind)
        self.action_widget.set_possible_actions(possible)
        self.action_widget_item.setVisible(True)

    def add_action(self, action_type, amount=Decimal(0)):
        hand_history: hh.HandHistory = self.scene().parent().hand_history
        hh_player = hand_history.get_player_by_position(self.hh_position)

        adjust = False
        if (
            action_type == hh.ActionType.BET
            and hh.ActionType.BET not in hand_history.possible_action_types()
        ):
            log.debug("Pseudo bet is in fact a raise")
            action_type = hh.ActionType.RAISE
            adjust = True
        if all(
            (
                hh_player.last_action.action_type in hh.BLINDS,
                hand_history.current_street == hh.Street.PRE_FLOP,
                action_type == hh.ActionType.BET,
            )
        ):
            log.debug("Blinds, everybody limps special case")
            adjust = True

        if adjust:
            new_amount = (
                amount
                - hand_history.current_player_amount_to_call()
                - hand_history.current_player_street_bet()
            )
            log.debug(f"Requested bet {amount}, transforming it to raise {new_amount}")
            amount = new_amount
        hand_history.add_action(action_type, amount)
        self.scene().parent().update_buttons()
        self.scene().request_action(hand_history)

    def contextMenuEvent(self, event: QtWidgets.QGraphicsSceneContextMenuEvent):
        if not self.active:
            return
        item = self._identify_item(event)
        if item is not self:
            try:
                item.contextMenuEvent(event)
            except (RuntimeError, AttributeError):
                pass

    def wheelEvent(self, event: QtWidgets.QGraphicsSceneWheelEvent):
        if not self.active:
            return
        item = self._identify_item(event)
        if item is not self:
            try:
                item.wheelEvent(event)
            except (RuntimeError, AttributeError):
                pass

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        main_window = self.scene().parent()
        if main_window.state == main_window.State.INIT:
            if event.button() == QtCore.Qt.MiddleButton:
                self.active = not self.active
                if self.has_button:
                    self.scene().reset_button()
                main_window.update_buttons()
            if event.button() == QtCore.Qt.RightButton:
                self.stack_item.mousePressEvent(event)
            elif event.button() == QtCore.Qt.LeftButton:
                self.scene().give_button(self)
                main_window.update_buttons()
            return
        if self.active:
            item = self._identify_item(event)
            if item is not self:
                try:
                    item.mousePressEvent(event)
                except (RuntimeError, AttributeError):
                    pass

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        item = self._identify_item(event)
        if item is not self:
            try:
                item.mouseReleaseEvent(event)
            except (RuntimeError, AttributeError):
                pass

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        item = self._identify_item(event)
        if item is not self:
            try:
                item.mouseMoveEvent(event)
            except (RuntimeError, AttributeError):
                pass

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        self.action_widget_item.keyPressEvent(event)

    def keyReleaseEvent(self, event: QtGui.QKeyEvent):
        self.action_widget_item.keyReleaseEvent(event)

    # def hoverEnterEvent(self, event: 'QGraphicsSceneHoverEvent'):
    #     main_window = self.scene().parent()
    #     if main_window.state == main_window.State.INIT:
    #         self.scene().give_button(self)


log = logging.getLogger(__name__)
