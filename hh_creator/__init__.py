import locale
import sys

from PyQt5 import QtWidgets

locale.setlocale(locale.LC_ALL, "")

__version__ = "NO_VERSION"

app = QtWidgets.QApplication(sys.argv)
