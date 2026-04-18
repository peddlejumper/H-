import os
import sys
ROOT = os.path.dirname(os.path.abspath(__file__))
parent = os.path.abspath(os.path.join(ROOT, '..'))
if parent not in sys.path:
    sys.path.insert(0, parent)

from lexer import Lexer
from parser import Parser
from interpreter import Interpreter

sample = '''
# coroutine test
coro worker() {
  coro_yield();
  return 42;
}

let c = worker();
print(coro_resume(c));
print(coro_resume(c));
'''

# load H# bootstrap tokenizer and parser into Python interpreter
with open(os.path.join(ROOT, 'tokenize.hto'), 'r', encoding='utf-8') as f:
    code = f.read()
lexer = Lexer(code)
parser = Parser(lexer)
boot_program = parser.parse()
interp = Interpreter()
interp.interpret(boot_program)

# load parser bootstrap
pboot = os.path.join(ROOT, 'parser.hto')
with open(pboot, 'r', encoding='utf-8') as f:
    pcode = f.read()
lexer2 = Lexer(pcode)
parser2 = Parser(lexer2)
prog2 = parser2.parse()
interp.interpret(prog2)

# parse and run sample program
from h_ast import CallExpression, Identifier, StringLiteral, ArrayLiteral, DictLiteral, StringLiteral as StrLit, NumberLiteral, BooleanLiteral, NullLiteral

call = CallExpression(Identifier('tokenize'), [StringLiteral(sample)])
toks = interp.visit_CallExpression(call, interp.global_env)
print('\nTOKENS from H# tokenize:')
for t in toks:
    print(t)

def py_tokens_to_ast(tokens_list):
    elems = []
    for tok in tokens_list:
        pairs = []
        for k, v in tok.items():
            key_node = StrLit(k)
            if v is None:
                val_node = NullLiteral()
            elif isinstance(v, bool):
                val_node = BooleanLiteral(v)
            elif isinstance(v, (int, float)):
                val_node = NumberLiteral(v)
            else:
                val_node = StrLit(str(v))
            pairs.append((key_node, val_node))
        elems.append(DictLiteral(pairs))
    return ArrayLiteral(elems)

if 'parse' in interp.functions:
    tokens_ast = py_tokens_to_ast(toks)
    ast = interp.visit_CallExpression(CallExpression(Identifier('parse'), [tokens_ast]), interp.global_env)
    print('\nAST from H# parse:')
    print(ast)
    program_from_h = interp._dict_to_ast(ast)
    print('\n--- Running coroutine sample ---')
    interp.interpret(program_from_h)
else:
    print('H# parse not available in interpreter')
