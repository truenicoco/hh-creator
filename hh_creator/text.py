import logging
import time
import typing

from PyQt5 import QtCore, QtGui, QtWidgets

from . import config
from .config import RESOURCE_PATH
from .dialog import NameDialog, StackDialog
from .util import amount_format, decimal_conversion


class TextItem(QtWidgets.QGraphicsTextItem):
    n_decimals = 1

    def __init__(
        self,
        postfix="",
        prefix="",
        currency="",
        currency_is_after=True,
        hide_if_empty=True,
        content_is_number=False,
        color=config.config["text"].get("global_font_color"),
        point_size=config.config["text"].getint("global_font_size"),
        weight=config.config["text"].getint("global_font_weight"),
        italic=False,
        *a,
        **kwa,
    ):
        super().__init__(*a, **kwa)
        font = QtGui.QFont(_fontstr, point_size, weight, italic)
        self.setFont(font)
        self.setDefaultTextColor(QtGui.QColor(color))
        self.set_center(0, 0)
        self.prefix = prefix
        self.postfix = postfix
        self.hide_if_empty = hide_if_empty
        if content_is_number:
            self._content = 0
        else:
            self._content = ""
        self.content_is_number = content_is_number
        self.currency = currency
        self.currency_is_after = currency_is_after

    def point_size(self):
        return self.font().pointSize()

    def color(self):
        return self.defaultTextColor()

    def weight(self):
        return self.font().weight()

    def font_kwargs(self):
        return {
            "point_size": self.point_size(),
            "color": self.color(),
            "weight": self.weight(),
        }

    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, value):
        log.debug(f"Updating content of {self}")
        if self.hide_if_empty and not value:
            log.debug(f"Hiding {self} because empty value")
            self.setVisible(False)
        else:
            self.setVisible(True)
        old_width = self.boundingRect().width()
        self._content = value
        text = self.prefix
        if not self.currency_is_after:
            text += self.currency
        if self.content_is_number:
            text += amount_format(value, self.n_decimals)
        else:
            text += str(value)
        if self.currency_is_after:
            text += self.currency
        text += self.postfix
        self.setPlainText(text)
        new_width = self.boundingRect().width()
        super().moveBy((old_width - new_width) / 2, 0)

    def get_pos_if_content(self, content):
        item = TextItem(
            postfix=self.postfix,
            prefix=self.prefix,
            currency_is_after=self.currency_is_after,
            currency=self.currency,
            **self.font_kwargs(),
            content_is_number=self.content_is_number,
        )
        item.set_center(self.sceneBoundingRect().center())
        item.content = content
        # self.scene().addItem(item)
        return item.scenePos()

    def set_center(
        self,
        pos: typing.Union[QtCore.QPointF, QtCore.QPoint, float],
        y: float = None,
        scene=False,
    ):
        if y is not None:
            pos = QtCore.QPointF(pos, y)
        rect = self.boundingRect()
        if scene:
            rpos = self.scenePos()
        else:
            rpos = self.pos()
        offset = pos - rect.center() - rpos
        super().moveBy(offset.x(), offset.y())


class StackItem(QtWidgets.QGraphicsItemGroup):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.stack_item = TextItem(hide_if_empty=False, content_is_number=True)
        self.action_item = TextItem()
        self.addToGroup(self.stack_item)
        self.addToGroup(self.action_item)
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)

    @property
    def stack(self):
        return decimal_conversion(self.stack_item.content)

    @stack.setter
    def stack(self, value):
        self.timer.timeout.connect(lambda: setattr(self.stack_item, "content", value))
        if not self.timer.isActive():
            self.stack_item.content = value

    @property
    def action(self):
        return

    @action.setter
    def action(self, value):
        log.debug(f"Setting timer to briefly display action {value}")
        self.action_item.content = value
        self.stack_item.setVisible(False)
        start = time.time()
        log.debug(f"Timer start:{start}")
        timer = self.timer
        timer.timeout.connect(lambda: self.stack_item.setVisible(True))
        timer.timeout.connect(lambda: self.action_item.setVisible(False))
        timer.timeout.connect(
            lambda: log.debug(f"end:{time.time()} ({time.time()-start})")
        )
        timer.start(config.config["animation"].getint("LAST_ACTION_DURATION"))

    def set_center(self, *a):
        self.stack_item.set_center(*a)
        self.action_item.set_center(*a)

    def dialog(self):
        win = self.scene().parent()
        dialog = StackDialog(win, self.stack)
        if dialog.exec():
            self.stack = dialog.get_value()

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        log.debug("Click on stack")
        win = self.scene().parent()
        if win.state != win.State.INIT:
            return
        self.dialog()
        # noinspection PyTypeChecker


class NameItem(TextItem):
    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        log.debug(f"Click on {self}")
        win = self.scene().parent()
        # noinspection PyTypeChecker
        dialog = NameDialog(win, self.content)
        if dialog.exec():
            self.content = dialog.widgets["lineEdit"].text()


log = logging.getLogger(__name__)

FILE_NAME = RESOURCE_PATH / "Lato-Black.ttf"
_id = QtGui.QFontDatabase.addApplicationFont(str(FILE_NAME))
_fontstr = QtGui.QFontDatabase.applicationFontFamilies(_id)
try:
    _fontstr = _fontstr[0]
except IndexError:
    log.warning("Could not load Lato font file for some reason")
    _fontstr = "Lato"
_FONT = QtGui.QFont(_fontstr, 30, 100, False)
