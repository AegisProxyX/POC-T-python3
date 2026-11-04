import shutil
__all__ = ['getTerminalSize']
def getTerminalSize():
    return tuple(shutil.get_terminal_size(fallback=(80, 25)))
