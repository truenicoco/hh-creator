import locale
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("hh-creator")
except PackageNotFoundError:
    __version__ = "DEV"

locale.setlocale(locale.LC_ALL, "")
