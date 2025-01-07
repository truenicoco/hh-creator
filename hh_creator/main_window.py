import json
import logging
from pathlib import Path
from typing import Union

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSlot

from . import config
from .animations import Animations
from .card import CardLook
from .dialog import NewHandDialog
from .hh import HandHistory, HHJSONEncoder, Street, json_hook
from .scene import TableScene
from .text import TextItem
from .util import AutoUI, IncrementableEnum, sounds


class KeyboardShortcutsMixin:
    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()
        elif event.key() in (QtCore.Qt.Key_Right, QtCore.Qt.Key_Space):
            if self.main_window.widgets["pushButtonNext"].isEnabled():
                self.main_window.on_pushButtonNext_clicked()
        elif event.key() in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Backspace):
            if self.main_window.widgets["pushButtonBack"].isEnabled():
                self.main_window.on_pushButtonBack_clicked()
        elif event.key() == QtCore.Qt.Key_Home:
            if self.main_window.widgets["pushButtonStart"].isEnabled():
                self.main_window.on_pushButtonStart_clicked()


class MainWindow(QtWidgets.QMainWindow, AutoUI):
    class State(IncrementableEnum):
        LAUNCH = 0
        INIT = 1
        ACTIONS = 2
        REPLAY = 3
        WAIT_FOR_FLOP = 10
        WAIT_FOR_TURN = 11
        WAIT_FOR_RIVER = 12

    STATUS_MESSAGES = {
        State.LAUNCH: "",
        State.INIT: "Clic gauche: choisir bouton, "
        "clic droit: modifier stack, "
        "clic molette: (dés)activer un joueur",
        State.ACTIONS: "Clic gauche sur un nom pour le modifier",
        State.REPLAY: "Mode replay",
        State.WAIT_FOR_FLOP: "Suivant = afficher flop",
        State.WAIT_FOR_TURN: "Suivant = afficher turn",
        State.WAIT_FOR_RIVER: "Suivant = afficher river",
    }

    def __init__(self):
        super().__init__()

        self.full_screen_widget = None

        self.graphics_view: QtWidgets.QGraphicsView = self.widgets["graphicsView"]

        self.hand_history: Union[None, HandHistory] = None
        self.hh_settings = {}

        if config.config["behavior"].getboolean("replay_start_with_blinds_posted"):
            self.replay_action_cursor = 1
        else:
            self.replay_action_cursor = 0

        self.actionOpenGL.setChecked(config.config["animation"].getboolean("opengl"))

        self._make_table_scene()
        self.show()
        if config.geometry is not None:
            self.restoreGeometry(config.geometry)
        if config.state is not None:
            self.restoreState(config.state)
        self._fit_scene()
        self.state = self.State.LAUNCH

        self.current_filename = None
        self.on_actionNew_triggered()

    def _make_table_scene(self):
        table_scene = TableScene(self)
        self.scene = table_scene
        if self.actionOpenGL.isChecked():
            self.graphics_view.setViewport(QtWidgets.QOpenGLWidget())
        self.graphics_view.setScene(table_scene)

    def _initialize_hh(self):
        player_items = self.scene.get_active_players_after_button()
        stacks = [p.stack_item.stack for p in player_items]
        hand_history = HandHistory(
            small_blind=self.hh_settings["sb"],
            ante=self.hh_settings["ante"],
            big_blind=self.hh_settings["bb"],
            bb_ante=self.hh_settings["bb_ante"],
            stacks=stacks,
        )

        for item, hh_player in zip(player_items, hand_history.players):
            item.hh_player = hh_player
            item.name_item.content = str(hh_player.position)

        self.hand_history = hand_history
        self.scene.sync_with_hh(self.hand_history)
        self.scene.request_action(self.hand_history)

    def _fit_scene(self):
        g = self.graphics_view
        g.fitInView(self.scene.sceneRect(), QtCore.Qt.KeepAspectRatio)
        self.scene.transform = g.transform()

    def resizeEvent(self, event: QtGui.QResizeEvent):
        self._fit_scene()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        config.save_config(self.saveGeometry(), self.saveState())
        super().closeEvent(event)

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, v):
        self._state = v
        self.statusBar().showMessage(self.STATUS_MESSAGES[v])

    @pyqtSlot()
    def on_actionNew_triggered(self):
        dialog = NewHandDialog(parent=self)
        code = dialog.exec()
        if code:
            dialog.get_field_value("SB")
            dialog.get_field_value("Ante")
            n_digits = dialog.get_field_value("Decimals")

            log.debug(f"Will use {n_digits} digits for display rounding")
            TextItem.n_decimals = n_digits

            self.hand_history = HandHistory(
                small_blind=dialog.get_field_value("SB"),
                big_blind=dialog.get_field_value("BB"),
                ante=dialog.get_field_value("Ante"),
                bb_ante=dialog.get_field_value("BBAnte"),
                n_straddle=dialog.get_field_value("Straddle"),
            )

            self.scene.n_seats = dialog.get_field_value("Players")

            self.scene.set_all_stacks(
                config.config["new_hand"].getint("default_stack_in_bb")
                * dialog.get_field_value("BB")
            )

            self.scene.set_n_cards(dialog.get_n_cards())
            self.scene.currency = dialog.get_field_value("Currency")
            pos = dialog.get_field_value("CurrencyPosition")
            self.scene.currency_is_after = pos == "après"
            self.state = self.State.INIT
            self.current_filename = None
            self.findChild(QtWidgets.QAction, "actionSave").setEnabled(False)

            conf = dialog.conf
            for name, field in dialog.FIELDS.items():
                conf[name] = config.escape_dollar(dialog.get_field_value(name))
                if field.checkable:
                    conf[f"{name}_checked"] = str(
                        dialog._get_checkbox(name).isChecked()
                    )
            config.save_config()
            self.widgets["checkBoxEditMode"].setChecked(True)
            self.replay_action_cursor = 0
            self.graphics_view.setInteractive(True)
        elif dialog.open_instead:
            self.on_actionOpen_triggered()
        self.update_buttons()

    @pyqtSlot()
    def on_pushButtonNext_clicked(self):
        if self.state == self.State.INIT:
            self.scene.init_hh(self.hand_history)
            self.state = self.state.next()
        elif self.state == self.State.REPLAY:
            self.replay_action_cursor += 1
            if self.replay_action_cursor > len(self.hand_history.editable_actions()):
                if (
                    self.replay_action_cursor
                    == len(self.hand_history.editable_actions()) + 1
                ):
                    Animations.reset()
                    self.scene.bets_to_pot_animations(
                        self.hand_history, add_last_call=False
                    )
                    self.scene.clear_bet_items()
                    self.scene.update_total_pot(self.hand_history)
                    Animations.start()
                play_len = self.hand_history.play_length() - (
                    Street.RIVER - self.hand_history.last_action.street
                )
                if self.replay_action_cursor == play_len - 4:
                    sounds["street"].play()
                    self.scene.show_flop()
                elif self.replay_action_cursor == play_len - 3:
                    self.scene.show_turn()
                    sounds["street"].play()
                elif self.replay_action_cursor == play_len - 2:
                    self.scene.show_river()
                    sounds["street"].play()
                elif self.replay_action_cursor == play_len - 1:
                    self.scene.show_known_hands()
                else:
                    self.scene.update_winners(self.hand_history)
            else:
                hand_history = self.hand_history.at_action(self.replay_action_cursor)
                self.scene.sync_with_hh(hand_history, update_board=False)
                cur_street = hand_history.current_street
                prev_street = hand_history.at_action(
                    self.replay_action_cursor - 1
                ).current_street
                if cur_street == Street.FLOP and prev_street == Street.PRE_FLOP:
                    self.state = self.State.WAIT_FOR_FLOP
                elif cur_street == Street.TURN and prev_street == Street.FLOP:
                    self.state = self.State.WAIT_FOR_TURN
                elif cur_street == Street.RIVER and prev_street == Street.TURN:
                    self.state = self.State.WAIT_FOR_RIVER
        elif self.state == self.State.WAIT_FOR_FLOP:
            self.scene.show_flop()
            sounds["street"].play()
            self.state = self.state.REPLAY
        elif self.state == self.State.WAIT_FOR_TURN:
            self.scene.show_turn()
            sounds["street"].play()
            self.state = self.state.REPLAY
        elif self.state == self.State.WAIT_FOR_RIVER:
            self.scene.show_river()
            sounds["street"].play()
            self.state = self.state.REPLAY
        self.update_buttons()

    @pyqtSlot()
    def on_pushButtonBack_clicked(self):
        if self.state == self.State.ACTIONS:
            self.hand_history.remove_last_action()
            self.scene.request_action(self.hand_history)
        elif self.state in (
            self.State.REPLAY,
            self.State.WAIT_FOR_FLOP,
            self.State.WAIT_FOR_TURN,
            self.State.WAIT_FOR_RIVER,
        ):
            self.replay_action_cursor -= 1
            self.state = self.State.REPLAY
            if self.replay_action_cursor > len(self.hand_history.editable_actions()):
                play_len = self.hand_history.play_length()
                if self.replay_action_cursor == play_len - 4:
                    self.scene.hide_board()
                elif self.replay_action_cursor == play_len - 3:
                    self.scene.show_flop()
                elif self.replay_action_cursor == play_len - 2:
                    self.scene.show_turn()
                elif self.replay_action_cursor == play_len - 1:
                    self.scene.hide_hands()
                    self.scene.sync_with_hh(self.hand_history, rebuild_pots=True)
            else:
                hand_history = self.hand_history.at_action(self.replay_action_cursor)
                pseudo_actions_remaining = self.replay_action_cursor != len(
                    self.hand_history.editable_actions()
                )
                self.scene.sync_with_hh(
                    hand_history,
                    rebuild_pots=pseudo_actions_remaining,
                    update_board=pseudo_actions_remaining,
                )

        self.update_buttons()

    @pyqtSlot()
    def on_pushButtonStart_clicked(self):
        self.replay_action_cursor = -1
        hand_history = self.hand_history.at_action(self.replay_action_cursor)
        self.checkBoxEditMode.setChecked(False)
        self.scene.sync_with_hh(hand_history)
        self.scene.hide_all_actions_widget()
        self.scene.hide_board()
        self.scene.show_all_active_players_cards()
        self.update_buttons()

    @pyqtSlot(bool)
    def on_checkBoxEditMode_toggled(self, checked):
        if checked:
            if self.state == self.State.INIT:
                return
            self.graphics_view.setInteractive(True)
            self.state = self.State.ACTIONS
            self.scene.sync_with_hh(self.hand_history)
            self.scene.request_action(self.hand_history)
            self.update_buttons()
        else:
            self.graphics_view.setInteractive(False)
            self.on_actionFullScreen_triggered()
            self.state = self.State.REPLAY
            self.on_pushButtonStart_clicked()

    @pyqtSlot()
    def on_actionFullScreen_triggered(self):
        log.debug("Toggling full screen")
        self.checkBoxEditMode.setChecked(False)
        self.full_screen_widget = FullScreenView(main_window=self, scene=self.scene)

    @pyqtSlot()
    def on_actionTableGreen_triggered(self):
        self.scene.change_table("green")

    @pyqtSlot()
    def on_actionTableBlue_triggered(self):
        self.scene.change_table("blue")

    @pyqtSlot()
    def on_actionWebcamPlain_triggered(self):
        self.scene.change_background("plain")

    @pyqtSlot()
    def on_actionWebcamBoth_triggered(self):
        self.scene.change_background("both")

    @pyqtSlot()
    def on_actionWebcamLeft_triggered(self):
        self.scene.change_background("left")

    @pyqtSlot()
    def on_actionWebcamRight_triggered(self):
        self.scene.change_background("right")

    @pyqtSlot()
    def on_actionBackBlue_triggered(self):
        CardLook.change_back("blue")

    @pyqtSlot()
    def on_actionBackRed_triggered(self):
        CardLook.change_back("red")

    @pyqtSlot()
    def on_actionQuit_triggered(self):
        self.close()

    @pyqtSlot()
    def on_actionSave_triggered(self):
        log.info(f"Saving to {self.current_filename}")
        self.save_hh(self.current_filename)

    @pyqtSlot()
    def on_actionSaveAs_triggered(self):
        result = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Choisissez le fichier HH à écrire",
            config.config["behavior"].get("default_path"),
            "Fichiers HH (*.hh)",
        )
        filename, selected_filter = result
        if filename:
            self.current_filename = filename
            self.findChild(QtWidgets.QAction, "actionSave").setEnabled(True)
            config.config["behavior"]["default_path"] = str(Path(filename).parent)
            config.save_config()
            self.save_hh(filename)

    @pyqtSlot()
    def on_actionOpen_triggered(self):
        result = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Choisissez le fichier HH à charger",
            config.config["behavior"].get("default_path"),
            "Fichiers HH (*.hh)",
        )
        filename, selected_filter = result
        if filename:
            self.current_filename = filename
            self.findChild(QtWidgets.QAction, "actionSave").setEnabled(True)
            config.config["behavior"]["default_path"] = str(Path(filename).parent)
            config.save_config()
            self.load_hh(filename)

    @pyqtSlot(bool)
    def on_actionHideHandsBeforeShowdown_triggered(self):
        self.scene.sync_with_hh(self.hand_history)

    @pyqtSlot(bool)
    def on_actionOpenGL_triggered(self, checked):
        if checked:
            self.graphics_view.setViewport(QtWidgets.QOpenGLWidget())
        else:
            self.graphics_view.setViewport(QtWidgets.QWidget())
        config.config["animation"]["opengl"] = str(checked)

    @pyqtSlot()
    def on_actionRestoreConfig_triggered(self):
        log.info("Restoring config defaults")
        config.restore_defaults()
        self.statusBar().showMessage(
            "Il est possible qu'il soit nécessaire de quitter et relancer le logiciel "
            "pour que tous les paramètres soient appliqués.",
            5000,
        )
        # self.close()

    def hide_cards_before_showdown(self):
        return (
            self.state == self.State.REPLAY
            and self.findChild(
                QtWidgets.QAction, "actionHideHandsBeforeShowdown"
            ).isChecked()
        )

    def save_hh(self, filename):
        hh_dict = self.hand_history.to_dict()
        hh_dict["n_decimals"] = TextItem.n_decimals
        hh_dict["player_names"] = [
            p.name_item.content for p in self.scene.get_active_players_after_button()
        ]
        hh_dict["n_seats"] = self.scene.n_seats
        hh_dict["n_cards"] = next(self.scene.active_players()).n_cards
        hh_dict["active_seats"] = self.scene.active_seats_idx()
        hh_dict["button_idx"] = self.scene.button_idx()
        hh_dict["hero"] = self.scene.hero_idx
        hh_dict["hands"] = [
            [c.deuces_format() for c in p.card_items]
            for p in self.scene.get_active_players_after_button()
        ]
        hh_dict["board"] = [c.deuces_format() for c in self.scene.board]
        hh_dict["currency"] = self.scene.currency
        hh_dict["currency_is_after"] = self.scene.currency_is_after
        with open(filename, "w", encoding="utf-8") as fp:
            json.dump(hh_dict, fp, cls=HHJSONEncoder)

    def load_hh(self, filename):
        log.info(f"Loading HH file: {filename}")
        self.current_filename = filename
        with open(filename, "r", encoding="utf-8") as fp:
            hh_dict = json.load(fp, object_hook=json_hook)
        self.hand_history = HandHistory.from_dict(hh_dict)
        self.scene.load_dict(hh_dict, self.hand_history)
        self.widgets["checkBoxEditMode"].setChecked(False)
        # Compat with previous HH format that didn't include n_decimals
        sb = self.hand_history.small_blind
        ante = self.hand_history.ante
        n_digits = hh_dict.get(
            "n_decimals", max(-sb.as_tuple().exponent, -ante.as_tuple().exponent, 1)
        )
        TextItem.n_decimals = n_digits
        self.pushButtonStart.clicked.emit()

    def update_buttons(self):
        next_ = self.widgets["pushButtonNext"]
        back = self.widgets["pushButtonBack"]
        edit = self.widgets["checkBoxEditMode"]
        full = self.actionFullScreen
        start = self.widgets["pushButtonStart"]
        start.setEnabled(False)
        if self.state == self.State.INIT:
            next_.setEnabled(
                self.scene.n_active_players >= 2 and self.scene.button_is_given
            )
            next_.setText("Démarrer")
            back.setEnabled(False)
            edit.setEnabled(False)
            full.setEnabled(False)
        elif self.state == self.State.ACTIONS:
            edit.setEnabled(True)
            full.setEnabled(True)

            next_.setEnabled(False)
            # back.setEnabled(True)
            back.setText("Annuler dernière action")

            back.setEnabled(self.hand_history.has_editable_actions())
        elif self.state == self.State.REPLAY:
            edit.setEnabled(True)
            full.setEnabled(True)
            cur = self.replay_action_cursor

            play_len = self.hand_history.play_length()

            back.setText("Retour")
            next_.setText("Suite")

            next_.setEnabled(cur < play_len)
            back.setEnabled(cur > -1)

            start.setEnabled(True)


