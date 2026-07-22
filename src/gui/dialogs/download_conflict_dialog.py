"""Диалог разрешения конфликтов при скачивании."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox,
    QDialogButtonBox, QWidget, QHBoxLayout,
    QGroupBox
)

class DownloadConflictDialog(QDialog):
    def __init__(self, conflicts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Конфликт файлов")
        self.setMinimumWidth(500)
        self.conflicts = conflicts
        self.decisions = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        label = QLabel("Некоторые файлы уже существуют. Выберите действие для каждого:")
        label.setWordWrap(True)
        layout.addWidget(label)

        group = QGroupBox()
        group_layout = QVBoxLayout(group)

        self.combo_boxes = []
        for item in self.conflicts:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            name_label = QLabel(item.name)
            name_label.setFixedWidth(250)
            combo = QComboBox()
            combo.addItem("Сохранить с новым именем (копия)", "rename")
            combo.addItem("Перезаписать", "overwrite")
            combo.addItem("Пропустить", "skip")
            combo.setCurrentIndex(0)
            row_layout.addWidget(name_label)
            row_layout.addWidget(combo)
            group_layout.addWidget(row)
            self.combo_boxes.append(combo)

        layout.addWidget(group)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        # Сохраняем индивидуальные решения
        for i, item in enumerate(self.conflicts):
            self.decisions[item.path] = self.combo_boxes[i].currentData()
        self.accept()

    def get_decisions(self):
        return self.decisions