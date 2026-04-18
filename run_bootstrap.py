"""Run the H# bootstrap program using the existing Python-based interpreter."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BOOT = os.path.join(ROOT, 'bootstrap.hto')

# Ensure parent folder (v0.4) is on sys.path so we can import local modules
parent = os.path.abspath(os.path.join(ROOT, '..'))
if parent not in sys.path:
    sys.path.insert(0, parent)

from lexer import Lexer
from parser import Parser
from interpreter import Interpreter

with open(BOOT, 'r', encoding='utf-8') as f:
    code = f.read()

lexer = Lexer(code)
parser = Parser(lexer)
program = parser.parse()
interp = Interpreter()
print('--- Running H# bootstrap program with Python-hosted interpreter ---')
interp.interpret(program)
print('--- Bootstrap run complete ---')
