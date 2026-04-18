import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
parent = os.path.abspath(os.path.join(ROOT, '..'))
if parent not in sys.path:
    sys.path.insert(0, parent)

from lexer import Lexer
from parser import Parser
from interpreter import Interpreter

GOOD = '''
concept Printable {
    fn printit(x) { }
}

class A implements Printable {
    fn printit(x) { print(x); }
}
print("ok");
'''

BAD = '''
concept Printable2 {
    fn printit(x, y) { }
}

class B implements Printable2 {
    fn printit(x) { print(x); }
}

let b = B();
print(b);
'''

def run_code(code):
    interp = Interpreter()
    lx = Lexer(code)
    p = Parser(lx)
    prog = p.parse()
    ret = interp.interpret(prog)
    return ret

print('Running GOOD sample:')
run_code(GOOD)
print('Running BAD sample (expect concept failure):')
run_code(BAD)
