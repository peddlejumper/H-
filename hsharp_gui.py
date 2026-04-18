"""
H# GUI Module - Powerful GUI window functionality based on PyQt5
Provides easy-to-use GUI components for H# programs
"""
import sys
import os
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                             QTextEdit, QComboBox, QCheckBox, QRadioButton,
                             QSlider, QProgressBar, QFileDialog, QMessageBox,
                             QGridLayout, QFormLayout, QTabWidget, QSplitter,
                             QGroupBox, QSpinBox, QDoubleSpinBox, QDateEdit,
                             QTimeEdit, QDateTimeEdit, QListWidget, QTreeWidget,
                             QTableWidget, QHeaderView, QToolBar, QAction,
                             QMenuBar, QStatusBar, QDialog, QInputDialog)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QIcon, QPixmap


class HSharpGUI:
    """Main GUI class for H# language"""
    
    def __init__(self):
        self.app = None
        self.windows = []
        self._ensure_app()
    
    def _ensure_app(self):
        """Ensure QApplication exists"""
        if self.app is None:
            self.app = QApplication.instance()
            if self.app is None:
                self.app = QApplication(sys.argv)
    
    def create_window(self, title="H# Window", width=800, height=600):
        """Create a new main window"""
        window = HSharpWindow(title, width, height)
        self.windows.append(window)
        return window
    
    def show_message(self, title, message, icon="info"):
        """Show a message box"""
        msg_box = QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        if icon == "info":
            msg_box.setIcon(QMessageBox.Information)
        elif icon == "warning":
            msg_box.setIcon(QMessageBox.Warning)
        elif icon == "error":
            msg_box.setIcon(QMessageBox.Critical)
        elif icon == "question":
            msg_box.setIcon(QMessageBox.Question)
        
        msg_box.exec_()
    
    def ask_question(self, title, question, default=""):
        """Ask user a question and return answer"""
        text, ok = QInputDialog.getText(None, title, question, text=default)
        if ok:
            return text
        return None
    
    def select_file(self, title="Select File", filter="All Files (*)"):
        """Open file selection dialog"""
        file_path, _ = QFileDialog.getOpenFileName(None, title, "", filter)
        return file_path if file_path else None
    
    def select_directory(self, title="Select Directory"):
        """Open directory selection dialog"""
        dir_path = QFileDialog.getExistingDirectory(None, title)
        return dir_path if dir_path else None
    
    def run(self):
        """Start the GUI event loop"""
        if self.app:
            return self.app.exec_()
        return 0


