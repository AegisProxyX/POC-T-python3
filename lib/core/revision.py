import subprocess
from pathlib import Path
def getRevisionNumber():
    try:
        result = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
            cwd=Path(__file__).resolve().parents[2], capture_output=True,
            text=True, timeout=5, check=True)
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None
