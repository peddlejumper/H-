#!/usr/bin/env python3
"""
H# GUI Complete Demo - Shows all available features
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from hsharp_gui import HSharpGUI, show_message

class CompleteDemo:
    """Complete demonstration of H# GUI features"""
    
    def __init__(self):
        self.gui = HSharpGUI()
        self.window = self.gui.create_window("H# GUI 完整演示", 900, 700)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup complete demo UI"""
        
        # Add menu bar
        file_menu = self.window.add_menu("文件")
        edit_menu = self.window.add_menu("编辑")
        help_menu = self.window.add_menu("帮助")
        
        # Add menu actions
        self.window.add_menu_action("文件", "新建", lambda: self.on_menu_click("新建"))
        self.window.add_menu_action("文件", "打开", lambda: self.on_menu_click("打开"))
        self.window.add_menu_action("文件", "保存", lambda: self.on_menu_click("保存"))
        self.window.add_menu_action("帮助", "关于", lambda: self.show_about())
        
        # Add toolbar
        self.window.add_toolbar_button("新建", lambda: self.on_toolbar_click("新建"))
        self.window.add_toolbar_button("打开", lambda: self.on_toolbar_click("打开"))
        self.window.add_toolbar_button("保存", lambda: self.on_toolbar_click("保存"))
        
        # Title
        self.window.add_label("H# GUI 功能完整演示")
        
        # Section 1: Text Input
        self.window.add_label("=== 文本输入 ===")
        self.window.add_text_input("请输入您的姓名", "name_input")
        
        # Section 2: Text Area
        self.window.add_label("=== 多行文本 ===")
        self.window.add_text_area("text_area")
        
        # Section 3: Selection Controls
        self.window.add_label("=== 选择控件 ===")
        self.window.start_horizontal_layout()
        
        # Combo box
        self.window.start_vertical_layout()
        self.window.add_label("城市：")
        self.window.add_combo_box(["北京", "上海", "广州", "深圳", "杭州"], "city_combo")
        self.window.end_layout()
        
        # Checkbox
        self.window.start_vertical_layout()
        self.window.add_checkbox("启用通知", True, "notify_check")
        self.window.add_checkbox("接受条款", False, "terms_check")
        self.window.end_layout()
        
        self.window.end_layout()
        
        # Section 4: Numeric Controls
        self.window.add_label("=== 数值控件 ===")
        self.window.start_horizontal_layout()
        
        # Slider
        self.window.start_vertical_layout()
        self.window.add_label("音量：")
        slider = self.window.add_slider(0, 100, 50, "volume_slider")
        # Connect slider value change
        slider.valueChanged.connect(lambda v: self.on_slider_change(v))
        self.window.end_layout()
        
        # Spin box
        self.window.start_vertical_layout()
        self.window.add_label("数量：")
        self.window.add_spin_box(0, 1000, 10, "count_spin")
        self.window.end_layout()
        
        # Progress bar
        self.window.start_vertical_layout()
        self.window.add_label("进度：")
        self.window.add_progress_bar("progress_bar")
        self.window.end_layout()
        
        self.window.end_layout()
        
        # Section 5: Buttons
        self.window.add_label("=== 按钮操作 ===")
        self.window.start_horizontal_layout()
        self.window.add_button("显示消息", lambda: self.show_info_message(), "msg_btn")
        self.window.add_button("询问输入", lambda: self.ask_user_input(), "ask_btn")
        self.window.add_button("选择文件", lambda: self.select_file_demo(), "file_btn")
        self.window.add_button("退出", lambda: self.window.close(), "exit_btn")
        self.window.end_layout()
        
        self.window.add_stretch()
        
        # Set status
        self.window.set_status("演示就绪 - 请尝试各种功能")
    
    def on_menu_click(self, action):
        """Handle menu clicks"""
        self.window.set_status(f"菜单点击: {action}")
        print(f"Menu clicked: {action}")
    
    def on_toolbar_click(self, action):
        """Handle toolbar clicks"""
        self.window.set_status(f"工具栏点击: {action}")
        print(f"Toolbar clicked: {action}")
    
    def on_slider_change(self, value):
        """Handle slider value change"""
        self.window.set_status(f"音量: {value}%")
    
    def show_info_message(self):
        """Show information message"""
        show_message("信息", "这是一个信息消息框！", "info")
    
    def ask_user_input(self):
        """Ask user for input"""
        from hsharp_gui import ask_question
        name = ask_question("输入", "请输入您的姓名：", "")
        if name:
            show_message("问候", f"你好，{name}！", "info")
            self.window.set_text("name_input", name)
    
    def select_file_demo(self):
        """Demonstrate file selection"""
        from hsharp_gui import select_file
        file_path = select_file("选择文件", "Python 文件 (*.py);;所有文件 (*)")
        if file_path:
            show_message("文件选择", f"您选择了:\n{file_path}", "info")
            self.window.set_status(f"已选择文件: {file_path}")
    
    def show_about(self):
        """Show about dialog"""
        show_message("关于", 
                    "H# GUI 模块\n版本 1.0\n\n一个强大的图形界面库，\n基于 PyQt5 构建。",
                    "info")
    
    def run(self):
        """Run the demo"""
        self.window.show()
        return self.gui.run()


if __name__ == '__main__':
    demo = CompleteDemo()
    demo.run()
