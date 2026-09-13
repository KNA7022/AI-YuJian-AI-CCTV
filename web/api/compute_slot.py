"""One GPU owner shared by offline job dispatch and live session startup."""
import threading

lock = threading.Lock()
