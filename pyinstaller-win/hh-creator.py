import logging
import sys
from datetime import datetime
from pathlib import Path

sys.argv.extend(
    [
        "-v",
        "--log-file",
        str(Path(__file__).parent / f"{datetime.now().strftime('%d%b%y-%H_%M')}.log"),
    ]
)

log = logging.getLogger(__name__)

try:
    import hh_creator.__main__
except Exception as e:
    log.exception(e)
