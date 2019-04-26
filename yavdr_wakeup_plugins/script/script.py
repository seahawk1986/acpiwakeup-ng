import subprocess
import sys

class Wakeup:
    def __init__(path):
        self.path = path

    def setWakeup(dt):
        try:
            subprocess.run([path, str(int(dt.timestamp()))])
        except Exception as e:
            print(str(e), file=sys.stderr)
            dt = None
        return dt