class HSharpWindow:
    """Represents a GUI window in H#"""
    
    def __init__(self, title="H# Window", width=800, height=600):
        self.window = QMainWindow()
        self.window.setWindowTitle(title)
        self.window.resize(width, height)
        
        # Central widget and layout
        self.central_widget = QWidget()
        self.window.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Components storage
        self.components = {}
        self.event_handlers = {}
        
        # Menu bar
        self.menu_bar = self.window.menuBar()
        self.menus = {}
        
        # Status bar
        self.status_bar = self.window.statusBar()
        self.status_bar.showMessage("Ready")
        
        # Toolbar
        self.toolbar = self.window.addToolBar("Main Toolbar")
        
        # Current layout for adding widgets
        self.current_layout = self.main_layout
        self.layout_stack = [self.main_layout]
    
    def set_status(self, message):
        """Set status bar message"""
        self.status_bar.showMessage(message)
    
    def add_menu(self, name):
        """Add a menu to the menu bar"""
        menu = self.menu_bar.addMenu(name)
        self.menus[name] = menu
        return menu
    
    def add_menu_action(self, menu_name, action_name, callback=None):
        """Add an action to a menu"""
        if menu_name in self.menus:
            action = QAction(action_name, self.window)
            if callback:
                action.triggered.connect(callback)
            self.menus[menu_name].addAction(action)
            return action
        return None
    
    def add_toolbar_button(self, text, callback=None, icon=None):
        """Add a button to the toolbar"""
        action = QAction(text, self.window)
        if callback:
            action.triggered.connect(callback)
        if icon:
            action.setIcon(QIcon(icon))
        self.toolbar.addAction(action)
        return action
    
    def add_label(self, text, name=None):
        """Add a label widget"""
        label = QLabel(text)
        self.current_layout.addWidget(label)
        if name:
            self.components[name] = label
        return label
    
    def add_button(self, text, callback=None, name=None):
        """Add a button widget"""
        button = QPushButton(text)
        if callback:
            button.clicked.connect(callback)
        self.current_layout.addWidget(button)
        if name:
            self.components[name] = button
        return button
    
    def add_text_input(self, placeholder="", name=None):
        """Add a text input field"""
        text_input = QLineEdit()
        if placeholder:
            text_input.setPlaceholderText(placeholder)
        self.current_layout.addWidget(text_input)
        if name:
            self.components[name] = text_input
        return text_input
    
    def add_text_area(self, name=None):
        """Add a multi-line text area"""
        text_area = QTextEdit()
        self.current_layout.addWidget(text_area)
        if name:
            self.components[name] = text_area
        return text_area
    
    def add_combo_box(self, items=None, name=None):
        """Add a combo box (dropdown)"""
        combo = QComboBox()
        if items:
            combo.addItems(items)
        self.current_layout.addWidget(combo)
        if name:
            self.components[name] = combo
        return combo
    
    def add_checkbox(self, text, checked=False, name=None):
        """Add a checkbox"""
        checkbox = QCheckBox(text)
        checkbox.setChecked(checked)
        self.current_layout.addWidget(checkbox)
        if name:
            self.components[name] = checkbox
        return checkbox
    
    def add_slider(self, min_val=0, max_val=100, value=50, name=None):
        """Add a slider"""
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(value)
        self.current_layout.addWidget(slider)
        if name:
            self.components[name] = slider
        return slider
    
    def add_progress_bar(self, name=None):
        """Add a progress bar"""
        progress = QProgressBar()
        self.current_layout.addWidget(progress)
        if name:
            self.components[name] = progress
        return progress
    
    def add_spin_box(self, min_val=0, max_val=100, value=0, name=None):
        """Add a spin box"""
        spin = QSpinBox()
        spin.setMinimum(min_val)
        spin.setMaximum(max_val)
        spin.setValue(value)
        self.current_layout.addWidget(spin)
        if name:
            self.components[name] = spin
        return spin
    
    def start_horizontal_layout(self):
        """Start a horizontal layout"""
        h_layout = QHBoxLayout()
        self.current_layout.addLayout(h_layout)
        self.layout_stack.append(h_layout)
        self.current_layout = h_layout
    
    def start_vertical_layout(self):
        """Start a vertical layout"""
        v_layout = QVBoxLayout()
        self.current_layout.addLayout(v_layout)
        self.layout_stack.append(v_layout)
        self.current_layout = v_layout
    
    def end_layout(self):
        """End current layout and return to parent"""
        if len(self.layout_stack) > 1:
            self.layout_stack.pop()
            self.current_layout = self.layout_stack[-1]
    
    def add_spacer(self):
        """Add a spacer"""
        from PyQt5.QtWidgets import QSpacerItem, QSizePolicy
        spacer = QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.current_layout.addItem(spacer)
    
    def add_stretch(self):
        """Add stretch to current layout"""
        self.current_layout.addStretch()
    
    def get_component(self, name):
        """Get a component by name"""
        return self.components.get(name)
    
    def get_text(self, name):
        """Get text from a component"""
        comp = self.components.get(name)
        if isinstance(comp, QLineEdit):
            return comp.text()
        elif isinstance(comp, QTextEdit):
            return comp.toPlainText()
        elif isinstance(comp, QLabel):
            return comp.text()
        return ""
    
    def set_text(self, name, text):
        """Set text of a component"""
        comp = self.components.get(name)
        if isinstance(comp, QLineEdit):
            comp.setText(text)
        elif isinstance(comp, QTextEdit):
            comp.setText(text)
        elif isinstance(comp, QLabel):
            comp.setText(text)
    
    def show(self):
        """Show the window"""
        self.window.show()
    
    def hide(self):
        """Hide the window"""
        self.window.hide()
    
    def close(self):
        """Close the window"""
        self.window.close()


# Global GUI instance
_gui_instance = None

def get_gui():
    """Get or create global GUI instance"""
    global _gui_instance
    if _gui_instance is None:
        _gui_instance = HSharpGUI()
    return _gui_instance


# Convenience functions for H# language
def create_window(title="H# Window", width=800, height=600):
    """Create a new window (convenience function)"""
    gui = get_gui()
    return gui.create_window(title, width, height)

def show_message(title, message, icon="info"):
    """Show a message box (convenience function)"""
    gui = get_gui()
    gui.show_message(title, message, icon)

def ask_question(title, question, default=""):
    """Ask user a question (convenience function)"""
    gui = get_gui()
    return gui.ask_question(title, question, default)

def select_file(title="Select File", filter="All Files (*)"):
    """Select a file (convenience function)"""
    gui = get_gui()
    return gui.select_file(title, filter)

def select_directory(title="Select Directory"):
    """Select a directory (convenience function)"""
    gui = get_gui()
    return gui.select_directory(title)

def run_gui():
    """Run the GUI event loop (convenience function)"""
    gui = get_gui()
    return gui.run()
