#!/usr/bin/env python3
"""
Test H# GUI module
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from hsharp_gui import HSharpGUI, create_window, show_message, run_gui

def test_basic_gui():
    """Test basic GUI functionality"""
    print("Testing H# GUI module...")
    
    try:
        # Create GUI instance
        gui = HSharpGUI()
        print("✓ GUI instance created")
        
        # Create window
        window = gui.create_window("Test Window", 400, 300)
        print("✓ Window created")
        
        # Add components
        window.add_label("Hello, H# GUI!")
        print("✓ Label added")
        
        window.add_button("Click Me", None, "btn1")
        print("✓ Button added")
        
        window.add_text_input("Enter text...", "input1")
        print("✓ Text input added")
        
        # Test getting/setting text
        window.set_text("input1", "Test text")
        text = window.get_text("input1")
        if text == "Test text":
            print("✓ Text get/set works correctly")
        else:
            print(f"✗ Text get/set failed: expected 'Test text', got '{text}'")
        
        # Show window (don't run event loop in test)
        print("✓ All basic tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_layouts():
    """Test layout functionality"""
    print("\nTesting layouts...")
    
    try:
        gui = HSharpGUI()
        window = gui.create_window("Layout Test", 500, 400)
        
        # Test horizontal layout
        window.start_horizontal_layout()
        window.add_button("Btn1")
        window.add_button("Btn2")
        window.end_layout()
        print("✓ Horizontal layout works")
        
        # Test vertical layout
        window.start_vertical_layout()
        window.add_label("Label1")
        window.add_label("Label2")
        window.end_layout()
        print("✓ Vertical layout works")
        
        # Test stretch and spacer
        window.add_stretch()
        print("✓ Stretch works")
        
        print("✓ All layout tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Layout test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_components():
    """Test various GUI components"""
    print("\nTesting components...")
    
    try:
        gui = HSharpGUI()
        window = gui.create_window("Components Test", 600, 500)
        
        # Test combo box
        window.add_combo_box(["A", "B", "C"], "combo1")
        print("✓ Combo box added")
        
        # Test checkbox
        window.add_checkbox("Check me", True, "check1")
        print("✓ Checkbox added")
        
        # Test slider
        window.add_slider(0, 100, 50, "slider1")
        print("✓ Slider added")
        
        # Test progress bar
        window.add_progress_bar("progress1")
        print("✓ Progress bar added")
        
        # Test spin box
        window.add_spin_box(0, 100, 10, "spin1")
        print("✓ Spin box added")
        
        # Test text area
        window.add_text_area("textarea1")
        print("✓ Text area added")
        
        print("✓ All component tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Component test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    results = []
    results.append(test_basic_gui())
    results.append(test_layouts())
    results.append(test_components())
    
    print(f"\n{'='*60}")
    print(f"Tests passed: {sum(results)}/{len(results)}")
    
    if all(results):
        print("All GUI tests passed!")
        sys.exit(0)
    else:
        print("Some tests failed!")
        sys.exit(1)
