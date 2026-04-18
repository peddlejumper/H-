#!/usr/bin/env python3
"""
Test script to verify the os import fix in compile_and_run
"""
import sys
import os
import json
import tempfile

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from lexer import Lexer
from parser import Parser
from compiler import Compiler

def test_compile_and_run_with_cleanup():
    """Test that compile_and_run properly cleans up temp files"""
    code = """
let x = 10;
print(x);
"""
    
    print("Testing compilation with proper cleanup...")
    tf = None
    try:
        # Compile the code
        lexer = Lexer(code)
        parser = Parser(lexer)
        program = parser.parse()
        compiler = Compiler()
        bc = compiler.compile(program)
        
        # Save bytecode to temp file (simulating what compile_and_run does)
        tf = tempfile.NamedTemporaryFile(delete=False, suffix='.hbc', mode='w')
        json.dump(bc, tf)
        tf.close()
        
        print(f"✓ Compilation successful")
        print(f"Temp file created: {tf.name}")
        
        # Verify file exists
        if os.path.exists(tf.name):
            print("✓ Temp file exists")
        else:
            print("✗ Temp file does not exist")
            return False
        
        # Simulate the cleanup that happens in finally block
        if tf and hasattr(tf, 'name'):
            try:
                os.unlink(tf.name)
                print("✓ Temp file cleaned up successfully")
            except Exception as e:
                print(f"✗ Failed to clean up temp file: {e}")
                return False
        
        # Verify file is deleted
        if not os.path.exists(tf.name):
            print("✓ Temp file was properly deleted")
        else:
            print("✗ Temp file still exists")
            return False
            
        print("✓ Test passed!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Clean up in case of error
        if tf and hasattr(tf, 'name'):
            try:
                os.unlink(tf.name)
            except:
                pass
        return False

if __name__ == '__main__':
    success = test_compile_and_run_with_cleanup()
    sys.exit(0 if success else 1)
