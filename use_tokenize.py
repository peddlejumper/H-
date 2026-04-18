import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
parent = os.path.abspath(os.path.join(ROOT, '..'))
if parent not in sys.path:
    sys.path.insert(0, parent)

from lexer import Lexer
from parser import Parser
from interpreter import Interpreter
from h_ast import Program, Identifier, StringLiteral, CallExpression, ArrayLiteral, DictLiteral, StringLiteral, NumberLiteral, BooleanLiteral, NullLiteral

BOOT = os.path.join(ROOT, 'tokenize.hto')
with open(BOOT, 'r', encoding='utf-8') as f:
    code = f.read()

# load H# tokenizer source into interpreter
lexer = Lexer(code)
parser = Parser(lexer)
try:
    # step through statements to locate parse failures
    stmts = []
    while parser.current_token[0].__str__() != 'TokenType.EOF':
        print('PARSER: next token', parser.current_token)
        s = parser.statement()
        stmts.append(s)
    program = Program(stmts)
except Exception as e:
    print('Parse error:', e)
    print('Current token at failure:', parser.current_token)
    try:
        print('Lexer pos (char index):', parser.lexer.pos)
        # dump surrounding source snippet
        src = parser.lexer.text
        p = parser.lexer.pos
        print('Context:', repr(src[max(0,p-60):min(len(src), p+60)]))
    except Exception:
        pass
    raise
interp = Interpreter()
# Inject host builtin helpers for file I/O and asm emission
def host_read_file(args):
    path = args[0]
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return None

def host_write_file(args):
    path = args[0]
    data = args[1]
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(data)
        return True
    except Exception:
        return False

def host_emit_asm(args):
    asm_code = args[0]
    fname = 'out_asm.s'
    try:
        with open(fname, 'w', encoding='utf-8') as f:
            f.write(asm_code)
        return fname
    except Exception:
        return None

# register into interpreter builtins so H# functions executed under Python interpreter can call them
interp.builtins['read_file'] = host_read_file
interp.builtins['write_file'] = host_write_file
interp.builtins['emit_asm'] = host_emit_asm
interp.interpret(program)

# Now create a CallExpression AST to call tokenize with a sample source
sample = 'let x = 1; print(x);'
call = CallExpression(Identifier('tokenize'), [StringLiteral(sample)])
# visit_CallExpression is implemented to evaluate calls
tokens = interp.visit_CallExpression(call, interp.global_env)
print('Tokens returned from H# tokenize:')
for t in tokens:
    print(t)

# Load H# parser implementation so we can call parse(tokens)
PARSER_BOOT = os.path.join(ROOT, 'parser.hto')
if os.path.exists(PARSER_BOOT):
    with open(PARSER_BOOT, 'r', encoding='utf-8') as f:
        pcode = f.read()
    lexer2 = Lexer(pcode)
    parser2 = Parser(lexer2)
    try:
        program2 = parser2.parse()
    except Exception as e:
        print('Parse error while loading parser.hto:', e)
        try:
            print('Current token at failure:', parser2.current_token)
            print('Lexer pos (char index):', parser2.lexer.pos)
            src = parser2.lexer.text
            p = parser2.lexer.pos
            print('Context:', repr(src[max(0,p-60):min(len(src), p+60)]))
        except Exception:
            pass
        raise
    interp.interpret(program2)

# Load H# interpreter implementation so we can call interpret(ast)
INTERP_BOOT = os.path.join(ROOT, 'interpreter.hto')
if os.path.exists(INTERP_BOOT):
    with open(INTERP_BOOT, 'r', encoding='utf-8') as f:
        ibody = f.read()
    lexer3 = Lexer(ibody)
    parser3 = Parser(lexer3)
    program3 = parser3.parse()
    interp.interpret(program3)

# Helper: convert Python token dict list to H# AST ArrayLiteral of DictLiteral
def py_tokens_to_ast(tokens_list):
    elems = []
    for tok in tokens_list:
        pairs = []
        for k, v in tok.items():
            # key as string literal
            key_node = StringLiteral(k)
            # value node
            if v is None:
                val_node = NullLiteral()
            elif isinstance(v, bool):
                val_node = BooleanLiteral(v)
            elif isinstance(v, (int, float)):
                val_node = NumberLiteral(v)
            else:
                val_node = StringLiteral(str(v))
            pairs.append((key_node, val_node))
        elems.append(DictLiteral(pairs))
    return ArrayLiteral(elems)

