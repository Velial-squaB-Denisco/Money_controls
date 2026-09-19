from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LoadingDotsWidget(QWidget):
    def __init__(self, text: str = "Загрузка", parent=None):
        super().__init__(parent)

        self._base_text = text
        self._dots = 0

        layout = QVBoxLayout(self)

        self.label = QLabel(text)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: #6b7280; font-size: 15px;")

        layout.addWidget(self.label)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._dots = 0
        self._update()
        self.timer.start(400)

    def stop(self) -> None:
        self.timer.stop()
        self._update()

    def _tick(self) -> None:
        self._dots = (self._dots + 1) % 4
        self._update()

    def _update(self) -> None:
        self.label.setText(self._base_text + "." * self._dots)