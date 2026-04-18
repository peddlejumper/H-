import sys
import os
import json
from lexer import Lexer
from parser import Parser
from interpreter import Interpreter
from compiler import Compiler
from bytecode import VM

def run(code, filename="<input>"):
    try:
        lexer = Lexer(code)
        parser = Parser(lexer)
        program = parser.parse()
        interpreter = Interpreter()
        interpreter.interpret(program)
    except SyntaxError as e:
        print(f"Syntax Error in {filename}: {e}")
    except Exception as e:
        print(f"Error in {filename}: {e}")

def repl():
    print("H# v0.4 REPL. Type 'exit' to quit.")
    interpreter = Interpreter()
    while True:
        try:
            line = input("h#> ").strip()
            if line == "exit":
                break
            if not line:
                continue
            if not line.endswith(';') and not line.startswith(('let ', 'fn ', 'while ', 'if ', 'for ', 'print ', 'return ', 'import ')):
                line += ';'
            lexer = Lexer(line)
            parser = Parser(lexer)
            program = parser.parse()
            interpreter.interpret(program)
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")

def main(argv=None):
    import sys as _sys
    args = list(argv if argv is not None else _sys.argv[1:])

    # simple flags
    if args:
        if args[0] in ('-h', '--help'):
            print('H# CLI\nUsage: hsharp.py [--emit-bc file.hto] [--run-bc file.hbc] [file.hto]')
            _sys.exit(0)
        if args[0] in ('-v', '--version'):
            print('H# v0.4')
            _sys.exit(0)

    if not args:
        repl()
        _sys.exit(0)

    # CLI modes:
    # 1) python hsharp.py file.hto
    # 2) python hsharp.py --emit-bc file.hto   -> writes file.hbc (JSON)
    # 3) python hsharp.py --run-bc file.hbc    -> executes compiled bytecode

    if args[0] == '--run-bc':
        if len(args) < 2:
            print('Usage: hsharp.py --run-bc file.hbc')
            _sys.exit(1)
        bcf = args[1]
        if not os.path.exists(bcf):
            print(f'Error: File not found: {bcf}')
            _sys.exit(1)
        with open(bcf, 'r', encoding='utf-8') as f:
            bc = json.load(f)
        vm = VM(bc)
        vm.run()
        _sys.exit(0)

    emit_bc = False
    if args[0] == '--emit-bc':
        emit_bc = True
        if len(args) < 2:
            print('Usage: hsharp.py --emit-bc file.hto')
            _sys.exit(1)
        filepath = args[1]
    else:
        filepath = args[0]

    if not filepath.endswith('.hto'):
        print(f"Warning: H# source files should use .hto extension (got {filepath})")
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        _sys.exit(1)
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()

    if emit_bc:
        try:
            lexer = Lexer(code)
            parser = Parser(lexer)
            program = parser.parse()
            compiler = Compiler()
            bc = compiler.compile(program)
            out = filepath.rsplit('.', 1)[0] + '.hbc'
            with open(out, 'w', encoding='utf-8') as f:
                json.dump(bc, f)
            print(f'Wrote bytecode to {out}')
        except Exception as e:
            print(f'Compilation error: {e}')
        _sys.exit(0)

    # default: run source via interpreter
    run(code, filepath)


if __name__ == '__main__':
    main()