# If parser was loaded, call parse(tokens)
if 'parse' in interp.functions:
    tokens_ast = py_tokens_to_ast(tokens)
    parse_call = CallExpression(Identifier('parse'), [tokens_ast])
    ast_dict = interp.visit_CallExpression(parse_call, interp.global_env)
    print('AST dict from H# parse:', ast_dict)
    # If H# interpreter loaded, call it directly with serialized AST
    # Prefer H# interpreter if it's a Python-callable; otherwise fall back
    if 'interpret' in interp.functions and callable(interp.functions['interpret']):
        ret = interp.functions['interpret'](ast_dict)
        # simple marker handling: __PRINT__, __IMPORT__, __ASM__
        if isinstance(ret, list) and len(ret) > 0:
            tag = ret[0]
            if tag == '__PRINT__':
                print('H# print:', ret[1])
            elif tag == '__IMPORT__':
                path = ret[1]
                print('H# import requested:', path)
                # fallback: use Python lexer/parser to load and run module
                if path is not None:
                    if not path.endswith('.hto'):
                        path = path + '.hto'
                    if os.path.exists(path):
                        with open(path, 'r', encoding='utf-8') as mf:
                            mcode = mf.read()
                        # prefer H# tokenizer/parser if available
                        processed = False
                        if 'tokenize' in interp.functions:
                            try:
                                mtoks = interp.functions['tokenize'](mcode)
                                if 'parse' in interp.functions:
                                    # convert mtoks to AST literal for parse call
                                    tokens_ast = py_tokens_to_ast(mtoks)
                                    mast = interp.visit_CallExpression(CallExpression(Identifier('parse'), [tokens_ast]), interp.global_env)
                                    # pass module AST back into H# interpret via visit_CallExpression
                                    from h_ast import ArrayLiteral, DictLiteral, StringLiteral as StrLit, NumberLiteral, BooleanLiteral, NullLiteral
                                    def serialize_to_hast(obj):
                                        if obj is None:
                                            return NullLiteral()
                                        if isinstance(obj, bool):
                                            return BooleanLiteral(obj)
                                        if isinstance(obj, (int, float)):
                                            return NumberLiteral(obj)
                                        if isinstance(obj, str):
                                            return StrLit(obj)
                                        if isinstance(obj, list):
                                            elems = [serialize_to_hast(e) for e in obj]
                                            return ArrayLiteral(elems)
                                        if isinstance(obj, dict):
                                            pairs = []
                                            for k, v in obj.items():
                                                pairs.append((StrLit(str(k)), serialize_to_hast(v)))
                                            return DictLiteral(pairs)
                                        return StrLit(str(obj))
                                    mast_literal = serialize_to_hast(mast)
                                    try:
                                        interp.visit_CallExpression(CallExpression(Identifier('interpret'), [mast_literal]), interp.global_env)
                                        processed = True
                                    except Exception:
                                        # fallback to Python parser if H# interpret cannot handle
                                        ml = Lexer(mcode)
                                        mp = Parser(ml)
                                        mprog = mp.parse()
                                        interp.interpret(mprog)
                                        processed = True
                                
                            except Exception:
                                pass
                        # final fallback: use Python lexer/parser if not processed
                        if not processed:
                            ml = Lexer(mcode)
                            mp = Parser(ml)
                            mprog = mp.parse()
                            interp.interpret(mprog)
            elif tag == '__ASM__':
                asm_code = ret[1]
                # write asm to file via host helper
                fname = interp.builtins.get('emit_asm', lambda a: None)([asm_code])
                print('H# asm block written to:', fname)
            elif tag == '__CONCEPT_FAIL__':
                print('H# concept check failed:', ret[1], 'missing method:', ret[2])
            elif tag == '__ERROR__':
                print('H# error:', ret[1])
    else:
        # convert to Python AST and interpret
        program_from_h = interp._dict_to_ast(ast_dict)
        print('Interpreting program built from H# parser:')
        interp.interpret(program_from_h)

    # If H# interpret exists as a Function AST (not directly callable), call it
    if 'interpret' in interp.functions and not callable(interp.functions['interpret']):
        # convert serialized list-style AST into h_ast literal nodes so that
        # calling via visit_CallExpression will pass a native Python list/dict
        # representation into the H# interpreter function.
        from h_ast import ArrayLiteral, DictLiteral, StringLiteral as StrLit, NumberLiteral, BooleanLiteral, NullLiteral

        def serialize_to_hast(obj):
            # obj is a Python list/dict/str/num representing H# serialized AST
            if obj is None:
                return NullLiteral()
            if isinstance(obj, bool):
                return BooleanLiteral(obj)
            if isinstance(obj, (int, float)):
                return NumberLiteral(obj)
            if isinstance(obj, str):
                return StrLit(obj)
            if isinstance(obj, list):
                # list of elements
                elems = [serialize_to_hast(e) for e in obj]
                return ArrayLiteral(elems)
            if isinstance(obj, dict):
                pairs = []
                for k, v in obj.items():
                    pairs.append((StrLit(str(k)), serialize_to_hast(v)))
                return DictLiteral(pairs)
            # fallback to string
            return StrLit(str(obj))

        ast_literal = serialize_to_hast(ast_dict)
        call_interp = CallExpression(Identifier('interpret'), [ast_literal])
        try:
            res = interp.visit_CallExpression(call_interp, interp.global_env)
            if isinstance(res, list) and len(res) > 0:
                if res[0] == '__PRINT__':
                    print('H# interpret print:', res[1])
                elif res[0] == '__ASM__':
                    fname = interp.builtins.get('emit_asm', lambda a: None)([res[1]])
                    print('H# interpret asm written to:', fname)
                elif res[0] == '__CONCEPT_FAIL__':
                    print('H# concept check failed:', res[1], 'missing method:', res[2])
                elif res[0] == '__ERROR__':
                    print('H# error:', res[1])
        except Exception as e:
            print('Error calling H# interpret via visit_CallExpression:', e)
