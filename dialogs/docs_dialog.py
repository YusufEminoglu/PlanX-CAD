# -*- coding: utf-8 -*-
"""HTML documentation dialog for PlanX CAD."""

import os

from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QTextBrowser, QPushButton
from qgis.PyQt.QtCore import QUrl, Qt


class DocsDialog(QDialog):
    def __init__(self, plugin_dir, parent=None):
        super().__init__(parent)
        self.plugin_dir = plugin_dir
        self.setWindowTitle("PlanX CAD - Command Reference")
        self.resize(920, 700)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget(self)
        tabs.addTab(self._make_browser("command_reference.html"), "Commands")
        tabs.addTab(self._make_browser("shortcuts.html"), "Shortcuts")
        layout.addWidget(tabs)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

    def _make_browser(self, html_name):
        browser = QTextBrowser(self)
        html_path = os.path.join(self.plugin_dir, "docs", html_name)
        if os.path.exists(html_path):
            browser.setSource(QUrl.fromLocalFile(html_path))
        else:
            browser.setHtml(
                "<h3>Documentation file missing</h3>"
                f"<p>Expected: {html_path}</p>"
            )
        return browser