class FullScreenView(QtWidgets.QGraphicsView, KeyboardShortcutsMixin):
    def __init__(self, main_window: MainWindow, scene: TableScene):
        super().__init__()
        self.setInteractive(False)
        self.setWindowFlag(QtCore.Qt.Window)

        if main_window.actionOpenGL.isChecked():
            self.setViewport(QtWidgets.QOpenGLWidget())

        self.setRenderHint(QtGui.QPainter.HighQualityAntialiasing, True)
        self.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        self.setRenderHint(QtGui.QPainter.Antialiasing, True)
        self.setRenderHint(QtGui.QPainter.LosslessImageRendering, True)

        self.setOptimizationFlag(self.DontAdjustForAntialiasing, True)
        self.setOptimizationFlag(self.DontClipPainter, True)
        self.setOptimizationFlag(self.DontSavePainterState, True)

        self.setScene(scene)
        self.scene = scene
        self.main_window = main_window
        app = QtWidgets.QApplication.instance()

        try:
            size = app.screenAt(main_window.pos()).size()
        except AttributeError:  # sometimes it's not on any screen
            size = app.primaryScreen().size()

        self.showFullScreen()
        self.resize(size)

        xratio = size.width() / scene.sceneRect().width()
        yratio = size.height() / scene.sceneRect().height()
        xratio = yratio = min(xratio, yratio)

        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.scale(xratio, yratio)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        # prevent scrolling on the scene in full screen
        pass


log = logging.getLogger(__name__)
