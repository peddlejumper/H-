#!/usr/bin/env python3
"""
Test script to verify idle compile and run functionality
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from lexer import Lexer
from parser import Parser
from compiler import Compiler
import json
import tempfile

def test_compile_and_run():
    """Test the compile and run functionality"""
    code = """
let x = 10;
print(x);
"""
    
    print("Testing compilation...")
    try:
        lexer = Lexer(code)
        parser = Parser(lexer)
        program = parser.parse()
        compiler = Compiler()
        bc = compiler.compile(program)
        
        # Save bytecode to temp file
        tf = tempfile.NamedTemporaryFile(delete=False, suffix='.hbc', mode='w')
        json.dump(bc, tf)
        tf.close()
        
        print(f"✓ Compilation successful")
        print(f"Bytecode saved to: {tf.name}")
        
        # Test running the bytecode
        from bytecode import VM
        vm = VM(bc)
        print("Running bytecode:")
        vm.run()
        
        # Clean up
        os.unlink(tf.name)
        print("✓ Test passed!")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == '__main__':
    success = test_compile_and_run()
    sys.exit(0 if success else 1)