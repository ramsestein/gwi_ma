"""Pseudo-terminal helpers that stand in for serial ports in tests (Linux/macOS)."""
import os
import select
import threading
import tty


class PtyPort:
    """One pty pair. `path` is opened with pyserial as if it were a serial port;
    the test talks to it through the master side (write/read)."""

    def __init__(self):
        self.master, self._slave = os.openpty()
        tty.setraw(self._slave)
        self.path = os.ttyname(self._slave)

    def write(self, data: bytes) -> None:
        os.write(self.master, data)

    def read(self, n: int = 4096, timeout: float = 1.0) -> bytes:
        ready, _, _ = select.select([self.master], [], [], timeout)
        return os.read(self.master, n) if ready else b""

    def read_until(self, total: int, timeout: float = 2.0) -> bytes:
        buf = b""
        while len(buf) < total:
            chunk = self.read(total - len(buf), timeout)
            if not chunk:
                break
            buf += chunk
        return buf

    def close(self) -> None:
        for fd in (self.master, self._slave):
            try:
                os.close(fd)
            except OSError:
                pass


class NullModem:
    """Joins two PtyPorts like a null-modem cable: bytes written to one port
    arrive at the other. `mutate` can alter bytes in transit to inject faults."""

    def __init__(self, mutate=None):
        self.a = PtyPort()
        self.b = PtyPort()
        self.mutate = mutate or (lambda data: data)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._relay, daemon=True)
        self._thread.start()

    def _relay(self):
        pair = {self.a.master: self.b.master, self.b.master: self.a.master}
        while not self._stop.is_set():
            ready, _, _ = select.select(list(pair), [], [], 0.05)
            for fd in ready:
                try:
                    data = os.read(fd, 4096)
                except OSError:
                    return
                if data:
                    os.write(pair[fd], self.mutate(data))

    def close(self):
        self._stop.set()
        self._thread.join(timeout=1)
        self.a.close()
        self.b.close()
