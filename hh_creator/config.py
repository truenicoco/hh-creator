import logging
import os
from configparser import ConfigParser, ExtendedInterpolation
from pathlib import Path


def save_config(window_geometry=None, window_state=None):
    log.info(f"Writing config to {config_filename}")
    with config_filename.open("w", encoding="utf-8") as fp:
        config.write(fp)
    if window_geometry is not None:
        with geometry_filename.open("wb") as fp:
            fp.write(bytes(window_geometry))
    if window_state is not None:
        with state_filename.open("wb") as fp:
            fp.write(bytes(window_state))


def restore_defaults():
    config = ConfigParser(interpolation=ExtendedInterpolation())
    config.read(RESOURCE_PATH / "default.ini", encoding="utf-8")
    with config_filename.open("w", encoding="utf-8") as fp:
        config.write(fp)


def escape_dollar(obj):
    s = str(obj).replace("$", "$$")
    return s


log = logging.getLogger(__name__)

candidates = [
    Path(__file__).parent / "resource",
    Path(__file__).parent.parent / "resource",  # Needed for pyinstaller
]

for c in candidates:
    if c.exists():
        RESOURCE_PATH = c
        break
else:
    raise FileNotFoundError("Cannot find resource files!")

if os.getenv("XDG_CONFIG_HOME") is not None:
    config_dir = Path(os.getenv("XDG_CONFIG_HOME")) / "hh-creator"
elif os.getenv("LOCALAPPDATA") is not None:
    config_dir = Path(os.getenv("LOCALAPPDATA")) / "hh-creator"
else:
    config_dir = Path.home() / ".config" / "hh-creator"

config_filename = config_dir / "config.ini"
geometry_filename = config_dir / "geometry.bin"
state_filename = config_dir / "state.bin"

try:
    with geometry_filename.open("rb") as fp:
        geometry = fp.read()
except FileNotFoundError:
    geometry = None

try:
    with state_filename.open("rb") as fp:
        state = fp.read()
except FileNotFoundError:
    state = None

config = ConfigParser(interpolation=ExtendedInterpolation())
config.read(RESOURCE_PATH / "default.ini", encoding="utf-8")
if not config_filename.exists():
    log.info("No config file found")
    config_dir.mkdir(parents=True, exist_ok=True)
    save_config()
else:
    log.info(f"Loading config from {config_filename}")
    config.read(config_filename, encoding="utf-8")
