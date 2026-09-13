"""Atomic replacement with bounded retries for Windows reader sharing locks."""
import time


def replace_when_ready(temporary, target):
    for attempt in range(8):
        try:
            temporary.replace(target)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(.025 * (attempt+1))
