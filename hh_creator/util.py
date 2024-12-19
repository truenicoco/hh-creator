import logging
from decimal import Decimal, InvalidOperation
from enum import Enum

from poker.constants import PokerEnum
from PyQt5 import Qt, QtCore, QtGui, QtMultimedia, QtWidgets, uic

from .config import RESOURCE_PATH

log = logging.getLogger(__name__)


class ActionType(PokerEnum):
    ANTE = ("post ante",)
    SB = ("post SB",)
    BB = ("post BB",)
    BET = "bet", "bets"
    RAISE = "raise", "raises"
    CHECK = "check", "checks"
    FOLD = "fold", "folded", "folds"
    CALL = "call", "calls"
    RETURN = "return", "returned", "uncalled"
    WIN = "win", "won", "collected"
    SHOW = ("show",)
    MUCK = "don't show", "didn't show", "did not show", "mucks"
    THINK = ("seconds left to act",)
    STRADDLE = ("straddle",)


class IncrementableEnum(Enum):
    def next(self):
        return self.__class__(self._value_ + 1)

    def prev(self):
        return self.__class__(self._value_ - 1)

    def __str__(self):
        return self._name_

    def __gt__(self, other):
        return self._value_ > other._value_

    def __sub__(self, other):
        return self._value_ - other._value_


class Image:
    IMG_PATH = RESOURCE_PATH / "img"

    @staticmethod
    def get(filename, parent=None):
        path = Image.IMG_PATH / f"{filename}"
        if path.with_suffix(".svg").exists():
            log.debug(f"Loading {path}")
            item = Qt.QGraphicsSvgItem(str(path.with_suffix(".svg")), parent)
            return item
        elif path.with_suffix(".png").exists():
            log.debug(f"Loading {path}")
            img = QtGui.QPixmap(str(path.with_suffix(".png")), parent)
            return Qt.QGraphicsPixmapItem(img)
        else:
            raise FileNotFoundError


class AutoUI:
    UI_PATH = RESOURCE_PATH / "ui"

    def __init__(self):
        self._load_ui()
        self.widgets = {}
        i = 0
        for obj in self.findChildren(QtWidgets.QWidget):
            if obj.objectName():
                key = obj.objectName()
            else:
                key = i
                i += 1
            self.widgets[key] = obj

    def _load_ui(self):
        uic.loadUi(self.UI_PATH / f"{type(self).__name__}.ui", self)


class AmountValidatorWithBounds(QtGui.QDoubleValidator):
    # Forbid "," that Decimal() does not like.
    LOCALE = QtCore.QLocale()
    log.debug(f"Locale is {LOCALE}")
    LOCALE.setNumberOptions(QtCore.QLocale.RejectGroupSeparator)

    def __init__(self, minimum=None, maximum=None, *a, **kw):
        super().__init__(*a, **kw)
        self.setNotation(QtGui.QDoubleValidator.StandardNotation)
        self.setLocale(self.LOCALE)
        if minimum is not None:
            self.setBottom(minimum)
        if maximum is not None:
            self.setTop(maximum)


class IntValidator(QtGui.QIntValidator):
    def __init__(self):
        super().__init__()
        self.setBottom(1)


def decimal_conversion(text):
    try:
        return Decimal(text)
    except InvalidOperation:
        log.warning(f"Error converting {text} to decimal, returning 0")
        return Decimal(0)


def int_conversion(text):
    try:
        return int(text)
    except InvalidOperation:
        log.warning(f"Error converting {text} to int, returning 0")
        return 0


def barycenter(x1, y1, x2, y2, w1=1, w2=2):
    return (w1 * x1 + w2 * x2) / (w1 + w2), (w1 * y1 + w2 * y2) / (w1 + w2)


def get_center(item, scene=False):
    if scene:
        pos = item.scenePos()
    else:
        pos = item.pos()
    x = pos.x()
    y = pos.y()
    rect = item.boundingRect().center()
    return [x + rect.x(), y + rect.y()]


def amount_format(x, n_decimals):
    if float(x).is_integer():
        return f"{int(x):n}"
    else:
        x = round(x, n_decimals)
        return f"{x:n}"


BLINDS = [ActionType.SB, ActionType.BB, ActionType.STRADDLE]


_sounds = {
    f.stem: QtMultimedia.QSound(str(f))
    for f in (RESOURCE_PATH / "sounds").glob("*.wav")
}

sounds = {
    ActionType.BET: _sounds["bet"],
    ActionType.RAISE: _sounds["bet"],
    ActionType.CHECK: _sounds["check"],
    ActionType.CALL: _sounds["call"],
    ActionType.FOLD: _sounds["fold"],
    ActionType.BB: _sounds["bet"],
    ActionType.ANTE: _sounds["bet"],
    ActionType.STRADDLE: _sounds["bet"],
    "street": _sounds["street"],
    "call_closing": _sounds["call_closing"],
}


amount_validator = AmountValidatorWithBounds(0)
int_validator = QtGui.QIntValidator()
