import sys
PYVERSION = sys.version.split()[0]
if sys.version_info < (3, 10):
    raise SystemExit('Python 3.10 or newer is required.')
