#!/usr/bin/env python3
"""
H# GUI Calculator - Full working example
This demonstrates a complete calculator application using the H# GUI module
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from hsharp_gui import HSharpGUI

class CalculatorApp:
    """Calculator application using H# GUI"""
    
    def __init__(self):
        self.gui = HSharpGUI()
        self.window = self.gui.create_window("H# Calculator", 320, 450)
        self.expression = ""
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the calculator UI"""
        # Display
        self.display = self.window.add_text_input("0", "display")
        self.display.setReadOnly(True)
        
        # Button layout
        buttons = [
            ['7', '8', '9', '/'],
            ['4', '5', '6', '*'],
            ['1', '2', '3', '-'],
            ['C', '0', '=', '+']
        ]
        
        for row in buttons:
            self.window.start_horizontal_layout()
            for btn_text in row:
                btn = self.window.add_button(btn_text, None, f"btn_{btn_text}")
                # Connect button click
                btn.clicked.connect(lambda checked, t=btn_text: self.on_button_click(t))
            self.window.end_layout()
        
        self.window.add_stretch()
        self.window.set_status("H# Calculator Ready")
    
    def on_button_click(self, text):
        """Handle button clicks"""
        if text == 'C':
            # Clear
            self.expression = ""
            self.window.set_text("display", "0")
        elif text == '=':
            # Calculate
            try:
                # Safe evaluation
                result = str(eval(self.expression, {}, {}))
                self.window.set_text("display", result)
                self.expression = result
            except:
                self.window.set_text("display", "Error")
                self.expression = ""
        else:
            # Add to expression
            if self.expression == "0" and text not in ['+', '-', '*', '/']:
                self.expression = text
            else:
                self.expression += text
            self.window.set_text("display", self.expression)
    
    def run(self):
        """Run the calculator"""
        self.window.show()
        return self.gui.run()


if __name__ == '__main__':
    app = CalculatorApp()
    app.run()
