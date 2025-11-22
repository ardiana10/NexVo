# idle_watcher.py
from PyQt6.QtCore import QObject, QTimer, QEvent
from otp_dialog import show_otp_dialog


class GlobalIdleWatcher(QObject):
    def __init__(self, app, timeout_ms=1 * 60 * 1000):
        super().__init__()
        self.app = app
        self.timeout_ms = timeout_ms

        self.timer = QTimer()
        self.timer.setInterval(self.timeout_ms)
        self.timer.timeout.connect(self._lock_now)
        self.timer.start()

        app.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() in (
            QEvent.Type.MouseMove,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.KeyPress,
            QEvent.Type.Wheel,
            QEvent.Type.FocusIn,
        ):
            self.timer.start()
        return False

    def _lock_now(self):
        parent = self.app.activeWindow()
        ok = show_otp_dialog(parent)
        if ok:
            self.timer.start()