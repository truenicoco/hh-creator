# this is required by pyinstaller for some reason

from PyInstaller.utils.hooks import copy_metadata

datas = copy_metadata("poker")
