from __future__ import annotations

import sys
import webbrowser
from datetime import datetime

from PyQt6.QtCore import QSettings, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from models import SCPEntry
from services import sync_database
from storage import database_path, load_scps


class SyncWorker(QThread):
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(list, str)
    failed = pyqtSignal(str)

    def __init__(self, entries: list[SCPEntry]) -> None:
        super().__init__()
        self.entries = entries

    def run(self) -> None:
        try:
            entries = sync_database(self.entries, self.progress.emit)
            self.finished.emit(entries, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SCP Researcher")
        self.resize(1360, 820)
        self.entries: list[SCPEntry] = load_scps()
        self.filtered_entries: list[SCPEntry] = []
        self.settings = QSettings("Local", "SCP Researcher")
        self.favorites: set[str] = set(self.settings.value("favorites", [], list))
        self.sync_worker: SyncWorker | None = None

        self._build_ui()
        self._apply_theme()
        self._load_entries_into_list()
        self._select_first_entry()
        self._start_sync("Checking SCP Wiki for updates...")

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter)

        splitter.addWidget(self._left_panel())
        splitter.addWidget(self._center_panel())
        splitter.addWidget(self._right_panel())
        splitter.setSizes([310, 760, 260])

        self.setCentralWidget(root)

        refresh_action = QAction("Refresh Database", self)
        refresh_action.triggered.connect(lambda: self._start_sync("Manual refresh started..."))
        self.addAction(refresh_action)

    def _left_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)

        heading = QLabel("SCP INDEX")
        heading.setObjectName("sectionHeading")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search SCP number or keyword")
        self.search_input.textChanged.connect(self._load_entries_into_list)

        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._show_selected_entry)

        layout.addWidget(heading)
        layout.addWidget(self.search_input)
        layout.addWidget(self.list_widget, 1)
        return panel

    def _center_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("viewerPanel")
        layout = QVBoxLayout(panel)

        self.title_label = QLabel("SCP Researcher")
        self.title_label.setObjectName("titleLabel")
        self.number_label = QLabel("Local SCP Archive")
        self.number_label.setObjectName("numberLabel")
        self.class_label = QLabel("Object Class: Unknown")
        self.class_label.setObjectName("classLabel")
        self.description_view = QTextBrowser()
        self.description_view.setOpenExternalLinks(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.number_label)
        layout.addWidget(self.class_label)
        layout.addWidget(self.description_view, 1)
        return panel

    def _right_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)

        heading = QLabel("SYSTEM")
        heading.setObjectName("sectionHeading")
        self.refresh_button = QPushButton("Refresh Database")
        self.refresh_button.clicked.connect(lambda: self._start_sync("Manual refresh started..."))
        self.open_button = QPushButton("Open in Browser")
        self.open_button.clicked.connect(self._open_current_in_browser)
        self.favorite_button = QPushButton("Add Favorite")
        self.favorite_button.clicked.connect(self._toggle_favorite)

        self.status_label = QLabel("Standing by")
        self.status_label.setWordWrap(True)
        self.count_label = QLabel("Entries: 0")
        self.database_label = QLabel(str(database_path()))
        self.database_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        layout.addWidget(heading)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.open_button)
        layout.addWidget(self.favorite_button)
        layout.addSpacing(18)
        layout.addWidget(QLabel("Sync Status"))
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.count_label)
        layout.addSpacing(18)
        layout.addWidget(QLabel("Database"))
        layout.addWidget(self.database_label)
        layout.addStretch(1)
        return panel

    def _apply_theme(self) -> None:
        font = QFont("Segoe UI", 10)
        QApplication.instance().setFont(font)
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #0b0f14;
                color: #d8dee9;
            }
            QFrame#panel, QFrame#viewerPanel {
                background: #111822;
                border: 1px solid #253140;
                border-radius: 6px;
            }
            QLabel#sectionHeading {
                color: #d69d45;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0px;
            }
            QLabel#titleLabel {
                color: #f2f5f8;
                font-size: 25px;
                font-weight: 700;
            }
            QLabel#numberLabel {
                color: #8fb7df;
                font-size: 15px;
                font-weight: 600;
            }
            QLabel#classLabel {
                color: #e06c75;
                font-size: 14px;
                font-weight: 600;
            }
            QLineEdit {
                background: #0c121a;
                border: 1px solid #304156;
                border-radius: 5px;
                padding: 9px;
                selection-background-color: #9b2c2c;
            }
            QListWidget, QTextBrowser {
                background: #0c121a;
                border: 1px solid #253140;
                border-radius: 5px;
                padding: 8px;
            }
            QListWidget::item {
                border-bottom: 1px solid #172231;
                padding: 8px;
            }
            QListWidget::item:selected {
                background: #2a3b4f;
                color: #ffffff;
            }
            QPushButton {
                background: #182331;
                border: 1px solid #3a4d63;
                border-radius: 5px;
                padding: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #223145;
                border-color: #d69d45;
            }
            QPushButton:disabled {
                color: #6c7682;
                background: #111820;
            }
            QProgressBar {
                background: #0c121a;
                border: 1px solid #253140;
                border-radius: 5px;
                height: 18px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: #b74747;
                border-radius: 4px;
            }
            """
        )

    def _load_entries_into_list(self) -> None:
        query = self.search_input.text().strip().lower() if hasattr(self, "search_input") else ""
        self.list_widget.clear()
        self.filtered_entries = []

        for entry in self.entries:
            haystack = f"{entry.scp_number} {entry.title} {entry.object_class} {entry.description}".lower()
            if query and query not in haystack:
                continue
            self.filtered_entries.append(entry)
            item = QListWidgetItem(f"{entry.scp_number}  {entry.title}")
            item.setToolTip(entry.url)
            self.list_widget.addItem(item)

        self.count_label.setText(f"Entries: {len(self.entries)}")

    def _select_first_entry(self) -> None:
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)
        elif not self.entries:
            self.description_view.setPlainText(
                "No local SCP database was found. The first sync is running in the background."
            )

    def _current_entry(self) -> SCPEntry | None:
        row = self.list_widget.currentRow()
        if 0 <= row < len(self.filtered_entries):
            return self.filtered_entries[row]
        return None

    def _show_selected_entry(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return

        favorite_mark = " ★" if entry.scp_number in self.favorites else ""
        self.title_label.setText(entry.title + favorite_mark)
        self.number_label.setText(entry.scp_number)
        self.class_label.setText(f"Object Class: {entry.object_class}")
        self.description_view.setPlainText(entry.description)
        self.favorite_button.setText("Remove Favorite" if entry.scp_number in self.favorites else "Add Favorite")

    def _start_sync(self, message: str) -> None:
        if self.sync_worker and self.sync_worker.isRunning():
            self.status_label.setText("Sync already in progress")
            return

        self.status_label.setText(message)
        self.progress_bar.setValue(0)
        self.refresh_button.setEnabled(False)
        self.sync_worker = SyncWorker(self.entries)
        self.sync_worker.progress.connect(self._on_sync_progress)
        self.sync_worker.finished.connect(self._on_sync_finished)
        self.sync_worker.failed.connect(self._on_sync_failed)
        self.sync_worker.start()

    def _on_sync_progress(self, message: str, current: int, total: int) -> None:
        self.status_label.setText(message)
        if total:
            self.progress_bar.setValue(int((current / total) * 100))

    def _on_sync_finished(self, entries: list[SCPEntry], timestamp: str) -> None:
        self.entries = entries
        self._load_entries_into_list()
        self._select_first_entry()
        self.status_label.setText(f"Last update: {timestamp}")
        self.progress_bar.setValue(100)
        self.refresh_button.setEnabled(True)

    def _on_sync_failed(self, message: str) -> None:
        self.status_label.setText("Network sync failed; using local cache")
        self.refresh_button.setEnabled(True)
        if not self.entries:
            QMessageBox.warning(self, "SCP Researcher", f"Unable to build database:\n{message}")

    def _open_current_in_browser(self) -> None:
        entry = self._current_entry()
        if entry:
            webbrowser.open(entry.url)

    def _toggle_favorite(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        if entry.scp_number in self.favorites:
            self.favorites.remove(entry.scp_number)
        else:
            self.favorites.add(entry.scp_number)
        self.settings.setValue("favorites", sorted(self.favorites))
        self._show_selected_entry()


def run() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
