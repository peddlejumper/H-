#!/usr/bin/env python3
"""
Test script to verify idle compile and run functionality with error handling
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

def test_compile_and_run_valid():
    """Test the compile and run functionality with valid code"""
    code = """
let x = 10;
print(x);
"""
    
    print("Testing compilation with valid code...")
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
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_compile_and_run_invalid():
    """Test the compile and run functionality with invalid code"""
    code = """
let x = ;  // Invalid syntax
"""
    
    print("\nTesting compilation with invalid code...")
    try:
        lexer = Lexer(code)
        parser = Parser(lexer)
        program = parser.parse()
        compiler = Compiler()
        bc = compiler.compile(program)
        
        print("✗ Test failed: Should have raised an exception")
        return False
        
    except Exception as e:
        print(f"✓ Correctly caught error: {type(e).__name__}: {e}")
        return True

def test_compile_and_run_empty():
    """Test the compile and run functionality with empty code"""
    code = ""
    
    print("\nTesting compilation with empty code...")
    if not code.strip():
        print("✓ Correctly detected empty code")
        return True
    else:
        print("✗ Test failed: Should have detected empty code")
        return False

if __name__ == '__main__':
    results = []
    results.append(test_compile_and_run_valid())
    results.append(test_compile_and_run_invalid())
    results.append(test_compile_and_run_empty())
    
    print(f"\n{'='*50}")
    print(f"Tests passed: {sum(results)}/{len(results)}")
    
    if all(results):
        print("All tests passed!")
        sys.exit(0)
    else:
        print("Some tests failed!")
        sys.exit(1)
