import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
parent = os.path.abspath(os.path.join(ROOT, '..'))
if parent not in sys.path:
  sys.path.insert(0, parent)

from lexer import Lexer
from parser import Parser
from interpreter import Interpreter

# sample exercising module/concept/coro/bit/pointer/asm
sample = '''
module M {
  concept Eq { }
  coro worker(x) {
  let y = x << 1;
  return y;
  }
  let z = 10 & 3;
  let p = ptr z;
  asm { mov eax, ebx; }
}
'''

with open(os.path.join(ROOT, 'tokenize.hto'), 'r', encoding='utf-8') as f:
  code = f.read()

# parse the H# tokenizer implementation to load into Python interpreter
lexer = Lexer(code)
parser = Parser(lexer)
stmts = parser.parse()
interp = Interpreter()
interp.interpret(stmts)

# call H# tokenize implementation
from h_ast import CallExpression, Identifier, StringLiteral
call = CallExpression(Identifier('tokenize'), [StringLiteral(sample)])
toks = interp.visit_CallExpression(call, interp.global_env)
print('TOKENS:')
for t in toks:
  print(t)

# load parser.hto and call parse if available
PARSER_BOOT = os.path.join(ROOT, 'parser.hto')
if os.path.exists(PARSER_BOOT):
  with open(PARSER_BOOT, 'r', encoding='utf-8') as f:
    pcode = f.read()
  lexer2 = Lexer(pcode)
  parser2 = Parser(lexer2)
  program2 = parser2.parse()
  interp.interpret(program2)
  if 'parse' in interp.functions:
    # convert Python token dicts to H# AST ArrayLiteral using helper from use_tokenize
    from h_ast import ArrayLiteral, DictLiteral, StringLiteral as StrLit, NumberLiteral, BooleanLiteral, NullLiteral
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

    tokens_ast = py_tokens_to_ast(toks)
    ast = interp.visit_CallExpression(CallExpression(Identifier('parse'), [tokens_ast]), interp.global_env)
    print('\nAST:')
    print(ast)
