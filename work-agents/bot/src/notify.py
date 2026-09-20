"""Notification macOS + trace ecrite. Stdlib + osascript uniquement."""
import datetime
import os
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
DATA = os.path.join(ROOT, "data")
os.makedirs(DATA, exist_ok=True)
ALERTS = os.path.join(DATA, "alerts.log")


def alert(title, message):
    """Affiche une notification macOS, trace toujours dans alerts.log. Retourne bool."""
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    try:
        with open(ALERTS, "a", encoding="utf-8") as f:
            f.write(f"{ts} [{title}] {message}\n")
    except OSError:
        pass
    try:
        t = str(title).replace("\\", "").replace('"', "'")
        m = str(message).replace("\\", "").replace('"', "'")
        subprocess.run(
            ["osascript", "-e", f'display notification "{m}" with title "{t}"'],
            timeout=5,
            capture_output=True,
        )
        return True
    except Exception:
        return False


if __name__ == "__main__":
    print(alert("test", "test"))
