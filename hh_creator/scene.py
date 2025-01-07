import logging
from decimal import Decimal
from pathlib import Path

from PyQt5 import Qt, QtGui, QtWidgets

from . import config, hh
from .animations import Animations
from .card import CardItem, Rank, Suit, get_winners
from .player import PlayerItemGroup
from .text import TextItem
from .util import Image, get_center, sounds


class TableScene(QtWidgets.QGraphicsScene):
    def __init__(self, parent):
        super().__init__(parent)
        self._create_background()
        self._create_button()
        self._create_board()
        self._create_text_items()

        self.player_items = [PlayerItemGroup(id=i) for i in range(10)]

        self.transform = QtGui.QTransform()
        self.board_street = hh.Street.ANTE

        self.hero_idx = 0

        self._currency = ""
        self._currency_is_after = True

        self._get_highlight_effect()
        self._n_seats = None

        self.hide_board()

    def _create_text_items(self):
        self.central_pot_item = TextItem(
            prefix=config.config["text"].get("main_pot_prefix") + " ",
            content_is_number=True,
            hide_if_empty=True,
        )
        self.total_pot_item = TextItem(
            prefix=config.config["text"].get("total_pot_prefix") + " ",
            content_is_number=True,
            hide_if_empty=True,
            point_size=config.config["text"].getint("total_pot_font_size"),
        )
        self.pot_odds = TextItem(
            prefix=config.config["text"].get("odds_prefix") + " ",
            postfix=config.config["text"].get("odds_postfix"),
            point_size=config.config["text"].getint("odds_font_size"),
            content_is_number=True,
            hide_if_empty=True,
        )
        self.pot_odds.n_decimals = 2
        self.addItem(self.pot_odds)
        self.addItem(self.total_pot_item)
        self.addItem(self.central_pot_item)

        self.pot_odds.setPos(
            config.config["position"].getfloat("pot_odds_x"),
            config.config["position"].getfloat("pot_odds_y"),
        )
        self.central_pot_item.set_center(
            self.sceneRect().center().x(),
            config.config["position"].getfloat("central_pot_y"),
        )
        self.total_pot_item.set_center(
            self.sceneRect().center().x(),
            config.config["position"].getfloat("total_pot_y"),
        )

        self.side_pot_items = [TextItem(content_is_number=True) for _ in range(9)]
        for i, item in enumerate(self.side_pot_items, start=1):
            x = config.config["position"].getfloat(f"side_pot{i}_x", 0)
            y = config.config["position"].getfloat(f"side_pot{i}_y", 0)
            item.setPos(x, y)
            self.addItem(item)

        self.text_items = [
            self.pot_odds,
            self.total_pot_item,
            self.central_pot_item,
        ] + self.side_pot_items

    def _create_button(self):
        self.button_item = Image.get(Path("chips") / "dealer")
        self.button_item.setVisible(False)
        self.button_item.setScale(config.config["look"].getfloat("button_scale"))
        self.addItem(self.button_item)

    def _create_board(self):
        self.board = [
            CardItem(scale_factor=config.config["look"].getfloat("board_scale"))
            for _ in range(5)
        ]
        board = self.board
        board[0].setPos(
            config.config["position"].getfloat("board_x"),
            config.config["position"].getfloat("board_y"),
        )
        self.addItem(board[0])
        for card, prev_card in zip(board[1:], board):
            card.setPos(
                prev_card.pos().x()
                + prev_card.boundingRect().width()
                + config.config["position"].getfloat("board_spacing"),
                prev_card.pos().y(),
            )
            self.addItem(card)

    def _update_currency(self):
        items = [self.central_pot_item, self.total_pot_item] + self.side_pot_items
        items.extend(p.stack_item.stack_item for p in self.player_items)
        items.extend(p.bet_item for p in self.player_items)
        for i in items:
            setattr(i, "content", getattr(i, "content"))
            setattr(i, "currency", self._currency)
            setattr(i, "currency_is_after", self._currency_is_after)

    def _get_highlight_effect(self):
        highlight_effect = QtWidgets.QGraphicsDropShadowEffect()
        highlight_effect.setColor(QtGui.QColor("white"))
        highlight_effect.setOffset(0)
        highlight_effect.setBlurRadius(200)

        self.highlight_effect = highlight_effect

    def _get_player_item_from_hh_position(self, position: hh.Position):
        for p in self.active_players():
            if p.hh_position == position:
                return p
        else:
            raise ValueError(f"{position} not found in {self.player_items}")

    def _create_background(self):
        table_item = Image.get(Path("table") / config.config["look"].get("table"))
        background = Image.get(Path("background") / config.config["look"].get("webcam"))

        shadow = QtWidgets.QGraphicsDropShadowEffect()
        shadow.setBlurRadius(config.config["look"].getfloat("TABLE_SHADOW_RADIUS"))
        table_item.setGraphicsEffect(shadow)
        table_rectf = Qt.QRectF(table_item.boundingRect())

        self.background_item = background
        self.background_item.setZValue(-100)
        self.table_shadow = shadow
        self.table_item = table_item

        self.setSceneRect(table_rectf)
        self.addItem(background)
        self.addItem(table_item)

    def _place_players(self):
        self.reset_button()
        self._clear_text()
        self.board_street = hh.Street.ANTE
        log.debug("Placing players")
        self.button_position = []
        conf = config.config[f"{self.n_seats}players"]
        center_pos = get_center(self.table_item)
        center_pos[1] += 100

        for i, player in enumerate(self.player_items, start=1):
            player.reset()

            x = conf.getfloat(f"position{i}_x")
            y = conf.getfloat(f"position{i}_y")

            if x is None:
                player.active = False
                player.setVisible(False)
                if player.scene() is self:
                    self.removeItem(player)
                continue

            player.setVisible(True)
            player.setPos(x, y)

            if player.scene() is not self:
                self.addItem(player)

            player.active = True

            bet_x_hc = conf.getfloat(f"bet{i}_x")
            bet_y_hc = conf.getfloat(f"bet{i}_y")
            button_x_hc = conf.getfloat(f"button{i}_x")
            button_y_hc = conf.getfloat(f"button{i}_y")

            player_pos = get_center(player.seat_item, scene=True)
            diff = center_pos[0] - player_pos[0], center_pos[1] - player_pos[1]
            ratio = abs(diff[0] / diff[1])

            # FIXME: this heuristic is bad, but will do until we hardcode
            #        all button and bet positions
            if ratio > 1.5:
                bet_y = player_pos[1]
                bet_y = min(bet_y, 700)
                bet_y = max(bet_y, 320)
                button_y = bet_y + 50
                if diff[0] < 0:  # right
                    log.info(f"Player {i}: right")
                    button_x = player_pos[0] - 150
                    bet_x = player_pos[0] - 200
                else:  # left
                    log.info(f"Player {i}: left")
                    button_x = player_pos[0] + 130
                    bet_x = player_pos[0] + 200
            else:
                bet_x = player_pos[0]
                button_x = bet_x + 100
                if diff[1] < 0:  # below
                    log.info(f"Player {i}: down")
                    bet_y = player_pos[1] - 180
                else:  # top
                    log.info(f"Player {i}: up")
                    bet_y = player_pos[1] + 80
                button_y = bet_y

            player.bet_item.set_center(
                bet_x if bet_x_hc is None else bet_x_hc,
                bet_y if bet_y_hc is None else bet_y_hc,
                scene=True,
            )
            player.removeFromGroup(player.action_widget_item)

            self.button_position.append(
                [
                    button_x if button_x_hc is None else button_x_hc,
                    button_y if button_y_hc is None else button_y_hc,
                ]
            )

    def _clear_text(self):
        for i in self.text_items:
            if i.content_is_number:
                i.content = 0
            else:
                i.content = ""

    def mouseDoubleClickEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        # TODO: replace this with full screen
        print(event.scenePos())
        pass

    @property
    def currency(self):
        return self._currency

    @currency.setter
    def currency(self, currency):
        self._currency = currency
        self._update_currency()

    @property
    def currency_is_after(self):
        return self._currency_is_after

    @currency_is_after.setter
    def currency_is_after(self, val):
        self._currency_is_after = val
        self._update_currency()

    @property
    def n_active_players(self):
        return sum(p.active for p in self.player_items)

    @property
    def button_is_given(self):
        return self.button_item.isVisible()

    @property
    def n_seats(self):
        return self._n_seats

    @n_seats.setter
    def n_seats(self, value):
        self._n_seats = value
        self._place_players()
        self.hide_board()
        CardItem.reset()

    def set_all_stacks(self, value):
        for p in self.player_items:
            p.stack_item.stack = value

    def set_n_cards(self, value):
        for p in self.player_items:
            p.n_cards = value

    def change_table(self, color):
        config.config["look"]["table"] = color
        self.removeItem(self.table_item)
        self.table_item.deleteLater()
        self.table_item = Image.get(Path("table") / color)
        self.table_item.setGraphicsEffect(self.table_shadow)
        self.table_item.setZValue(-50)
        self.addItem(self.table_item)

    def change_background(self, name):
        config.config["look"]["webcam"] = name
        self.background_item.setPixmap(Image.get(Path("background") / name).pixmap())

    def load_dict(self, hh_dict, hand_history):
        self._clear_text()

        self.hero_idx = hh_dict["hero"]

        self.n_seats = hh_dict["n_seats"]
        for i, player in enumerate(self.player_items):
            player.active = i in hh_dict["active_seats"]

        self.set_n_cards(hh_dict["n_cards"])

        self.give_button(self.player_items[hh_dict["button_idx"]])

        for player, hand, name, hhp in zip(
            self.get_active_players_after_button(),
            hh_dict["hands"],
            hh_dict["player_names"],
            hand_history.players,
        ):
            player.hh_position = hhp.position
            player.name_item.content = name
            for rank_suit, card in zip(hand, player.card_items):
                if rank_suit == "xx":
                    continue
                card.rank = Rank(rank_suit[0])
                card.suit = Suit(rank_suit[1])

        self._currency = hh_dict["currency"]
        self._currency_is_after = hh_dict["currency_is_after"]
        self.hide_inactive_players()
        self._update_currency()

        for card, value in zip(self.board, hh_dict["board"]):
            if value == "xx":
                card.rank = None
                card.suit = None
                continue
            card.rank = Rank(value[0])
            card.suit = Suit(value[1])

    def button_idx(self):
        for i, p in enumerate(self.player_items):
            if p.has_button:
                return i

    def active_seats_idx(self):
        return [i for i, p in enumerate(self.player_items) if p.active]

    def get_active_players_after_button(self):
        players = list(self.active_players())
        for i, p in enumerate(players):
            if p.has_button:
                break
        else:
            raise TypeError
        i += 1
        players = players[i:] + players[:i]
        players = [p for p in players if p.active]
        if len(players) == 2:
            players = players[::-1]
        return players

    def show_all_players(self):
        for i, p in enumerate(self.player_items):
            p.setVisible(i < self.n_seats)

    def hide_inactive_players(self):
        for p in self.player_items:
            if not p.active:
                p.setVisible(False)

    def reset_button(self):
        for p in self.player_items:
            p.has_button = False
        self.button_item.setVisible(False)

    def give_button(self, player):
        self.reset_button()
        player.has_button = True
        i = self.player_items.index(player)
        self.button_item.setVisible(True)
        pos = self.button_position[i]
        log.debug(f"Showing button at {pos} for player {i}")
        self.button_item.setPos(*pos)
        self.parent().update_buttons()

    def bets_to_pot_animations(self, hand_history, add_last_call=True):
        log.info("Animating bets to pot")
        last_action = hand_history.last_action
        if add_last_call and last_action.action_type == hh.ActionType.CALL:
            p = self._get_player_item_from_hh_position(last_action.player.position)
            p.animate_stack_to_bet(last_action.amount, 0, target=self.central_pot_item)
            p.bet_item.content = last_action.amount

        side_pots = hand_history.side_pots()

        for side_pot, pot_item in zip(
            side_pots, [self.central_pot_item] + self.side_pot_items
        ):
            for side_pot_player in side_pot.contributors():
                player_item = self._get_player_item_from_hh_position(
                    side_pot_player.position
                )

                bet_item = player_item.bet_item
                Animations.text(
                    source=bet_item,
                    target=pot_item,
                    duration=config.config["animation"].getint(
                        "BETS_TO_POT_ANIMATION_DURATION"
                    ),
                    scene=self,
                )

            pot_item.content = side_pot.amount

    def animate_pot_to_winner(
        self,
        position: hh.Position,
        pot_item=None,
        split=1,
    ):
        player_item = self._get_player_item_from_hh_position(position)

        if pot_item is None:
            items = [self.central_pot_item]
            items.extend(
                p.bet_item for p in self.active_players() if p.bet_item.isVisible()
            )
        else:
            items = [pot_item]

        total = 0
        for item in items:
            amount = Decimal(item.content) / split
            log.debug(f"Animating {amount} to {position}")

            Animations.text(
                source=item,
                content=amount,
                target=player_item.stack_item.stack_item,
                duration=config.config["animation"].getint("POT_TO_WINNER_DURATION"),
                scene=self,
                callbacks=[],
            )

            total += amount

        Animations.add_callback(
            lambda: setattr(
                player_item.stack_item,
                "stack",
                total + getattr(player_item.stack_item, "stack"),
            )
        )

        # print(amount)

    def ante_animations(self, hand_history: hh.HandHistory):
        for i, p in enumerate(self.active_players()):
            Animations.text(
                source=p.stack_item.stack_item,
                content=hand_history.ante,
                duration=config.config["animation"].getint(
                    "BETS_TO_POT_ANIMATION_DURATION"
                ),
                target=self.total_pot_item,
                scene=self,
            )

    def bb_ante_animation(self, hand_history: hh.HandHistory):
        Animations.text(
            source=self.bb_player().stack_item.stack_item,
            content=hand_history.bb_ante,
            duration=config.config["animation"].getint(
                "BETS_TO_POT_ANIMATION_DURATION"
            ),
            target=self.total_pot_item,
            scene=self,
        )

    def clear_side_pots(self):
        for pot_item in [self.central_pot_item] + self.side_pot_items:
            pot_item.content = 0

    def show_down(self, hand_history):
        for side_pot, side_pot_item in zip(
            hand_history.side_pots(), [self.central_pot_item] + self.side_pot_items
        ):
            player_items = []
            for side_pot_player in side_pot.players:
                player_items.append(
                    self._get_player_item_from_hh_position(side_pot_player.position)
                )

            try:
                winners = get_winners(player_items, self.board)
            except (AttributeError, KeyError) as e:
                log.warning(f"Showdown impossible {e}")
                continue
            for w in winners:
                self.animate_pot_to_winner(
                    w.hh_position, side_pot_item, split=len(winners)
                )

    def clear_bet_items(self):
        for p in self.player_items:
            p.bet_item.content = 0

    def update_winners(self, hand_history):
        Animations.reset()
        self.show_known_hands()
        if hand_history.winner is None:
            self.show_down(hand_history)
        else:
            # p = self._get_player_item_from_hh_position(hand_history.winner.position)
            self.animate_pot_to_winner(hand_history.winner.position)
            self.clear_bet_items()
        self._clear_text()
        Animations.start()

    def update_total_pot(self, hand_history):
        central_pot = hand_history.central_pot
        total_pot = hand_history.total_pot

        if central_pot != total_pot:
            self.total_pot_item.content = total_pot
        else:
            self.total_pot_item.content = 0

    def sync_with_hh(self, hand_history, rebuild_pots=False, update_board=True):
        log.debug("Syncing table with HH")

        Animations.reset()

        if self.parent().hide_cards_before_showdown():
            self.hide_hands()
        else:
            self.show_known_hands()

        self.update_total_pot(hand_history)

        total_pot = hand_history.total_pot

        if hand_history.current_player is not None:
            to_call = hand_history.current_player_amount_to_call()

            if to_call != 0:
                try:
                    diff = min(
                        abs(
                            hand_history.current_player.initial_stack
                            - hand_history.actions[-1].player.initial_stack
                        ),
                        0,
                    )
                except IndexError:
                    self.pot_odds.content = 0
                else:
                    pseudo_total = total_pot - diff

                    self.pot_odds.content = pseudo_total / to_call
            else:
                self.pot_odds.content = 0
        else:
            self.pot_odds.content = 0

        next_street = self.board_street < hand_history.current_street
        if self.board_street == hh.Street.ANTE and hand_history.ante:
            self.ante_animations(hand_history)
        elif self.board_street == hh.Street.ANTE and getattr(
            hand_history, "bb_ante", None
        ):
            self.bb_ante_animation(hand_history)
        elif next_street and self.board_street != hh.Street.ANTE:
            self.bets_to_pot_animations(hand_history)

        for p in self.active_players():
            p.sync_with_hh(hand_history)

        if hand_history.current_player is not None:
            player_item = self._get_player_item_from_hh_position(
                hand_history.current_player.position
            )
            try:
                player_item.setGraphicsEffect(self.highlight_effect)
            except RuntimeError:
                self._get_highlight_effect()
                player_item.setGraphicsEffect(self.highlight_effect)
        else:
            for p in self.active_players():
                p.setGraphicsEffect(None)

        street_back = self.board_street > hand_history.current_street
        if street_back or rebuild_pots:
            if hand_history.current_street == hh.Street.PRE_FLOP:
                for side_pot_item in [self.central_pot_item] + self.side_pot_items:
                    side_pot_item.content = 0
                if hand_history.ante:
                    self.central_pot_item.content = hand_history.central_pot
            else:
                side_pots = hand_history.side_pots(at_street_begin=True)
                for i, side_pot_item in enumerate(
                    [self.central_pot_item] + self.side_pot_items
                ):
                    try:
                        val = side_pots[i].amount
                    except IndexError:
                        val = 0
                    side_pot_item.content = val

        self.board_street = hand_history.current_street

        last_action = hand_history.last_action

        try:
            if next_street and last_action.action_type == hh.ActionType.CALL:
                sounds["call_closing"].play()
            else:
                sounds[last_action.action_type].play()
        except KeyError:
            log.debug(f"No sound for action {last_action.action_type}")
        except AttributeError:
            log.debug("No action, no sound")

        if update_board:
            if hand_history.current_street in (hh.Street.SHOWDOWN, hh.Street.RIVER):
                self.show_river()
            elif hand_history.current_street == hh.Street.FLOP:
                self.show_flop()
            elif hand_history.current_street == hh.Street.TURN:
                self.show_turn()
            elif hand_history.current_street == hh.Street.PRE_FLOP:
                self.hide_board()

        Animations.start()

    def show_known_hands(self):
        for p in self.active_players():
            for c in p.card_items:
                c.discover()

    def hide_hands(self, hide_hero=False):
        for i, p in enumerate(self.active_players()):
            if not hide_hero and i == self.hero_idx:
                continue
            for c in p.card_items:
                c.hide_face()

    def hide_board(self):
        for c in self.board:
            c.setVisible(False)

    def show_flop(self):
        for c in self.board[:3]:
            c.setVisible(True)
        for c in self.board[3:]:
            c.setVisible(False)

    def show_turn(self):
        for c in self.board[:4]:
            c.setVisible(True)
        self.board[4].setVisible(False)

    def show_river(self):
        for c in self.board:
            c.setVisible(True)

    def active_players(self):
        for p in self.player_items:
            if not p.active:
                continue
            yield p

    def bb_player(self):
        for p in self.player_items:
            if p.hh_position == hh.Position.BB:
                return p

    def reset_bet_items(self):
        for p in self.active_players():
            p.bet_item.content = 0

    def hide_all_actions_widget(self):
        for p in self.player_items:
            p.hide_actions_widget()

    def request_action(self, hand_history: hh.HandHistory):
        self.sync_with_hh(hand_history)
        self.hide_all_actions_widget()
        next_hh_player = hand_history.current_player
        if next_hh_player is None:
            return
        next_player_item = self._get_player_item_from_hh_position(
            next_hh_player.position
        )
        next_player_item.show_actions_widget(hand_history)

    def init_hh(self, hand_history: hh.HandHistory):
        players = self.get_active_players_after_button()
        hand_history.set_stacks([p.stack_item.stack for p in players])
        for p, hhp in zip(players, hand_history.players):
            log.debug(f"{hhp.position}: {p}")
            p.hh_position = hhp.position
            p.name_item.content = hhp.position
        hand_history.post_blinds_and_antes()
        self.sync_with_hh(hand_history)
        self.request_action(hand_history)
        self.hide_inactive_players()

    def show_all_active_players_cards(self):
        for p in self.active_players():
            p.show_cards()


log = logging.getLogger(__name__)
