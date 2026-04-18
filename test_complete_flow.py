#!/usr/bin/env python3
"""
Test the complete compile and run flow
"""
import sys
import os
import json
import tempfile
import subprocess

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from lexer import Lexer
from parser import Parser
from compiler import Compiler
from bytecode import VM

def test_complete_flow():
    """Test the complete compile and run flow"""
    code = """let x = 10;
print(x);
"""
    
    print("Testing complete compile and run flow...")
    print(f"Code: {repr(code)}")
    
    try:
        # Step 1: Compile
        print("\n=== Step 1: Compiling ===")
        lexer = Lexer(code)
        parser = Parser(lexer)
        program = parser.parse()
        compiler = Compiler()
        bc = compiler.compile(program)
        
        print(f"Bytecode instructions: {len(bc['instructions'])}")
        print(f"Constants: {bc['consts']}")
        
        # Step 2: Save to temp file
        print("\n=== Step 2: Saving to temp file ===")
        tf = tempfile.NamedTemporaryFile(delete=False, suffix='.hbc', mode='w')
        json.dump(bc, tf)
        tf.close()
        print(f"Saved to: {tf.name}")
        
        # Step 3: Run via hsharp.py --run-bc
        print("\n=== Step 3: Running via hsharp.py ===")
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), 'hsharp.py'), '--run-bc', tf.name],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        print(f"Return code: {result.returncode}")
        print(f"stdout: {result.stdout}")
        if result.stderr:
            print(f"stderr: {result.stderr}")
        
        # Step 4: Also test direct VM execution
        print("\n=== Step 4: Testing direct VM execution ===")
        vm = VM(bc)
        print("VM output:")
        vm.run()
        
        # Clean up
        os.unlink(tf.name)
        
        if result.returncode == 0 and '10' in result.stdout:
            print("\n✓ Test passed!")
            return True
        else:
            print("\n✗ Test failed!")
            return False
            
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_complete_flow()
    sys.exit(0 if success else 1)
