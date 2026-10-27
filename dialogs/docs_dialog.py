# -*- coding: utf-8 -*-
"""HTML documentation dialog for PlanX CAD."""

import os

from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QTextBrowser, QPushButton
from qgis.PyQt.QtCore import QUrl, Qt


class DocsDialog(QDialog):
    def __init__(self, plugin_dir, parent=None, initial_tab=0, command_anchor=None):
        super().__init__(parent)
        self.plugin_dir = plugin_dir
        self.initial_tab = int(initial_tab)
        self.command_anchor = command_anchor or ""
        self.setWindowTitle("CAD Drafting Toolset - Command Reference")
        self.resize(920, 700)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget(self)
        self.commands_browser = self._make_browser("command_reference.html", self.command_anchor)
        self.shortcuts_browser = self._make_browser("shortcuts.html")
        self.tabs.addTab(self.commands_browser, "Commands")
        self.tabs.addTab(self.shortcuts_browser, "Shortcuts")
        self.tabs.setCurrentIndex(0 if self.initial_tab < 0 else min(self.initial_tab, 1))
        layout.addWidget(self.tabs)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _make_browser(self, html_name, anchor=""):
        browser = QTextBrowser(self)
        html_path = os.path.join(self.plugin_dir, "docs", html_name)
        if os.path.exists(html_path):
            if anchor:
                url = QUrl.fromLocalFile(html_path)
                url.setFragment(anchor)
                browser.setSource(url)
            else:
                browser.setSource(QUrl.fromLocalFile(html_path))
        else:
            browser.setHtml(
                "<h3>Documentation file missing</h3>"
                f"<p>Expected: {html_path}</p>"
            )
        return browser
