import logging
import typing
from dataclasses import dataclass
from decimal import Decimal

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import pyqtSlot

from . import config, hh
from .util import AutoUI, amount_validator, decimal_conversion

if typing.TYPE_CHECKING:
    from .player import PlayerItemGroup


@dataclass
class Field:
    type: type
    checkable: bool
    input: str = "lineEdit"
    input_property: str = "Text"


class NewHandDialog(QtWidgets.QDialog, AutoUI):
    FIELDS = {
        "SB": Field(Decimal, True),
        "BB": Field(Decimal, False),
        "Straddle": Field(int, True),
        "Ante": Field(Decimal, True),
        "BBAnte": Field(Decimal, True),
        "Players": Field(int, False),
        "Currency": Field(str, True),
        "Variant": Field(str, False, "comboBox", "CurrentText"),
        "CurrencyPosition": Field(str, False, "comboBox", "CurrentText"),
        "Decimals": Field(int, True),
    }

    N_CARDS = {"Texas": 2, "Omaha": 4}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)

        self.ok_button = self.widgets[0]

        conf = config.config["new_hand"]
        for name, field in self.FIELDS.items():
            widget = self._get_widget(name)
            getattr(widget, f"set{field.input_property}")(conf.get(name))
            if field.checkable:
                checkbox = self._get_checkbox(name)
                checked = conf.getboolean(f"{name}_checked")
                checkbox.setChecked(checked)
                widget.setEnabled(checked)
                checkbox.toggled.connect(widget.setEnabled)
        self.conf = conf
        self.open_instead = False
        self.update_ok()

    def _auto_decimals(self):
        sb = self.get_field_value("SB", Decimal())
        ante = self.get_field_value("Ante", Decimal())
        self._get_widget("Decimals").setText(
            str(max(-sb.as_tuple().exponent, -ante.as_tuple().exponent, 1))
        )

    def _auto_sb(self):
        self._get_widget("SB").setText(str(self.get_field_value("BB") / 2))

    def _get_widget(self, field_name):
        field = self.FIELDS[field_name]
        return self.widgets[f"{field.input}{field_name}"]

    def _get_checkbox(self, field_name):
        return self.widgets[f"checkBox{field_name}"]

    def get_field_value(self, field_name, default=None):
        field = self.FIELDS[field_name]
        widget = self._get_widget(field_name)
        try:
            text = widget.text()
        except AttributeError:  # For combobox
            text = widget.currentText()

        if (
            field_name not in ("SB", "Decimals")
            and field.checkable
            and not self._get_checkbox(field_name).isChecked()
        ):
            return field.type()

        try:
            return field.type(text)
        except Exception:
            log.warning(f"Conversion error from {text} for {field.type}")
            return default

    def get_n_cards(self):
        return self.N_CARDS[self.get_field_value("Variant")]

    @pyqtSlot(str)
    def on_lineEditSB_textEdited(self, value):
        if not self.widgets["checkBoxDecimals"].isChecked():
            self._auto_decimals()
        self.update_ok()

    @pyqtSlot(bool)
    def on_checkBoxSB_toggled(self, checked):
        if not checked:
            self._auto_sb()
        self.update_ok()

    @pyqtSlot(bool)
    def on_checkBoxDecimals_toggled(self, checked):
        if not checked:
            self._auto_decimals()
        self.update_ok()

    @pyqtSlot(str)
    def on_lineEditBB_textEdited(self, value):
        if not self.widgets["checkBoxSB"].isChecked():
            self._auto_sb()
        if not self.widgets["checkBoxDecimals"].isChecked():
            self._auto_decimals()
        self.update_ok()

    @pyqtSlot(str)
    def on_lineEditStraddle_textEdited(self, value):
        self.update_ok()

    @pyqtSlot(bool)
    def on_checkBoxStraddle_toggled(self, checked):
        if not checked:
            self._get_widget("Straddle").setText("0")
        self.update_ok()

    @pyqtSlot(str)
    def on_lineEditAnte_textEdited(self, value):
        self._auto_decimals()
        self.update_ok()

    @pyqtSlot(bool)
    def on_checkBoxAnte_toggled(self, checked):
        if not checked:
            self._get_widget("Ante").setText("0")
        self.update_ok()

    @pyqtSlot(bool)
    def on_checkBoxBBAnte_toggled(self, checked):
        if not checked:
            self._get_widget("BBAnte").setText("0")
        self.update_ok()

    @pyqtSlot(str)
    def on_lineEditPlayers_textEdited(self, value):
        self.update_ok()

    @pyqtSlot()
    def on_pushButtonOpen_clicked(self):
        self.open_instead = True
        self.close()

    def update_ok(self):
        sb = self.get_field_value("SB", default=0)
        bb = self.get_field_value("BB", default=0)
        straddle = self.get_field_value("Straddle", default=0)
        ante = self.get_field_value("Ante", default=0)
        players = self.get_field_value("Players", default=0)
        decimals = self.get_field_value("Decimals", default=0)

        sb_ok = 0 <= sb <= bb
        bb_ok = 0 < bb
        straddle_ok = (
            not self._get_checkbox("Straddle").isChecked()
            or 0 < straddle <= players - 2
        )
        ante_ok = not self._get_checkbox("Ante").isChecked() or 0 < ante
        players_ok = 2 <= players <= 10
        decimals_ok = decimals >= 0

        self.ok_button.setEnabled(
            all((sb_ok, bb_ok, straddle_ok, ante_ok, players_ok, decimals_ok))
        )


