#!/usr/bin/env python3
"""
Debug script to check what code is being compiled and run
"""
import sys
import os

# Test simple code
test_codes = [
    ('Simple print', 'print("Hello");'),
    ('Variable assignment', 'let x = 10;\nprint(x);'),
    ('Calculator-like', 'let a = 5;\nlet b = 3;\nprint(a + b);'),
]

sys.path.insert(0, os.path.dirname(__file__))

from lexer import Lexer
from parser import Parser
from compiler import Compiler
from bytecode import VM

for name, code in test_codes:
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"Code: {repr(code)}")
    print('='*60)
    
    try:
        lexer = Lexer(code)
        parser = Parser(lexer)
        program = parser.parse()
        compiler = Compiler()
        bc = compiler.compile(program)
        
        print(f"✓ Compilation successful")
        print(f"Instructions: {len(bc['instructions'])}")
        print(f"Constants: {bc['consts']}")
        
        print("\nRunning:")
        vm = VM(bc)
        vm.run()
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "="*60)
print("All tests completed!")
