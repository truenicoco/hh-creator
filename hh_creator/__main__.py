import logging
import sys
from argparse import ArgumentParser

from PyQt5 import QtWidgets

from hh_creator.main_window import MainWindow

app = QtWidgets.QApplication.instance()

parser = ArgumentParser()

parser.add_argument(
    "-d",
    "--debug",
    help="print lots of debugging statements",
    action="store_const",
    dest="loglevel",
    const=logging.DEBUG,
    default=logging.WARNING,
)
parser.add_argument(
    "-v",
    "--verbose",
    help="be verbose",
    action="store_const",
    dest="loglevel",
    const=logging.INFO,
)
parser.add_argument("--log-file")

args = parser.parse_args(app.arguments()[1:])
# noinspection PyArgumentList
logging.basicConfig(
    level=args.loglevel,
    # Force UTF8 because f***ing Windows and its cp1252
    handlers=(
        [logging.FileHandler(args.log_file, "w", "utf-8")]
        if args.log_file is not None
        else None
    ),
)


window = MainWindow()
app.main_window = window
sys.exit(app.exec())