class NameDialog(QtWidgets.QDialog, AutoUI):
    def __init__(self, parent, content):
        super().__init__(parent=parent)

        line_edit = self.widgets["lineEdit"]
        line_edit.setText(str(content))
        line_edit.selectAll()
        self.show()

    @pyqtSlot(str)
    def on_lineEdit_textEdited(self, text):
        self.findChild(QtWidgets.QPushButton).setEnabled(bool(text))


class StackDialog(QtWidgets.QDialog, AutoUI):
    def __init__(self, parent, value):
        super().__init__(parent)
        self.line_edit: QtWidgets.QLineEdit = self.widgets["lineEdit"]
        self.line_edit.setText(str(value))
        self.line_edit.setValidator(amount_validator)
        self.line_edit.selectAll()
        self.show()

    def get_value(self):
        return decimal_conversion(self.widgets["lineEdit"].text())


class ActionWidget(QtWidgets.QWidget, AutoUI):
    def __init__(self, player_item: "PlayerItemGroup", parent):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.slider: QtWidgets.QSlider = self.widgets["horizontalSlider"]
        self.slider_values = []
        self.player_item = player_item

    def set_min_max_step(self, min_, max_, step):
        values = [min_]
        while values[-1] < max_:
            values.append(values[-1] + step)
        if len(values) > 1:
            values[-1] = max_
        else:
            values.append(max_)
        self.slider.setMinimum(0)
        self.slider.setMaximum(len(values) - 1)
        self.slider.setValue(0)
        self.slider_values = values
        self.widgets["lineEdit"].setText(str(min_))

    def set_possible_actions(self, action_types):
        self.widgets["call"].setEnabled(hh.ActionType.CALL in action_types)
        self.widgets["check"].setEnabled(hh.ActionType.CHECK in action_types)
        bet = hh.ActionType.BET in action_types or hh.ActionType.RAISE in action_types
        self.widgets["bet"].setEnabled(bet)
        self.slider.setEnabled(bet)
        self.widgets["lineEdit"].setEnabled(bet)

    def amount(self):
        return decimal_conversion(self.widgets["lineEdit"].text())

    @pyqtSlot(int)
    def on_horizontalSlider_valueChanged(self, index):
        try:
            linevalue = float(self.widgets["lineEdit"].text())
        except ValueError:
            linevalue = 0
        if (
            index == 0
            or index == len(self.slider_values) - 1
            or not (
                self.slider_values[index - 1]
                < linevalue
                < self.slider_values[index + 1]
            )
        ):
            self.widgets["lineEdit"].setText(str(self.slider_values[index]))

        self.widgets["bet"].setEnabled(True)

    @pyqtSlot(str)
    def on_lineEdit_textEdited(self, value):
        try:
            value = float(value)
        except ValueError:
            log.warning("Invalid value entered")
            self.widgets["bet"].setEnabled(False)
            return

        if self.slider_values[0] <= value <= self.slider_values[-1]:
            self.widgets["bet"].setEnabled(True)
            for i, v in enumerate(self.slider_values):
                if v >= value:
                    break
            else:
                raise ValueError("Shouldn't happen, slider stuff")
            self.slider.setValue(i)
        elif value > self.slider_values[-1]:
            max_ = self.slider_values[-1]
            self.widgets["lineEdit"].setText(str(max_))
            self.slider.setValue(len(self.slider_values) - 1)
        elif value < self.slider_values[0]:
            self.widgets["bet"].setEnabled(False)

    @pyqtSlot()
    def on_bet_clicked(self):
        self.player_item.add_action(hh.ActionType.BET, self.amount())

    @pyqtSlot()
    def on_fold_clicked(self):
        self.player_item.add_action(hh.ActionType.FOLD)

    @pyqtSlot()
    def on_check_clicked(self):
        self.player_item.add_action(hh.ActionType.CHECK)

    @pyqtSlot()
    def on_call_clicked(self):
        self.player_item.add_action(hh.ActionType.CALL)


log = logging.getLogger()


if __name__ == "__main__":
    app = QtWidgets.QApplication.instance()
    logging.basicConfig(level=logging.DEBUG)
    dialog = NewHandDialog()
    dialog.show()
    app.exec()
