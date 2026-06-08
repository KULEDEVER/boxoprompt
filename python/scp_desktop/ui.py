from __future__ import annotations

import random
import sys
from datetime import datetime

from PyQt6.QtCore import QThread, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .data import MAX_SCP_NUMBER
from .models import HistoryItem, ScpEntry
from .services import ScpInputError, ScpService
from .storage import AppStorage


THEMES = {
    "amber": {
        "name": "Amber Theme",
        "mode": "CONTAINMENT ALERT",
        "bg": "#080a08",
        "panel": "#10150f",
        "panel_alt": "#151c14",
        "field": "#0c110c",
        "text": "#edf7e8",
        "muted": "#94a48e",
        "line": "#2e3a2b",
        "accent": "#f2b84b",
        "accent_dim": "#7c5d25",
        "good": "#78d982",
        "danger": "#ff5d52",
        "button_text": "#151007",
    },
    "red": {
        "name": "Red Theme",
        "mode": "BREACH MODE",
        "bg": "#0d0708",
        "panel": "#170d10",
        "panel_alt": "#211114",
        "field": "#10090b",
        "text": "#fff0ef",
        "muted": "#bc9295",
        "line": "#462329",
        "accent": "#ff4f58",
        "accent_dim": "#852931",
        "good": "#f4c45b",
        "danger": "#ff2035",
        "button_text": "#190708",
    },
    "blue": {
        "name": "Blue Theme",
        "mode": "ARCHIVE MODE",
        "bg": "#071019",
        "panel": "#0d1824",
        "panel_alt": "#122235",
        "field": "#09131d",
        "text": "#e9f6ff",
        "muted": "#91abc0",
        "line": "#24425b",
        "accent": "#68d8ff",
        "accent_dim": "#245c74",
        "good": "#9ca7ff",
        "danger": "#ff6678",
        "button_text": "#071018",
    },
}

CLASS_COLORS = {
    "Safe": "#79dc89",
    "Euclid": "#f1b94d",
    "Keter": "#ff5964",
    "Thaumiel": "#6bd7ff",
    "Neutralized": "#b7c4c2",
    "Explained": "#b7c4c2",
    "Apollyon": "#d947ff",
    "Archon": "#6bd7ff",
    "Ticonderoga": "#6bd7ff",
    "Pending": "#9aa6a0",
    "Unavailable": "#ff5964",
}


