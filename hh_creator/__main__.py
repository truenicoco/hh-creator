import logging
import os
import sys
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from tempfile import gettempdir

from PyQt5 import QtWidgets

from hh_creator import __version__
from hh_creator.main_window import MainWindow


def main():
    app = QtWidgets.QApplication.instance()

    parser = ArgumentParser()

    parser.add_argument(
        "-d",
        "--debug",
        help="print lots of debugging statements",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
        default=logging.INFO,
    )
    parser.add_argument(
        "--log-file",
        default=(
            Path(gettempdir()) / f"hh-creator-{datetime.now():%Y%m%d-%H%M}.txt"
            if os.name == "nt"
            else None
        ),
    )

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
    logging.info("Starting HH Creator version %s", __version__)

    window = MainWindow()
    app.main_window = window
    sys.exit(app.exec())


main()
