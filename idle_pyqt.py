import sys
import os
import json
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QFont, QColor, QTextFormat, QTextCharFormat, QSyntaxHighlighter, QTextCursor, QPixmap, QKeySequence
from PyQt5.QtCore import QRect, QRegExp, Qt, QFileInfo
from PyQt5.QtWidgets import (QDockWidget, QLineEdit, QTabWidget, QTreeWidget, 
                             QTreeWidgetItem, QFileDialog, QDialog, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QCompleter, 
                             QToolBar, QAction, QSplitter,
                             QInputDialog, QMessageBox)

from lexer import Lexer
from parser import Parser
from interpreter import Interpreter
from compiler import Compiler
from bytecode import VM


class EmittingStream(QtCore.QObject):
    textWritten = QtCore.pyqtSignal(str)
    def write(self, text):
        if not text:
            return
        # Schedule emission via the Qt event loop to avoid calling
        # into signal handlers directly from arbitrary Python code
        # and prevent exceptions from propagating into PyQt internals.
        try:
            QtCore.QTimer.singleShot(0, lambda t=str(text): self.textWritten.emit(t))
        except Exception:
            try:
                self.textWritten.emit(str(text))
            except Exception:
                import traceback
                sys.__stderr__.write(traceback.format_exc())

    def flush(self):
        pass


class IDLEWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('H# interpreter IDLE')
        self.resize(1200, 700)

        # Create central widget with splitter for file browser and editor
        central_splitter = QSplitter(Qt.Horizontal)
        
        # File browser dock (left side)
        self.file_browser_widget = QtWidgets.QWidget()
        file_browser_layout = QVBoxLayout(self.file_browser_widget)
        file_browser_layout.setContentsMargins(5, 5, 5, 5)
        
        browser_header = QtWidgets.QHBoxLayout()
        browser_header.addWidget(QLabel('Project Files:'))
        refresh_btn = QPushButton('⟳')
        refresh_btn.setFixedSize(24, 24)
        refresh_btn.setToolTip('Refresh file list')
        refresh_btn.clicked.connect(self.refresh_file_tree)
        browser_header.addWidget(refresh_btn)
        file_browser_layout.addLayout(browser_header)
        
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(['Name', 'Type'])
        self.file_tree.setColumnWidth(0, 150)
        self.file_tree.itemDoubleClicked.connect(self.open_file_from_tree)
        file_browser_layout.addWidget(self.file_tree)
        
        central_splitter.addWidget(self.file_browser_widget)
        
        # Editor area (right side) - using tab widget for multiple files
        editor_container = QtWidgets.QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        
        # Tab widget for multiple editors
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        # Create first tab
        self.create_new_tab()
        
        btn_layout = QtWidgets.QHBoxLayout()
        # Simplified toolbar - only essential buttons
        self.open_folder_btn = QtWidgets.QPushButton('📁 Open Folder')
        self.save_btn = QtWidgets.QPushButton('💾 Save')
        self.compile_run_btn = QtWidgets.QPushButton('▶ Compile & Run')
        self.compile_run_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 5px 10px;")
        self.stop_btn = QtWidgets.QPushButton('⏹ Stop')
        self.clear_btn = QtWidgets.QPushButton('🗑 Clear')
        
        for b in (self.open_folder_btn, self.save_btn, self.compile_run_btn, self.stop_btn, self.clear_btn):
            btn_layout.addWidget(b)
        
        btn_layout.addStretch()  # Push buttons to the left

        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        out_font = self.output.font()
        out_font.setPointSize(11)
        self.output.setFont(out_font)

        editor_layout.addLayout(btn_layout)
        editor_layout.addWidget(self.tab_widget)
        editor_layout.addWidget(QtWidgets.QLabel('Output:'))
        editor_layout.addWidget(self.output)
        
        central_splitter.addWidget(editor_container)
        central_splitter.setStretchFactor(0, 0)  # File browser doesn't stretch
        central_splitter.setStretchFactor(1, 1)  # Editor area stretches
        
        # Set initial widths
        central_splitter.setSizes([250, 950])

        self.setCentralWidget(central_splitter)

        # menu bar - simplified
        menubar = self.menuBar()
        file_menu = menubar.addMenu('File')
        edit_menu = menubar.addMenu('Edit')
        run_menu = menubar.addMenu('Run')
        tools_menu = menubar.addMenu('Tools')

        # File actions - only essential
        new_tab_action = QtWidgets.QAction('New Tab', self)
        new_tab_action.setShortcut(QKeySequence.New)
        new_tab_action.triggered.connect(lambda: self.create_new_tab())
        file_menu.addAction(new_tab_action)
        
        open_folder_action = QtWidgets.QAction('Open Folder', self)
        open_folder_action.triggered.connect(self.open_folder)
        file_menu.addAction(open_folder_action)
        
        file_menu.addSeparator()
        
        save_action = QtWidgets.QAction('Save', self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        # Edit actions
        find_action = QtWidgets.QAction('Find', self)
        find_action.setShortcut(QKeySequence.Find)
        find_action.triggered.connect(self.show_find_dialog)
        edit_menu.addAction(find_action)
        
        replace_action = QtWidgets.QAction('Replace', self)
        replace_action.setShortcut(QKeySequence.Replace)
        replace_action.triggered.connect(self.show_replace_dialog)
        edit_menu.addAction(replace_action)

        # Run actions - simplified to essentials
        compile_run_action = QtWidgets.QAction('Compile & Run', self)
        compile_run_action.setShortcut('F5')
        compile_run_action.triggered.connect(self.compile_and_run)
        run_menu.addAction(compile_run_action)
        
        stop_action = QtWidgets.QAction('Stop', self)
        stop_action.setShortcut('Ctrl+.')
        stop_action.triggered.connect(self.stop_process)
        run_menu.addAction(stop_action)

        # Tools - only important ones
        self.shell_action = QtWidgets.QAction('Shell Mode', self, checkable=True)
        self.shell_action.triggered.connect(self.toggle_shell)
        tools_menu.addAction(self.shell_action)

        self.debug_action = QtWidgets.QAction('Debug Mode', self, checkable=True)
        self.debug_action.triggered.connect(self.toggle_debug_mode)
        tools_menu.addAction(self.debug_action)
        
        # connections - simplified
        self.open_folder_btn.clicked.connect(self.open_folder)
        self.save_btn.clicked.connect(self.save_file)
        self.compile_run_btn.clicked.connect(self.compile_and_run)
        self.clear_btn.clicked.connect(self.output.clear)
        self.stop_btn.clicked.connect(self.stop_process)

        self.current_file = None
        self.proc = None
        self.shell_proc = None
        self.shell_dock = None
        self.debug_mode = False
        self.debug_dock = None
        self.debug_vars_widget = None
        
        # Debug toolbar buttons (initially hidden)
        self.step_btn = QtWidgets.QPushButton('Step Into')
        self.step_over_btn = QtWidgets.QPushButton('Step Over')
        self.continue_btn = QtWidgets.QPushButton('Continue')
        self.step_btn.setVisible(False)
        self.step_over_btn.setVisible(False)
        self.continue_btn.setVisible(False)
        btn_layout.addWidget(self.step_btn)
        btn_layout.addWidget(self.step_over_btn)
        btn_layout.addWidget(self.continue_btn)
        self.step_btn.clicked.connect(self.debug_step_into)
        self.step_over_btn.clicked.connect(self.debug_step_over)
        self.continue_btn.clicked.connect(self.debug_continue)

        # redirect stdout
        self.stream = EmittingStream()
        self.stream.textWritten.connect(self.append_output)
        
        # Setup auto-completion for editor
        completion_words = [
            'let', 'fn', 'return', 'while', 'if', 'else', 'for', 'in', 
            'print', 'import', 'class', 'extends', 'new', 'private',
            'true', 'false', 'and', 'or', 'not', 'interface', 'implements'
        ]
        completer = QCompleter(completion_words)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.get_current_editor().setCompleter(completer)
        
        # Initialize current file tracking
        self.current_file = None

    @property
    def editor(self):
        """Get the current active editor"""
        return self.get_current_editor()
        
    def get_current_editor(self):
        """Get the current active editor widget"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            return current_tab
        return None
        
    def create_new_tab(self, filepath=None, content=''):
        """Create a new editor tab"""
        editor = CodeEditor()
        font = QFont('Consolas' if sys.platform == 'win32' else 'Menlo')
        font.setPointSize(12)
        editor.setFont(font)
        
        # Setup auto-completion for this editor
        completion_words = [
            'let', 'fn', 'return', 'while', 'if', 'else', 'for', 'in', 
            'print', 'import', 'class', 'extends', 'new', 'private',
            'true', 'false', 'and', 'or', 'not', 'interface', 'implements'
        ]
        completer = QCompleter(completion_words)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        editor.setCompleter(completer)
        
        if content:
            editor.setPlainText(content)
            
        # Determine tab name
        if filepath:
            tab_name = os.path.basename(filepath)
            editor.file_path = filepath
        else:
            tab_name = f'Untitled-{self.tab_widget.count() + 1}'
            editor.file_path = None
            
        # Add tab
        self.tab_widget.addTab(editor, tab_name)
        self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)
        
        return editor
        
    def close_tab(self, index):
        """Close a tab"""
        if self.tab_widget.count() <= 1:
            # Don't close the last tab
            QMessageBox.information(self, 'Info', 'Cannot close the last tab')
            return
        self.tab_widget.removeTab(index)
        
    def on_tab_changed(self, index):
        """Handle tab change event"""
        editor = self.tab_widget.widget(index)
        if editor and hasattr(editor, 'file_path'):
            self.current_file = editor.file_path

    def append_output(self, text):
        try:
            self.output.moveCursor(QTextCursor.End)
            self.output.insertPlainText(text)
        except Exception:
            # Avoid allowing exceptions raised while updating the GUI to
            # bubble into PyQt internals (which can call qFatal).
            import traceback
            sys.__stderr__.write('Exception in append_output:\n')
            sys.__stderr__.write(traceback.format_exc())

    def open_file(self, path=None):
        """Open a file in a new tab"""
        try:
            if not path:
                path, _ = QtWidgets.QFileDialog.getOpenFileName(
                    self, 
                    'Open H# file', 
                    os.getcwd(),
                    'H# Files (*.hto);;All Files (*)'
                )
            
            if not path:
                return
                
            # Check if file is already open
            for i in range(self.tab_widget.count()):
                editor = self.tab_widget.widget(i)
                if hasattr(editor, 'file_path') and editor.file_path == path:
                    self.tab_widget.setCurrentIndex(i)
                    return
                    
            # Open in new tab
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.create_new_tab(filepath=path, content=content)
            self.current_file = path
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to open file: {e}')
            import traceback
            traceback.print_exc()
            
    def open_folder(self):
        """Open a folder and display its contents in file browser"""
        try:
            folder_path = QtWidgets.QFileDialog.getExistingDirectory(
                self, 
                'Open Folder', 
                os.getcwd(),
                QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks
            )
            if folder_path:
                # Change to the selected folder
                os.chdir(folder_path)
                # Refresh file tree to show folder contents
                self.refresh_file_tree()
                # Update window title
                self.setWindowTitle(f'H# interpreter IDLE - {folder_path}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to open folder: {e}')
            import traceback
            traceback.print_exc()
            
    def open_file_from_tree(self, item, column):
        """Open file when double-clicked in file tree"""
        if item.childCount() == 0:  # It's a file, not a directory
            file_path = item.data(0, Qt.UserRole)
            if file_path and os.path.exists(file_path):
                self.open_file(file_path)

    def save_file(self):
        """Save current file"""
        editor = self.get_current_editor()
        if not editor:
            return
            
        if editor.file_path:
            with open(editor.file_path, 'w', encoding='utf-8') as f:
                f.write(editor.toPlainText())
        else:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save H# file', '.', 'H# Files (*.hto)')
            if path:
                editor.file_path = path
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(editor.toPlainText())
                # Update tab name
                index = self.tab_widget.indexOf(editor)
                self.tab_widget.setTabText(index, os.path.basename(path))
                self.current_file = path
                
    def refresh_file_tree(self):
        """Refresh the file tree with current directory contents"""
        try:
            self.file_tree.clear()
            
            # Get current directory or use working directory
            current_dir = os.getcwd()
            if self.current_file:
                current_dir = os.path.dirname(self.current_file)
                
            # Add root item
            root_item = QTreeWidgetItem([os.path.basename(current_dir), 'Folder'])
            root_item.setData(0, Qt.UserRole, current_dir)
            self.file_tree.addTopLevelItem(root_item)
            root_item.setExpanded(True)
            
            # Scan directory
            self._scan_directory(current_dir, root_item, depth=0)
        except Exception as e:
            import traceback
            traceback.print_exc()
        
    def _scan_directory(self, dir_path, parent_item, depth=0):
        """Recursively scan directory and populate tree"""
        try:
            # Limit recursion depth to avoid performance issues
            if depth > 2:
                return
                
            items = sorted(os.listdir(dir_path))
            for item_name in items:
                item_path = os.path.join(dir_path, item_name)
                
                # Skip hidden files and common non-source directories
                if item_name.startswith('.') or item_name in ('__pycache__', 'dist', '.git', 'node_modules', 'venv', '.venv'):
                    continue
                    
                if os.path.isdir(item_path):
                    # Add directory
                    dir_item = QTreeWidgetItem([item_name, 'Folder'])
                    dir_item.setData(0, Qt.UserRole, item_path)
                    parent_item.addChild(dir_item)
                    
                    # Recursively scan subdirectory
                    self._scan_directory(item_path, dir_item, depth + 1)
                elif item_name.endswith(('.hto', '.hbc', '.py')):
                    # Add source file
                    file_item = QTreeWidgetItem([item_name, 'File'])
                    file_item.setData(0, Qt.UserRole, item_path)
                    parent_item.addChild(file_item)
        except PermissionError:
            pass
        except Exception as e:
            # Silently ignore other errors during directory scanning
            pass

    def run_source(self):
        # Run current editor content in a subprocess so it can be terminated
        code = self.editor.toPlainText()
        if not code.strip():
            return
        # write to temp file
        import tempfile
        tf = tempfile.NamedTemporaryFile(delete=False, suffix='.hto')
        tf.write(code.encode('utf-8'))
        tf.close()
        cmd = [sys.executable, os.path.join(os.path.dirname(__file__), 'hsharp.py'), tf.name]
        self.start_process(cmd)
        
    def compile_and_run(self):
        """Compile source to bytecode and run it in one step"""
        code = self.editor.toPlainText()
        if not code.strip():
            QMessageBox.information(self, 'Info', 'No code to compile and run')
            return
            
        self.output.clear()
        old_stdout = sys.stdout
        sys.stdout = self.stream
        
        tf = None
        try:
            # Step 1: Compile to bytecode
            print('=== Compiling ===')
            lexer = Lexer(code)
            parser = Parser(lexer)
            program = parser.parse()
            compiler = Compiler()
            bc = compiler.compile(program)
            
            # Save bytecode to temp file
            import tempfile
            tf = tempfile.NamedTemporaryFile(delete=False, suffix='.hbc', mode='w')
            json.dump(bc, tf)
            tf.close()
            
            print(f'✓ Compilation successful')
            print(f'=== Running ===')
            
            # Step 2: Run the bytecode
            # Restore stdout before starting subprocess
            sys.stdout = old_stdout
            self.start_process([sys.executable, os.path.join(os.path.dirname(__file__), 'hsharp.py'), '--run-bc', tf.name], clear_output=False)
            
        except Exception as e:
            # Show error in output window
            try:
                print(f'✗ Compilation error: {e}')
                import traceback
                print(traceback.format_exc())
            except:
                # If printing fails, try to print simple error message
                try:
                    self.output.appendPlainText(f'✗ Compilation error: {str(e)}')
                except:
                    pass
            finally:
                # Always restore stdout
                sys.stdout = old_stdout
                # Clean up temp file if it was created
                if tf and hasattr(tf, 'name'):
                    try:
                        os.unlink(tf.name)
                    except:
                        pass

    def compile_bc(self):
        code = self.editor.toPlainText()
        self.output.clear()
        old_stdout = sys.stdout
        sys.stdout = self.stream
        try:
            lexer = Lexer(code)
            parser = Parser(lexer)
            program = parser.parse()
            compiler = Compiler()
            bc = compiler.compile(program)
            out = (self.current_file or 'untitled.hto').rsplit('.', 1)[0] + '.hbc'
            with open(out, 'w', encoding='utf-8') as f:
                json.dump(bc, f)
            print(f'Wrote bytecode to {out}')
        except Exception as e:
            print(f'Compilation error: {e}')
        finally:
            sys.stdout = old_stdout

    def run_bc_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open HBC file', '.', 'Bytecode Files (*.hbc);;All Files (*)')
        if not path:
            return
        # run VM via hsharp.py --run-bc for safety
        self.start_process([sys.executable, os.path.join(os.path.dirname(__file__), 'hsharp.py'), '--run-bc', path])

    def syntax_check(self):
        code = self.editor.toPlainText()
        self.output.clear()
        try:
            lexer = Lexer(code)
            parser = Parser(lexer)
            parser.parse()
            print('Syntax OK')
        except Exception as e:
            print(f'Syntax Error: {e}')

    def run_selection(self):
        text = self.editor.textCursor().selectedText()
        if not text.strip():
            return
        import tempfile
        tf = tempfile.NamedTemporaryFile(delete=False, suffix='.hto')
        tf.write(text.encode('utf-8'))
        tf.close()
        cmd = [sys.executable, os.path.join(os.path.dirname(__file__), 'hsharp.py'), tf.name]
        self.start_process(cmd)

    def start_process(self, cmd, clear_output=True):
        # ensure previous process stopped
        if self.proc and self.proc.state() != QtCore.QProcess.NotRunning:
            self.proc.kill()
            self.proc = None
        if clear_output:
            self.output.clear()
        self.proc = QtCore.QProcess(self)
        self.proc.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._read_proc)
        self.proc.readyReadStandardError.connect(self._read_proc)
        self.proc.finished.connect(self._proc_finished)
        try:
            # inject debug flag if enabled
            if self.debug_mode and '--debug' not in cmd:
                cmd = cmd[:1] + ['--debug'] + cmd[1:]
            self.proc.start(cmd[0], cmd[1:])
        except Exception as e:
            # Use append_output directly to avoid stdout redirection issues
            try:
                self.output.appendPlainText(f'Failed to start process: {e}')
            except:
                pass

    def _read_proc(self):
        if not self.proc:
            return
        out = bytes(self.proc.readAllStandardOutput()).decode('utf-8', errors='replace')
        if out:
            self.append_output(out)

    def _proc_finished(self, exitCode, exitStatus):
        self.append_output(f"\nProcess finished with code {exitCode}\n")

    def stop_process(self):
        if self.proc and self.proc.state() != QtCore.QProcess.NotRunning:
            self.proc.terminate()
            QtCore.QTimer.singleShot(500, lambda: self.proc.kill())

    # Shell mode: start/stop REPL in a dock widget
    def toggle_shell(self, checked):
        if checked:
            self.open_shell()
        else:
            self.close_shell()

    def open_shell(self):
        if self.shell_dock and not self.shell_dock.isHidden():
            self.shell_dock.show()
            return
        # create dock
        self.shell_dock = QDockWidget('H# Shell', self)
        shell_widget = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(shell_widget)
        self.shell_output = QtWidgets.QPlainTextEdit()
        self.shell_output.setReadOnly(True)
        self.shell_input = QLineEdit()
        v.addWidget(self.shell_output)
        v.addWidget(self.shell_input)
        self.shell_dock.setWidget(shell_widget)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.shell_dock)
        # start REPL process
        self.shell_proc = QtCore.QProcess(self)
        self.shell_proc.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.shell_proc.readyReadStandardOutput.connect(self._read_shell)
        self.shell_proc.finished.connect(lambda code, stat: self.shell_output.appendPlainText(f"Shell exited {code}"))
        cmd = [sys.executable, os.path.join(os.path.dirname(__file__), 'hsharp.py')]
        if self.debug_mode:
            cmd = cmd[:1] + ['--debug'] + cmd[1:]
        self.shell_proc.start(cmd[0], cmd[1:])
        self.shell_input.returnPressed.connect(self._send_shell_input)

    def close_shell(self):
        if self.shell_proc and self.shell_proc.state() != QtCore.QProcess.NotRunning:
            self.shell_proc.terminate()
            QtCore.QTimer.singleShot(300, lambda: self.shell_proc.kill())
        if self.shell_dock:
            self.shell_dock.hide()
        self.shell_action.setChecked(False)

    def _read_shell(self):
        if not self.shell_proc:
            return
        out = bytes(self.shell_proc.readAllStandardOutput()).decode('utf-8', errors='replace')
        if out:
            self.shell_output.insertPlainText(out)

    def _send_shell_input(self):
        if not self.shell_proc:
            return
        txt = self.shell_input.text() + '\n'
        try:
            self.shell_proc.write(txt.encode('utf-8'))
        except Exception:
            pass
        self.shell_input.clear()

    def toggle_debug_mode(self, checked):
        self.debug_mode = bool(checked)
        if checked:
            self.show_debug_panel()
            # Show debug buttons
            self.step_btn.setVisible(True)
            self.step_over_btn.setVisible(True)
            self.continue_btn.setVisible(True)
        else:
            if self.debug_dock:
                self.debug_dock.hide()
            # Hide debug buttons
            self.step_btn.setVisible(False)
            self.step_over_btn.setVisible(False)
            self.continue_btn.setVisible(False)
        
    def show_find_dialog(self):
        """Show find dialog"""
        dialog = FindReplaceDialog(self, mode='find')
        if dialog.exec_():
            text = dialog.get_search_text()
            case_sensitive = dialog.is_case_sensitive()
            if text:
                self.find_text(text, case_sensitive)
                
    def show_replace_dialog(self):
        """Show replace dialog"""
        dialog = FindReplaceDialog(self, mode='replace')
        if dialog.exec_():
            search_text = dialog.get_search_text()
            replace_text = dialog.get_replace_text()
            case_sensitive = dialog.is_case_sensitive()
            if search_text:
                self.replace_text(search_text, replace_text, case_sensitive)
                
    def find_text(self, text, case_sensitive=False):
        """Find text in editor"""
        flags = QTextDocument.FindFlags()
        if not case_sensitive:
            flags |= QTextDocument.FindCaseInsensitively
            
        cursor = self.editor.document().find(text, self.editor.textCursor(), flags)
        if not cursor.isNull():
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()
        else:
            # Wrap around to beginning
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor = self.editor.document().find(text, cursor, flags)
            if not cursor.isNull():
                self.editor.setTextCursor(cursor)
                self.editor.ensureCursorVisible()
            else:
                QMessageBox.information(self, 'Find', f'"{text}" not found')
                
    def replace_text(self, search_text, replace_text, case_sensitive=False):
        """Replace text in editor"""
        flags = QTextDocument.FindFlags()
        if not case_sensitive:
            flags |= QTextDocument.FindCaseInsensitively
            
        cursor = self.editor.textCursor()
        found = self.editor.document().find(search_text, cursor, flags)
        
        if not found.isNull():
            self.editor.setTextCursor(found)
            found.insertText(replace_text)
        else:
            # Try from beginning
            cursor.movePosition(QTextCursor.Start)
            found = self.editor.document().find(search_text, cursor, flags)
            if not found.isNull():
                self.editor.setTextCursor(found)
                found.insertText(replace_text)
            else:
                QMessageBox.information(self, 'Replace', f'"{search_text}" not found')
                
    def show_debug_panel(self):
        """Show debug panel with variables and breakpoints"""
        if self.debug_dock and not self.debug_dock.isHidden():
            self.debug_dock.show()
            return
            
        # Create debug dock widget
        self.debug_dock = QDockWidget('Debug', self)
        debug_widget = QtWidgets.QWidget()
        v_layout = QVBoxLayout(debug_widget)
        
        # Variables tree
        vars_label = QLabel('Variables:')
        self.debug_vars_widget = QTreeWidget()
        self.debug_vars_widget.setHeaderLabels(['Name', 'Value', 'Type'])
        self.debug_vars_widget.setColumnWidth(0, 120)
        self.debug_vars_widget.setColumnWidth(1, 150)
        
        # Breakpoints list
        bp_label = QLabel('Breakpoints:')
        self.debug_bp_widget = QTreeWidget()
        self.debug_bp_widget.setHeaderLabels(['Line', 'File', 'Enabled'])
        self.debug_bp_widget.setColumnWidth(0, 60)
        self.debug_bp_widget.setColumnWidth(1, 150)
        
        v_layout.addWidget(vars_label)
        v_layout.addWidget(self.debug_vars_widget)
        v_layout.addWidget(bp_label)
        v_layout.addWidget(self.debug_bp_widget)
        
        self.debug_dock.setWidget(debug_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.debug_dock)
        
        # Update breakpoints display
        self.update_breakpoints_display()
        
    def update_breakpoints_display(self):
        """Update the breakpoints display in debug panel"""
        if not self.debug_bp_widget:
            return
        self.debug_bp_widget.clear()
        for line_num in sorted(self.editor.breakpoints.keys()):
            item = QTreeWidgetItem([str(line_num), self.current_file or '<unsaved>', 'Yes'])
            self.debug_bp_widget.addTopLevelItem(item)
            
    def update_variables_display(self, variables):
        """Update variables display in debug panel"""
        if not self.debug_vars_widget:
            return
        self.debug_vars_widget.clear()
        for name, value in variables.items():
            value_str = str(value) if value is not None else 'None'
            type_str = type(value).__name__ if value is not None else 'NoneType'
            item = QTreeWidgetItem([name, value_str, type_str])
            self.debug_vars_widget.addTopLevelItem(item)
            
    def debug_step_into(self):
        """Step into function call"""
        # This would integrate with a debugger - for now just a placeholder
        QMessageBox.information(self, 'Debug', 'Step Into: This feature requires interpreter support')
        
    def debug_step_over(self):
        """Step over function call"""
        QMessageBox.information(self, 'Debug', 'Step Over: This feature requires interpreter support')
        
    def debug_continue(self):
        """Continue execution until next breakpoint"""
        QMessageBox.information(self, 'Debug', 'Continue: This feature requires interpreter support')


class FindReplaceDialog(QDialog):
    """Simple find/replace dialog"""
    def __init__(self, parent=None, mode='find'):
        super().__init__(parent)
        self.setWindowTitle('Find' if mode == 'find' else 'Replace')
        layout = QVBoxLayout()
        
        # Search text
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel('Find:'))
        self.search_input = QLineEdit()
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Replace text (only for replace mode)
        if mode == 'replace':
            replace_layout = QHBoxLayout()
            replace_layout.addWidget(QLabel('Replace:'))
            self.replace_input = QLineEdit()
            replace_layout.addWidget(self.replace_input)
            layout.addLayout(replace_layout)
            
        # Case sensitive checkbox
        self.case_checkbox = QtWidgets.QCheckBox('Case sensitive')
        layout.addWidget(self.case_checkbox)
        
        # Buttons
        button_layout = QHBoxLayout()
        ok_btn = QPushButton('OK')
        cancel_btn = QPushButton('Cancel')
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def get_search_text(self):
        return self.search_input.text()
        
    def get_replace_text(self):
        if hasattr(self, 'replace_input'):
            return self.replace_input.text()
        return ''
        
    def is_case_sensitive(self):
        return self.case_checkbox.isChecked()


class LineNumberArea(QtWidgets.QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QtCore.QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)


class CodeEditor(QtWidgets.QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()
        # attach highlighter
        self.highlighter = HSharpHighlighter(self.document())
        
        # Auto-completion setup
        self.completer = None
        self.setCompleter(None)
        
        # Bracket matching
        self.matching_brackets = {'(': ')', '[': ']', '{': '}'}
        self.opening_brackets = set(self.matching_brackets.keys())
        self.closing_brackets = set(self.matching_brackets.values())
        self.bracket_match_format = QTextCharFormat()
        self.bracket_match_format.setBackground(QColor(200, 230, 255))
        
        # Breakpoints storage: line_number -> bool
        self.breakpoints = {}
        
        # Connect signals for bracket matching
        self.cursorPositionChanged.connect(self.highlightMatchingBracket)
        
        # Auto-indentation enabled
        self.auto_indent_enabled = True
        
    def setCompleter(self, completer):
        if self.completer:
            try:
                self.completer.activated.disconnect()
            except (TypeError, RuntimeError):
                pass
        self.completer = completer
        if not self.completer:
            return
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.activated.connect(self.insertCompletion)
        
    def insertCompletion(self, completion):
        if self.completer.widget() != self:
            return
        tc = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        tc.movePosition(QTextCursor.Left)
        tc.movePosition(QTextCursor.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)
            
    def keyPressEvent(self, event):
        """Enhanced key press handling for auto-completion and indentation"""
        # Handle Tab for completion
        if self.completer and self.completer.popup().isVisible():
            if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab):
                event.ignore()
                return
                
        # Auto-indentation
        if event.key() == Qt.Key_Return and self.auto_indent_enabled:
            cursor = self.textCursor()
            block = cursor.block()
            text = block.text()
            
            # Calculate indentation
            indent = len(text) - len(text.lstrip())
            # Add extra indent after opening braces
            if text.rstrip().endswith('{'):
                indent += 4
                
            super().keyPressEvent(event)
            # Insert indentation
            self.insertPlainText(' ' * indent)
            return
            
        # Bracket auto-completion
        if event.text() in self.opening_brackets:
            closing = self.matching_brackets[event.text()]
            self.insertPlainText(event.text() + closing)
            # Move cursor back between brackets
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.Left)
            self.setTextCursor(cursor)
            return
            
        # Skip closing bracket if next char is the same
        if event.text() in self.closing_brackets:
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.Right)
            next_char = cursor.selectedText()
            if next_char == event.text():
                cursor.movePosition(QTextCursor.Right)
                self.setTextCursor(cursor)
                return
                
        super().keyPressEvent(event)
        
    def highlightMatchingBracket(self):
        """Highlight matching brackets"""
        # Clear previous highlighting
        extra = []
        
        cursor = self.textCursor()
        pos = cursor.position()
        
        if pos == 0:
            return
            
        # Check character before cursor
        cursor.setPosition(pos - 1)
        char = cursor.document().characterAt(cursor.position())
        
        if char in self.opening_brackets:
            self._highlightBracketPair(cursor, forward=True, extra=extra)
        elif char in self.closing_brackets:
            self._highlightBracketPair(cursor, forward=False, extra=extra)
            
        # Also add current line highlight
        if not self.isReadOnly():
            selection = QtWidgets.QTextEdit.ExtraSelection()
            lineColor = QColor(235, 245, 255)
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra.append(selection)
            
        self.setExtraSelections(extra)
            
    def _highlightBracketPair(self, cursor, forward=True, extra=None):
        """Highlight a pair of matching brackets"""
        if extra is None:
            extra = []
            
        start_pos = cursor.position()
        depth = 1
        match_pos = -1
        
        while True:
            if forward:
                cursor.movePosition(QTextCursor.Right)
            else:
                cursor.movePosition(QTextCursor.Left)
                
            if cursor.atEnd() or cursor.atStart():
                break
                
            char = cursor.document().characterAt(cursor.position())
            
            if forward:
                if char in self.opening_brackets:
                    depth += 1
                elif char in self.closing_brackets:
                    depth -= 1
            else:
                if char in self.closing_brackets:
                    depth += 1
                elif char in self.opening_brackets:
                    depth -= 1
                    
            if depth == 0:
                match_pos = cursor.position()
                break
                
        if match_pos != -1:
            # Highlight opening bracket
            sel1 = QtWidgets.QTextEdit.ExtraSelection()
            sel1.format = self.bracket_match_format
            sel1.cursor = QTextCursor(self.document())
            sel1.cursor.setPosition(start_pos)
            sel1.cursor.setPosition(start_pos + 1, QTextCursor.KeepAnchor)
            extra.append(sel1)
            
            # Highlight closing bracket
            sel2 = QtWidgets.QTextEdit.ExtraSelection()
            sel2.format = self.bracket_match_format
            sel2.cursor = QTextCursor(self.document())
            sel2.cursor.setPosition(match_pos)
            sel2.cursor.setPosition(match_pos + 1, QTextCursor.KeepAnchor)
            extra.append(sel2)
            
    def toggle_breakpoint(self, line_number):
        """Toggle breakpoint at given line number"""
        if line_number in self.breakpoints:
            del self.breakpoints[line_number]
        else:
            self.breakpoints[line_number] = True
        self.viewport().update()

    def lineNumberAreaWidth(self):
        digits = 1
        max_block = max(1, self.blockCount())
        while max_block >= 10:
            max_block //= 10
            digits += 1
        space = 3 + self.fontMetrics().width('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QtWidgets.QStylePainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor(240, 240, 240))
        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(QColor(120, 120, 120))
                # Draw breakpoint indicator if exists
                line_num = blockNumber + 1
                if line_num in self.breakpoints:
                    painter.setBrush(QColor(200, 50, 50))
                    painter.setPen(Qt.NoPen)
                    radius = min(8, self.lineNumberArea.width() // 3)
                    painter.drawEllipse(4, int(top) + (self.fontMetrics().height() - radius) // 2, radius, radius)
                    text_x = 4 + radius + 2
                else:
                    text_x = 0
                painter.drawText(text_x, int(top), self.lineNumberArea.width()-4-text_x, self.fontMetrics().height(), QtCore.Qt.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1
            
    def mousePressEvent(self, event):
        """Handle mouse clicks for toggling breakpoints"""
        if event.button() == Qt.LeftButton:
            # Check if click is in the line number area
            if event.pos().x() < self.lineNumberAreaWidth():
                cursor = self.cursorForPosition(event.pos())
                if cursor is not None:
                    line_number = cursor.blockNumber() + 1
                    self.toggle_breakpoint(line_number)
                    self.viewport().update()
                    return
        super().mousePressEvent(event)

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QtWidgets.QTextEdit.ExtraSelection()
            lineColor = QColor(235, 245, 255)
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)


class HSharpHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self._rules = []
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor(0, 0, 180))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [
            'let','fn','return','while','if','else','for','in','print','import',
            'class','extends','new','private','true','false'
        ]
        # logical operators
        keywords.extend(['and', 'or', 'not'])
        for kw in keywords:
            pattern = QRegExp(r"\b" + kw + r"\b")
            self._rules.append((pattern, keyword_format))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor(150, 0, 0))
        self._rules.append((QRegExp(r"\b[0-9]+\b"), number_format))

        string_format = QTextCharFormat()
        string_format.setForeground(QColor(0, 150, 0))
        self._rules.append((QRegExp(r'".*"'), string_format))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor(128, 128, 128))
        self._rules.append((QRegExp(r'//.*$'), comment_format))

        # function name / call highlighting (identifier followed by '(')
        func_format = QTextCharFormat()
        func_format.setForeground(QColor(128, 0, 128))
        func_format.setFontItalic(True)
        self._rules.append((QRegExp(r"\b[A-Za-z_][A-Za-z0-9_]*(?=\s*\()"), func_format))

        # Type/Class names (capitalized identifiers)
        type_format = QTextCharFormat()
        type_format.setForeground(QColor(0, 120, 120))
        type_format.setFontWeight(QFont.Bold)
        self._rules.append((QRegExp(r"\b[A-Z][A-Za-z0-9_]*\b"), type_format))

        # Multi-line comment and multi-line string handling
        self.commentStart = QRegExp(r'/\*')
        self.commentEnd = QRegExp(r'\*/')
        self.tripleDoubleStart = QRegExp(r'"""')
        self.tripleDoubleEnd = QRegExp(r'"""')
        self.tripleSingleStart = QRegExp("'''")
        self.tripleSingleEnd = QRegExp("'''")
        self.multiLineStringFormat = string_format
        self.commentFormat = comment_format

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            index = pattern.indexIn(text)
            while index >= 0:
                length = pattern.matchedLength()
                self.setFormat(index, length, fmt)
                index = pattern.indexIn(text, index + length)

        # Multi-line comments /* ... */
        self.setCurrentBlockState(0)
        startIndex = 0
        if self.previousBlockState() != 1:
            startIndex = self.commentStart.indexIn(text)
        while startIndex >= 0:
            endIndex = self.commentEnd.indexIn(text, startIndex)
            if endIndex == -1:
                self.setCurrentBlockState(1)
                commentLength = len(text) - startIndex
                self.setFormat(startIndex, commentLength, self.commentFormat)
                break
            else:
                commentLength = endIndex - startIndex + self.commentEnd.matchedLength()
                self.setFormat(startIndex, commentLength, self.commentFormat)
                startIndex = self.commentStart.indexIn(text, startIndex + commentLength)

        # Multi-line triple-double strings
        startIndex = 0
        if self.previousBlockState() != 2:
            startIndex = self.tripleDoubleStart.indexIn(text)
        while startIndex >= 0:
            endIndex = self.tripleDoubleEnd.indexIn(text, startIndex + 3)
            if endIndex == -1:
                self.setCurrentBlockState(2)
                strLen = len(text) - startIndex
                self.setFormat(startIndex, strLen, self.multiLineStringFormat)
                break
            else:
                strLen = endIndex - startIndex + self.tripleDoubleEnd.matchedLength()
                self.setFormat(startIndex, strLen, self.multiLineStringFormat)
                startIndex = self.tripleDoubleStart.indexIn(text, startIndex + strLen)

        # Multi-line triple-single strings
        startIndex = 0
        if self.previousBlockState() != 3:
            startIndex = self.tripleSingleStart.indexIn(text)
        while startIndex >= 0:
            endIndex = self.tripleSingleEnd.indexIn(text, startIndex + 3)
            if endIndex == -1:
                self.setCurrentBlockState(3)
                strLen = len(text) - startIndex
                self.setFormat(startIndex, strLen, self.multiLineStringFormat)
                break
            else:
                strLen = endIndex - startIndex + self.tripleSingleEnd.matchedLength()
                self.setFormat(startIndex, strLen, self.multiLineStringFormat)
                startIndex = self.tripleSingleStart.indexIn(text, startIndex + strLen)


def main():
    app = QtWidgets.QApplication(sys.argv)

    # attempt to show splash from local image file for 3 seconds
    img_path = os.path.join(os.path.dirname(__file__), 'hcs_logo_design2_compressed.jpg')
    if os.path.exists(img_path):
        try:
            pix = QPixmap(img_path)
            if not pix.isNull():
                # scale to a reasonable maximum size while keeping aspect ratio
                max_width = 480
                max_height = 320
                pix = pix.scaled(max_width, max_height, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                splash = QtWidgets.QSplashScreen(pix)
                splash.setWindowFlags(splash.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
                # center the splash on the primary screen if available
                screen = app.primaryScreen()
                if screen:
                    sg = screen.availableGeometry()
                    sw = pix.width()
                    sh = pix.height()
                    splash.move(sg.center().x() - sw // 2, sg.center().y() - sh // 2)
                splash.show()
                app.processEvents()
                win = IDLEWindow()
                def _show_main():
                    try:
                        splash.finish(win)
                        win.show()
                    except:
                        # If splash finish fails, just show the window
                        try:
                            win.show()
                        except:
                            pass
                QtCore.QTimer.singleShot(3000, _show_main)
                try:
                    sys.exit(app.exec_())
                except KeyboardInterrupt:
                    # Handle Ctrl+C gracefully
                    pass
        except Exception:
            # fallback to normal startup on any error
            pass

    # default startup if splash unavailable
    try:
        win = IDLEWindow()
        win.show()
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        pass


if __name__ == '__main__':
    main()