def build_qss(tokens: dict[str, str]) -> str:
    return f"""
    * {{
        font-family: "Segoe UI";
        color: {tokens["text"]};
        selection-background-color: {tokens["accent_dim"]};
        selection-color: {tokens["text"]};
    }}
    QMainWindow, QWidget#Root {{
        background: {tokens["bg"]};
    }}
    QFrame#Sidebar, QFrame#CenterPanel, QFrame#ActionPanel {{
        background: {tokens["panel"]};
        border: 1px solid {tokens["line"]};
    }}
    QFrame#HeaderBand, QFrame#DetailBlock, QFrame#HistoryBlock {{
        background: {tokens["panel_alt"]};
        border: 1px solid {tokens["line"]};
    }}
    QLabel#AppTitle {{
        color: {tokens["accent"]};
        font-size: 23px;
        font-weight: 800;
    }}
    QLabel#ModeLabel, QLabel#StatusLabel {{
        color: {tokens["accent"]};
        font-family: "Cascadia Mono", "Consolas";
        font-size: 11px;
    }}
    QLabel#SectionLabel {{
        color: {tokens["muted"]};
        font-family: "Cascadia Mono", "Consolas";
        font-size: 11px;
        font-weight: 700;
    }}
    QLabel#ScpCode {{
        color: {tokens["accent"]};
        font-family: "Cascadia Mono", "Consolas";
        font-size: 44px;
        font-weight: 900;
    }}
    QLabel#ScpTitle {{
        color: {tokens["text"]};
        font-size: 25px;
        font-weight: 800;
    }}
    QLabel#ScpDescription {{
        color: {tokens["muted"]};
        font-size: 14px;
        line-height: 150%;
    }}
    QLabel#MetaPill {{
        background: {tokens["field"]};
        border: 1px solid {tokens["line"]};
        border-radius: 4px;
        color: {tokens["text"]};
        padding: 7px 9px;
        font-family: "Cascadia Mono", "Consolas";
        font-size: 12px;
    }}
    QLineEdit {{
        background: {tokens["field"]};
        border: 1px solid {tokens["line"]};
        border-radius: 5px;
        padding: 10px 12px;
        color: {tokens["text"]};
        font-size: 13px;
    }}
    QLineEdit:focus {{
        border-color: {tokens["accent"]};
    }}
    QListWidget {{
        background: {tokens["field"]};
        border: 1px solid {tokens["line"]};
        border-radius: 5px;
        outline: none;
        padding: 4px;
    }}
    QListWidget::item {{
        border-radius: 4px;
        padding: 9px 8px;
        margin: 2px;
    }}
    QListWidget::item:selected {{
        background: {tokens["accent_dim"]};
        color: {tokens["text"]};
    }}
    QListWidget::item:hover {{
        background: {tokens["panel_alt"]};
    }}
    QPushButton {{
        background: {tokens["panel_alt"]};
        border: 1px solid {tokens["line"]};
        border-radius: 5px;
        padding: 10px 12px;
        font-weight: 700;
    }}
    QPushButton:hover {{
        border-color: {tokens["accent"]};
        color: {tokens["accent"]};
    }}
    QPushButton:pressed {{
        background: {tokens["field"]};
    }}
    QPushButton:disabled {{
        color: {tokens["muted"]};
        border-color: {tokens["line"]};
    }}
    QPushButton#PrimaryButton {{
        background: {tokens["accent"]};
        border-color: {tokens["accent"]};
        color: {tokens["button_text"]};
    }}
    QPushButton#PrimaryButton:hover {{
        background: {tokens["good"]};
        color: {tokens["button_text"]};
    }}
    QCheckBox {{
        spacing: 8px;
        color: {tokens["text"]};
        padding: 3px 0;
    }}
    QCheckBox::indicator {{
        width: 15px;
        height: 15px;
        border: 1px solid {tokens["line"]};
        background: {tokens["field"]};
        border-radius: 3px;
    }}
    QCheckBox::indicator:checked {{
        background: {tokens["accent"]};
        border-color: {tokens["accent"]};
    }}
    QComboBox {{
        background: {tokens["field"]};
        border: 1px solid {tokens["line"]};
        border-radius: 5px;
        padding: 8px 10px;
    }}
    QComboBox:hover {{
        border-color: {tokens["accent"]};
    }}
    QComboBox QAbstractItemView {{
        background: {tokens["panel"]};
        border: 1px solid {tokens["line"]};
        selection-background-color: {tokens["accent_dim"]};
    }}
    QScrollBar:vertical {{
        background: {tokens["field"]};
        width: 12px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {tokens["line"]};
        border-radius: 5px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {tokens["accent_dim"]};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    """


class FetchThread(QThread):
    fetched = pyqtSignal(object)

    def __init__(self, service: ScpService, number: int) -> None:
        super().__init__()
        self.service = service
        self.number = number

    def run(self) -> None:
        self.fetched.emit(self.service.fetch_entry(self.number))


class ScpResearcherWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.service = ScpService.create()
        self.storage = AppStorage()
        profile = self.storage.load()

        self.favorites: set[int] = set(profile["favorites"])
        self.history: list[HistoryItem] = self.storage.parse_history(profile["history"])
        self.theme_name = profile["theme"] if profile["theme"] in THEMES else "amber"
        self.selected_entry: ScpEntry | None = None
        self.fetch_thread: FetchThread | None = None
        self.loading_number: int | None = None
        self.pulse_on = False
        self.loading_step = 0

        self.setWindowTitle("SCP Researcher // Foundation Internal Utility")
        self.resize(1320, 780)
        self.setMinimumSize(1100, 680)

        self._build_ui()
        self._bind_events()
        self.apply_theme(self.theme_name)
        self.refresh_results()
        self.refresh_history()

        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self.pulse_status)
        self.pulse_timer.start(600)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)

        main = QVBoxLayout(root)
        main.setContentsMargins(18, 18, 18, 18)
        main.setSpacing(12)

        header = QFrame()
        header.setObjectName("HeaderBand")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(14)

        title_stack = QVBoxLayout()
        title_stack.setSpacing(2)
        self.app_title = QLabel("SCP FOUNDATION // LIVE RESEARCH TERMINAL")
        self.app_title.setObjectName("AppTitle")
        self.mode_label = QLabel("MODE: CONTAINMENT ALERT")
        self.mode_label.setObjectName("ModeLabel")
        title_stack.addWidget(self.app_title)
        title_stack.addWidget(self.mode_label)

        self.status_label = QLabel("ACCESS LEVEL 3 // LIVE DATABASE READY")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        header_layout.addLayout(title_stack)
        header_layout.addItem(QSpacerItem(20, 1, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        header_layout.addWidget(self.status_label)
        main.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(12)
        main.addLayout(body, stretch=1)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setMinimumWidth(330)
        self.sidebar.setMaximumWidth(430)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(14, 14, 14, 14)
        sidebar_layout.setSpacing(10)

        sidebar_layout.addWidget(self._section_label("LIVE FILE REQUEST"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter SCP number, e.g. 173 or SCP-049")
        sidebar_layout.addWidget(self.search_input)
        self.fetch_button = QPushButton("FETCH FILE")
        self.fetch_button.setObjectName("PrimaryButton")
        sidebar_layout.addWidget(self.fetch_button)

        sidebar_layout.addWidget(self._section_label("CACHE FILTERS"))
        self.safe_filter = QCheckBox("Safe")
        self.euclid_filter = QCheckBox("Euclid")
        self.keter_filter = QCheckBox("Keter")
        filter_row = QHBoxLayout()
        filter_row.addWidget(self.safe_filter)
        filter_row.addWidget(self.euclid_filter)
        filter_row.addWidget(self.keter_filter)
        sidebar_layout.addLayout(filter_row)

        self.favorites_only = QCheckBox("Favorites only")
        sidebar_layout.addWidget(self.favorites_only)

        sidebar_layout.addWidget(self._section_label("RECENTLY CACHED FILES"))
        self.scp_list = QListWidget()
        self.scp_list.setUniformItemSizes(True)
        sidebar_layout.addWidget(self.scp_list, stretch=1)

        utility_row = QHBoxLayout()
        self.random_button = QPushButton("RANDOM FETCH")
        self.clear_search_button = QPushButton("CLEAR")
        utility_row.addWidget(self.random_button)
        utility_row.addWidget(self.clear_search_button)
        sidebar_layout.addLayout(utility_row)
        body.addWidget(self.sidebar, stretch=3)

        self.center_panel = QFrame()
        self.center_panel.setObjectName("CenterPanel")
        center_layout = QVBoxLayout(self.center_panel)
        center_layout.setContentsMargins(22, 22, 22, 22)
        center_layout.setSpacing(16)

        self.scp_code = QLabel("SCP-___")
        self.scp_code.setObjectName("ScpCode")
        self.scp_title = QLabel("No file loaded")
        self.scp_title.setObjectName("ScpTitle")
        self.scp_title.setWordWrap(True)

        meta_row = QHBoxLayout()
        self.class_pill = QLabel("CLASS: PENDING")
        self.class_pill.setObjectName("MetaPill")
        self.favorite_pill = QLabel("FAVORITE: NO")
        self.favorite_pill.setObjectName("MetaPill")
        self.url_pill = QLabel("WIKI LINK: STANDBY")
        self.url_pill.setObjectName("MetaPill")
        meta_row.addWidget(self.class_pill)
        meta_row.addWidget(self.favorite_pill)
        meta_row.addWidget(self.url_pill, stretch=1)

        detail_block = QFrame()
        detail_block.setObjectName("DetailBlock")
        detail_layout = QVBoxLayout(detail_block)
        detail_layout.setContentsMargins(18, 18, 18, 18)
        detail_layout.setSpacing(12)
        detail_layout.addWidget(self._section_label("LIVE FILE PREVIEW"))
        self.scp_description = QLabel("Enter a file number and press Fetch File. Pages are downloaded on demand and cached locally.")
        self.scp_description.setObjectName("ScpDescription")
        self.scp_description.setWordWrap(True)
        self.scp_description.setAlignment(Qt.AlignmentFlag.AlignTop)
        detail_layout.addWidget(self.scp_description)

        cache_block = QFrame()
        cache_block.setObjectName("DetailBlock")
        cache_layout = QVBoxLayout(cache_block)
        cache_layout.setContentsMargins(18, 18, 18, 18)
        cache_layout.setSpacing(10)
        cache_layout.addWidget(self._section_label("CACHE METADATA"))
        self.tags_label = QLabel("CACHE: EMPTY")
        self.tags_label.setObjectName("ScpDescription")
        self.tags_label.setWordWrap(True)
        cache_layout.addWidget(self.tags_label)

        center_layout.addWidget(self.scp_code)
        center_layout.addWidget(self.scp_title)
        center_layout.addLayout(meta_row)
        center_layout.addWidget(detail_block, stretch=2)
        center_layout.addWidget(cache_block, stretch=1)
        body.addWidget(self.center_panel, stretch=5)

        self.action_panel = QFrame()
        self.action_panel.setObjectName("ActionPanel")
        self.action_panel.setMinimumWidth(280)
        self.action_panel.setMaximumWidth(360)
        action_layout = QVBoxLayout(self.action_panel)
        action_layout.setContentsMargins(14, 14, 14, 14)
        action_layout.setSpacing(10)

        action_layout.addWidget(self._section_label("ACTIONS"))
        self.open_button = QPushButton("OPEN WIKI")
        self.open_button.setObjectName("PrimaryButton")
        self.favorite_button = QPushButton("ADD TO FAVORITES")
        self.copy_button = QPushButton("COPY WIKI URL")
        self.history_button = QPushButton("VIEW HISTORY")
        action_layout.addWidget(self.open_button)
        action_layout.addWidget(self.favorite_button)
        action_layout.addWidget(self.copy_button)
        action_layout.addWidget(self.history_button)

        action_layout.addWidget(self._section_label("THEME SYSTEM"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Amber Theme", "amber")
        self.theme_combo.addItem("Red Theme", "red")
        self.theme_combo.addItem("Blue Theme", "blue")
        self.theme_combo.setCurrentIndex(["amber", "red", "blue"].index(self.theme_name))
        action_layout.addWidget(self.theme_combo)

        self.history_stack = QStackedWidget()
        history_front = QFrame()
        history_front.setObjectName("HistoryBlock")
        front_layout = QVBoxLayout(history_front)
        front_layout.setContentsMargins(14, 14, 14, 14)
        front_layout.addWidget(self._section_label("RESEARCHER NOTES"))
        note = QLabel("Live SCP pages are fetched only when requested. Cached files are stored under %LOCALAPPDATA%/SCP Researcher/cache/.")
        note.setObjectName("ScpDescription")
        note.setWordWrap(True)
        front_layout.addWidget(note)
        front_layout.addStretch(1)

        history_back = QFrame()
        history_back.setObjectName("HistoryBlock")
        back_layout = QVBoxLayout(history_back)
        back_layout.setContentsMargins(14, 14, 14, 14)
        back_layout.setSpacing(10)
        back_layout.addWidget(self._section_label("ACCESS HISTORY"))
        self.history_list = QListWidget()
        back_layout.addWidget(self.history_list, stretch=1)
        self.clear_history_button = QPushButton("CLEAR HISTORY")
        back_layout.addWidget(self.clear_history_button)

        self.history_stack.addWidget(history_front)
        self.history_stack.addWidget(history_back)
        action_layout.addWidget(self.history_stack, stretch=1)
        body.addWidget(self.action_panel, stretch=2)

    def _bind_events(self) -> None:
        self.search_input.textChanged.connect(self.refresh_results)
        self.search_input.returnPressed.connect(self.fetch_from_search)
        self.fetch_button.clicked.connect(self.fetch_from_search)
        self.safe_filter.stateChanged.connect(self.refresh_results)
        self.euclid_filter.stateChanged.connect(self.refresh_results)
        self.keter_filter.stateChanged.connect(self.refresh_results)
        self.favorites_only.stateChanged.connect(self.refresh_results)
        self.scp_list.currentItemChanged.connect(self.select_current_item)
        self.scp_list.itemDoubleClicked.connect(self.fetch_list_item)
        self.open_button.clicked.connect(self.open_selected)
        self.favorite_button.clicked.connect(self.toggle_favorite)
        self.copy_button.clicked.connect(self.copy_selected_url)
        self.history_button.clicked.connect(self.toggle_history_panel)
        self.history_list.itemDoubleClicked.connect(self.fetch_history_item)
        self.random_button.clicked.connect(self.fetch_random)
        self.clear_search_button.clicked.connect(self.search_input.clear)
        self.clear_history_button.clicked.connect(self.clear_history)
        self.theme_combo.currentIndexChanged.connect(self.change_theme)

        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search_input.setFocus)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self.fetch_random)
        QShortcut(QKeySequence("Return"), self, activated=self.fetch_from_search)

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionLabel")
        return label

    def selected_classes(self) -> set[str]:
        classes = set()
        if self.safe_filter.isChecked():
            classes.add("Safe")
        if self.euclid_filter.isChecked():
            classes.add("Euclid")
        if self.keter_filter.isChecked():
            classes.add("Keter")
        return classes

    def refresh_results(self) -> None:
        current_number = self.selected_entry.number if self.selected_entry else None
        entries = self.service.search_cached(
            self.search_input.text(),
            favorites=self.favorites,
            only_favorites=self.favorites_only.isChecked(),
            object_classes=self.selected_classes(),
        )
        self.scp_list.blockSignals(True)
        self.scp_list.clear()

        for entry in entries:
            favorite = "*" if entry.number in self.favorites else " "
            availability = "" if entry.available else " [REDACTED]"
            item = QListWidgetItem(f"{favorite} {entry.code:<8} {entry.object_class:<11} {entry.title}{availability}")
            item.setData(Qt.ItemDataRole.UserRole, entry.number)
            item.setToolTip(entry.description)
            self.scp_list.addItem(item)

        self.scp_list.blockSignals(False)
        if entries:
            row = 0
            if current_number:
                for index, entry in enumerate(entries):
                    if entry.number == current_number:
                        row = index
                        break
            self.scp_list.setCurrentRow(row)
            self.set_selected(entries[row])
            self.set_status(f"{len(entries)} CACHED FILES AVAILABLE")
        elif self.selected_entry is None:
            self.set_empty_state()
            self.set_status("CACHE EMPTY // ENTER SCP NUMBER TO FETCH")
        else:
            self.set_status("NO CACHED FILES MATCH CURRENT FILTER")

    def select_current_item(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        entry = self.service.cached_entry(int(item.data(Qt.ItemDataRole.UserRole)))
        if entry is not None:
            self.set_selected(entry)

    def set_empty_state(self) -> None:
        self.scp_code.setText("SCP-___")
        self.scp_title.setText("No file loaded")
        self.scp_description.setText("Enter a file number and press Fetch File. Pages are downloaded on demand and cached locally.")
        self.class_pill.setText("CLASS: PENDING")
        self.class_pill.setStyleSheet("")
        self.favorite_pill.setText("FAVORITE: NO")
        self.url_pill.setText("WIKI LINK: STANDBY")
        self.tags_label.setText("CACHE: EMPTY")
        self.favorite_button.setText("ADD TO FAVORITES")

    def set_loading(self, number: int) -> None:
        self.loading_number = number
        self.loading_step = 0
        self.fetch_button.setEnabled(False)
        self.random_button.setEnabled(False)
        self.scp_code.setText(f"SCP-{number:03d}")
        self.scp_title.setText("CLASSIFIED FILE LOADING")
        self.scp_description.setText("Contacting SCP Wiki archive...\nDecrypting page body...\nExtracting object class and description...")
        self.class_pill.setText("CLASS: LOADING")
        self.class_pill.setStyleSheet("")
        self.url_pill.setText(self.service.url_for(number))
        self.tags_label.setText("CACHE: FETCHING LIVE SOURCE")
        self.set_status(f"FETCHING LIVE FILE // SCP-{number:03d}")

    def set_selected(self, entry: ScpEntry | None) -> None:
        self.selected_entry = entry
        if entry is None:
            self.set_empty_state()
            return

        favorite = entry.number in self.favorites
        self.scp_code.setText(entry.code)
        self.scp_title.setText(entry.title)
        self.scp_description.setText(entry.description)
        self.class_pill.setText(f"CLASS: {entry.object_class.upper()}")
        self.class_pill.setStyleSheet(f"color: {CLASS_COLORS.get(entry.object_class, CLASS_COLORS['Pending'])};")
        self.favorite_pill.setText(f"FAVORITE: {'YES' if favorite else 'NO'}")
        self.url_pill.setText(self.service.url_for(entry.number))
        cache_info = f"FETCHED: {entry.fetched_at or 'UNKNOWN'}"
        tag_info = ", ".join(entry.tags) if entry.tags else "NONE"
        self.tags_label.setText(f"{cache_info}\nTAGS: {tag_info}")
        self.favorite_button.setText("REMOVE FAVORITE" if favorite else "ADD TO FAVORITES")

    def fetch_from_search(self) -> None:
        try:
            number = self.service.normalize_number(self.search_input.text())
        except ScpInputError as exc:
            QMessageBox.information(self, "SCP Researcher", str(exc))
            return
        self.fetch_number(number)

    def fetch_list_item(self, item: QListWidgetItem) -> None:
        self.fetch_number(int(item.data(Qt.ItemDataRole.UserRole)))

    def fetch_history_item(self, item: QListWidgetItem) -> None:
        self.fetch_number(int(item.data(Qt.ItemDataRole.UserRole)))

    def fetch_random(self) -> None:
        number = random.randint(1, MAX_SCP_NUMBER)
        self.search_input.setText(f"SCP-{number:03d}")
        self.fetch_number(number)

    def fetch_number(self, number: int) -> None:
        if self.fetch_thread and self.fetch_thread.isRunning():
            self.set_status("FETCH ALREADY IN PROGRESS // PLEASE STAND BY")
            return
        self.set_loading(number)
        self.fetch_thread = FetchThread(self.service, number)
        self.fetch_thread.fetched.connect(self.handle_fetched_entry)
        self.fetch_thread.finished.connect(self.fetch_thread.deleteLater)
        self.fetch_thread.start()

    def handle_fetched_entry(self, entry: ScpEntry) -> None:
        self.fetch_button.setEnabled(True)
        self.random_button.setEnabled(True)
        self.loading_number = None
        self.set_selected(entry)
        self.add_history(entry)
        self.refresh_results()
        self._select_number_in_list(entry.number)
        if entry.available:
            self.set_status(f"LIVE FILE READY // {entry.code}")
        else:
            self.set_status(f"FILE UNAVAILABLE OR REDACTED // {entry.code}")

    def open_selected(self) -> None:
        if self.selected_entry is None:
            try:
                number = self.service.normalize_number(self.search_input.text())
            except ScpInputError:
                QMessageBox.information(self, "SCP Researcher", "Fetch or select a file before opening the wiki.")
                return
            self.service.open_in_browser(number)
            self.set_status(f"OPENED EXTERNAL WIKI LINK // SCP-{number:03d}")
            return
        self.service.open_in_browser(self.selected_entry.number)
        self.set_status(f"OPENED EXTERNAL WIKI LINK // {self.selected_entry.code}")

    def _select_number_in_list(self, number: int) -> None:
        for row in range(self.scp_list.count()):
            item = self.scp_list.item(row)
            if int(item.data(Qt.ItemDataRole.UserRole)) == number:
                self.scp_list.setCurrentRow(row)
                self.scp_list.scrollToItem(item)
                return

    def copy_selected_url(self) -> None:
        if self.selected_entry is None:
            try:
                number = self.service.normalize_number(self.search_input.text())
            except ScpInputError:
                QMessageBox.information(self, "SCP Researcher", "Fetch or select a file before copying a wiki URL.")
                return
        else:
            number = self.selected_entry.number
        QApplication.clipboard().setText(self.service.url_for(number))
        self.set_status(f"COPIED WIKI URL // SCP-{number:03d}")

    def toggle_favorite(self) -> None:
        if self.selected_entry is None:
            return
        number = self.selected_entry.number
        if number in self.favorites:
            self.favorites.remove(number)
            self.set_status(f"FAVORITE REMOVED // {self.selected_entry.code}")
        else:
            self.favorites.add(number)
            self.set_status(f"FAVORITE ADDED // {self.selected_entry.code}")
        self.save_profile()
        self.refresh_results()

    def add_history(self, entry: ScpEntry) -> None:
        self.history = [item for item in self.history if item.number != entry.number]
        self.history.insert(0, HistoryItem(number=entry.number, opened_at=datetime.now(), title=entry.title))
        self.history = self.history[:50]
        self.refresh_history()
        self.save_profile()

    def refresh_history(self) -> None:
        self.history_list.clear()
        for item in self.history:
            history_item = QListWidgetItem(f"{item.opened_at:%Y-%m-%d %H:%M}  {item.code}  {item.title}")
            history_item.setData(Qt.ItemDataRole.UserRole, item.number)
            self.history_list.addItem(history_item)

    def toggle_history_panel(self) -> None:
        next_index = 0 if self.history_stack.currentIndex() == 1 else 1
        self.history_stack.setCurrentIndex(next_index)
        self.history_button.setText("HIDE HISTORY" if next_index == 1 else "VIEW HISTORY")

    def clear_history(self) -> None:
        self.history.clear()
        self.refresh_history()
        self.save_profile()
        self.set_status("LOCAL ACCESS HISTORY CLEARED")

    def change_theme(self) -> None:
        theme = self.theme_combo.currentData()
        if theme:
            self.apply_theme(str(theme))
            self.save_profile()

    def apply_theme(self, theme: str) -> None:
        self.theme_name = theme
        tokens = THEMES[theme]
        self.setStyleSheet(build_qss(tokens))
        self.mode_label.setText(f"MODE: {tokens['mode']}")
        self.set_status(f"{tokens['mode']} // THEME ACTIVE")
        if self.selected_entry:
            self.set_selected(self.selected_entry)

    def pulse_status(self) -> None:
        self.pulse_on = not self.pulse_on
        tokens = THEMES[self.theme_name]
        color = tokens["accent"] if self.pulse_on else tokens["muted"]
        self.status_label.setStyleSheet(f"color: {color};")
        if self.loading_number is not None:
            marks = "." * (self.loading_step % 4)
            self.loading_step += 1
            self.set_status(f"FETCHING LIVE FILE // SCP-{self.loading_number:03d}{marks}")

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def save_profile(self) -> None:
        self.storage.save(favorites=self.favorites, history=self.history, redirect=True, theme=self.theme_name)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.save_profile()
        if self.fetch_thread and self.fetch_thread.isRunning():
            self.fetch_thread.quit()
            self.fetch_thread.wait(1500)
        super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("SCP Researcher")
    app.setApplicationVersion("3.1.0")
    app.setFont(QFont("Segoe UI", 10))
    window = ScpResearcherWindow()
    window.show()
    sys.exit(app.exec())
