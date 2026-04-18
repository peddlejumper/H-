import os, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
parent = os.path.abspath(os.path.join(ROOT, '..'))
if parent not in sys.path:
    sys.path.insert(0, parent)

from lexer import Lexer
from parser import Parser

files = ['tokenize.hto', 'parser.hto', 'interpreter.hto']
all_ok = True
for f in files:
    path = os.path.join(ROOT, f)
    if not os.path.exists(path):
        print('Missing', path)
        all_ok = False
        continue
    src = open(path, 'r', encoding='utf-8').read()
    try:
        lex = Lexer(src)
        p = Parser(lex)
        try:
            prog = p.parse()
            print(f'Parsed OK: {f}')
        except Exception as e:
            print(f'Parse failed for {f}:', e)
            try:
                print('Current token at failure:', p.current_token)
                print('Lexer pos (char index):', p.lexer.pos)
                s = p.lexer.text
                pos = p.lexer.pos
                print('Context:', repr(s[max(0,pos-80):min(len(s), pos+80)]))
            except Exception:
                pass
            all_ok = False
            continue
    except Exception as e:
        print(f'Parse failed for {f}:', e)
        all_ok = False

if not all_ok:
    sys.exit(2)
print('All bootstrap .hto files parse OK')
