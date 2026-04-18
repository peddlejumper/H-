import os
from h_ast import *
from tokens import TokenType
from bytecode import VM
import time


# Bridge: wrap a list of tokens produced by an H# tokenizer into an object
# compatible with the Python Parser (provides get_next_token()).
class HSharpTokenStream:
    def __init__(self, tokens_list):
        # tokens_list: list of dicts {"type": str, "value": val}
        self.tokens = tokens_list or []
        self.pos = 0

    def _convert_value(self, ttype, val):
        if val is None:
            return None
        if ttype == 'NUMBER':
            try:
                if isinstance(val, (int, float)):
                    return val
                s = str(val)
                if '.' in s:
                    return float(s)
                return int(s)
            except Exception:
                return val
        if ttype == 'BOOL':
            return bool(val)
        # keep strings and other values as-is
        return val

    def get_next_token(self):
        if self.pos >= len(self.tokens):
            return (TokenType.EOF, None)
        tk = self.tokens[self.pos]
        self.pos += 1
        tname = tk.get('type')
        val = tk.get('value')
        # map token name to TokenType enum; if missing, raise
        try:
            ttype = getattr(TokenType, tname)
        except Exception:
            raise HSharpError(f"Unknown token type from H# tokenizer: {tname}")
        return (ttype, self._convert_value(tname, val))

class ReturnException(Exception):
    def __init__(self, value):
        self.value = value

class ContinueException(Exception):
    pass

class BreakException(Exception):
    pass

class HSharpError(Exception):
    pass

# Add polymorphism-related AST nodes
class SuperExpression(AST):
    def __init__(self, method_name, args):
        self.method_name = method_name
        self.args = args

class InstanceOfExpression(AST):
    def __init__(self, expr, type_name):
        self.expr = expr
        self.type_name = type_name

class CastExpression(AST):
    def __init__(self, expr, type_name):
        self.expr = expr
        self.type_name = type_name

# Add polymorphism-related AST nodes
class SuperExpression(AST):
    def __init__(self, method_name, args):
        self.method_name = method_name
        self.args = args

class InstanceOfExpression(AST):
    def __init__(self, expr, type_name):
        self.expr = expr
        self.type_name = type_name

class CastExpression(AST):
    def __init__(self, expr, type_name):
        self.expr = expr
        self.type_name = type_name

class Environment:
    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

    def define(self, name, value):
        self.vars[name] = value

    def assign(self, name, value):
        if name in self.vars:
            self.vars[name] = value
        elif self.parent:
            self.parent.assign(name, value)
        else:
            raise HSharpError(f"Undefined variable: '{name}'")

    def lookup(self, name):
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.lookup(name)
        raise HSharpError(f"Undefined variable: '{name}'")


class CoroYield(Exception):
    pass


class Coroutine:
    def __init__(self, func_node, interpreter, args):
        self.func = func_node
        self.interpreter = interpreter
        # prepare env with params
        self.env = Environment(parent=interpreter.global_env)
        for pname, arg in zip(func_node.params, args):
            self.env.define(pname, arg)
        self.done = False
        self.retval = None
        self.pc = 0
        # stack of frames: each is dict {'stmts': list, 'pc': int, 'env': Environment}
        self.stack = []
        self.waiting = None  # None or ('sleep', until) or ('event', name)
        self.priority = 0

    def resume(self):
        if self.done:
            return self.retval
        prev = self.interpreter._current_coroutine
        self.interpreter._current_coroutine = self
        try:
            # initialize stack with function body if empty
            if not self.stack:
                self.stack.append({'stmts': list(self.func.body.statements), 'pc': 0, 'env': self.env})

            while self.stack:
                frame = self.stack[-1]
                # generator frame
                if 'gen' in frame:
                    gen = frame['gen']
                    try:
                        yielded = next(gen)
                        # if generator yields a suspend tuple, suspend coroutine
                        if isinstance(yielded, tuple) and yielded[0] == 'suspend':
                            return None
                        # otherwise continue running
                        continue
                    except StopIteration as e:
                        # generator finished with value
                            self.stack.pop()
                            # advance parent frame pc so the statement that spawned the gen is not re-run
                            if self.stack:
                                parent = self.stack[-1]
                                if 'pc' in parent:
                                    parent['pc'] = parent.get('pc', 0) + 1
                            continue
                else:
                    stmts = frame['stmts']
                    pc = frame['pc']
                    if pc >= len(stmts):
                        # pop finished frame
                        self.stack.pop()
                        continue
                    stmt = stmts[pc]
                    try:
                        # execute a single statement in coroutine-aware mode
                        finished = self.interpreter.execute_stmt_for_coro(stmt, frame['env'], self)
                        if finished is True:
                            # statement completed normally
                            frame['pc'] += 1
                            continue
                        # if finished is False, it means control transferred (e.g., pushed new frame)
                        # in that case do not advance pc here
                        continue
                    except CoroYield:
                        # suspend: advance pc so resume continues after this statement
                        frame['pc'] += 1
                        return None
            # no frames left: finished
            self.done = True
            return self.retval
        except ReturnException as e:
            self.retval = e.value
            self.done = True
            return self.retval
        finally:
            self.interpreter._current_coroutine = prev
        # finished without explicit return
        self.done = True
        return None

# --- Built-in Functions ---

def builtin_len(args):
    if len(args) != 1:
        raise HSharpError("len() takes exactly 1 argument")
    obj = args[0]
    if isinstance(obj, list):
        return len(obj)
    elif isinstance(obj, str):
        return len(obj)
    elif isinstance(obj, dict):
        return len(obj)
    else:
        raise HSharpError("len() argument must be array, dict, or string")

def builtin_push(args):
    if len(args) != 2:
        raise HSharpError("push(arr, x) takes exactly 2 arguments")
    arr, x = args
    if not isinstance(arr, list):
        raise HSharpError("First argument to push must be an array")
    arr.append(x)
    return None

def builtin_pop(args):
    if len(args) != 1:
        raise HSharpError("pop(arr) takes exactly 1 argument")
    arr = args[0]
    if not isinstance(arr, list):
        raise HSharpError("Argument to pop must be an array")
    if not arr:
        raise HSharpError("Cannot pop from empty array")
    return arr.pop()

def builtin_read_file(args):
    if len(args) != 1:
        raise HSharpError("read_file(path) takes exactly 1 argument")
    path = args[0]
    if not isinstance(path, str):
        raise HSharpError("File path must be a string")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        raise HSharpError(f"Failed to read file '{path}': {e}")

def builtin_write_file(args):
    if len(args) != 2:
        raise HSharpError("write_file(path, content) takes exactly 2 arguments")
    path, content = args
    if not isinstance(path, str) or not isinstance(content, str):
        raise HSharpError("Arguments must be strings")
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return None
    except Exception as e:
        raise HSharpError(f"Failed to write file '{path}': {e}")

def builtin_input(args):
    if len(args) > 1:
        raise HSharpError("input() takes at most 1 argument")
    if args:
        prompt = args[0]
        if not isinstance(prompt, str):
            raise HSharpError("input() argument must be a string")
        return input(prompt)
    else:
        return input()

def builtin_input(args):
    if len(args) > 1:
        raise HSharpError("input() takes at most 1 argument")
    if args:
        prompt = args[0]
        if not isinstance(prompt, str):
            raise HSharpError("input() argument must be a string")
        return input(prompt)
    else:
        return input()

class Interpreter:
    def __init__(self, global_env=None, functions=None):
        self.global_env = global_env or Environment()
        self.functions = functions or {}
        self.interfaces = {}
        self.builtins = {
            'len': builtin_len,
            'push': builtin_push,
            'pop': builtin_pop,
            'read_file': builtin_read_file,
            'write_file': builtin_write_file,
            'input': builtin_input,
            'thread_spawn': self._builtin_thread_spawn,
            'thread_join': self._builtin_thread_join,
            'coro_yield': self._builtin_coro_yield,
            'coro_resume': self._builtin_coro_resume,
            'coro_sleep': self._builtin_coro_sleep,
            'coro_wait': self._builtin_coro_wait,
            'coro_signal': self._builtin_coro_signal,
            'coro_signal_io': self._builtin_coro_signal_io,
            'scheduler_run': self._builtin_scheduler_run,
        }

        self._current_coroutine = None
        self._event_waiters = {}
        self._io_waiters = {}

    def _dict_to_ast(self, node):
        """Convert a serialized AST (from H# parser) into Python h_ast objects.
        Expected node format (examples):
        {"type": "Program", "statements": [...]}
        {"type": "LetStatement", "name": "x", "value": {...}}
        Expressions similarly: {"type":"Identifier","name":"x"},
        {"type":"NumberLiteral","value": 1}
        This is a conservative converter for common node types used in bootstrap.
        """
        if node is None:
            return None
        # Accept two serialized forms from the H# parser: dict-based or list-based positional.
        if isinstance(node, list):
            t = node[0]
            if t == 'Program':
                stmts = [self._dict_to_ast(s) for s in node[1]]
                return Program(stmts)
            if t == 'LetStatement':
                name = node[1]
                val = self._dict_to_ast(node[2])
                return LetStatement(name, val)
            if t == 'PrintStatement':
                expr = self._dict_to_ast(node[1])
                return PrintStatement(expr)
            if t == 'ReturnStatement':
                expr = self._dict_to_ast(node[1])
                return ReturnStatement(expr)
            if t == 'Function':
                name = node[1]
                params = node[2] or []
                body = self._dict_to_ast(node[3])
                return Function(name, params, body)
            if t == 'BlockStatement':
                stm = [self._dict_to_ast(s) for s in node[1]]
                return BlockStatement(stm)
            if t == 'WhileStatement':
                cond = self._dict_to_ast(node[1])
                body = self._dict_to_ast(node[2])
                return WhileStatement(cond, body)
            if t == 'IfStatement':
                cond = self._dict_to_ast(node[1])
                cons = self._dict_to_ast(node[2])
                alt = self._dict_to_ast(node[3]) if node[3] else None
                return IfStatement(cond, cons, alt)
            # expressions
            if t == 'Identifier':
                return Identifier(node[1])
            if t == 'NumberLiteral':
                return NumberLiteral(node[1])
            if t == 'StringLiteral':
                return StringLiteral(node[1])
            if t == 'BooleanLiteral':
                return BooleanLiteral(node[1])
            if t == 'NullLiteral':
                return NullLiteral()
            if t == 'CallExpression':
                func = self._dict_to_ast(node[1])
                args = [self._dict_to_ast(a) for a in node[2]]
                return CallExpression(func, args)
            if t == 'BinaryOp':
                left = self._dict_to_ast(node[1])
                op = node[2]
                right = self._dict_to_ast(node[3])
                # map op name to TokenType if possible
                if isinstance(op, str):
                    try:
                        op_token = getattr(TokenType, op)
                    except Exception:
                        symmap = {'+':'PLUS','-':'MINUS','*':'STAR','/':'SLASH','==':'EQEQ','!=':'BANGEQ','>':'GT','<':'LT','>=':'GTE','<=':'LTE','&':'BITAND','|':'BITOR','^':'BITXOR','<<':'LSHIFT','>>':'RSHIFT'}
                        opname = symmap.get(op, None)
                        op_token = getattr(TokenType, opname) if opname else op
                else:
                    op_token = op
                return BinaryOp(left, op_token, right)
            if t == 'UnaryOp':
                op = node[1]
                operand = self._dict_to_ast(node[2])
                try:
                    op_token = getattr(TokenType, op)
                except Exception:
                    op_token = op
                return UnaryOp(op_token, operand)
            # array / dict / index / member
            if t == 'ArrayLiteral':
                elems = [self._dict_to_ast(e) for e in node[1]]
                return ArrayLiteral(elems)
            if t == 'DictLiteral':
                pairs = []
                for k, v in node[1]:
                    pairs.append((self._dict_to_ast(k), self._dict_to_ast(v)))
                return DictLiteral(pairs)
            if t == 'IndexExpression':
                left = self._dict_to_ast(node[1])
                index = self._dict_to_ast(node[2])
                return IndexExpression(left, index)
            if t == 'MemberExpression':
                left = self._dict_to_ast(node[1])
                name = node[2]
                return MemberExpression(left, name)
            # assignments
            if t == 'AssignmentIndex':
                arr = self._dict_to_ast(node[1])
                index = self._dict_to_ast(node[2])
                val = self._dict_to_ast(node[3])
                return AssignmentIndex(arr, index, val)
            if t == 'AssignmentMember':
                left = self._dict_to_ast(node[1])
                name = node[2]
                val = self._dict_to_ast(node[3])
                return AssignmentMember(left, name, val)
            if t == 'AssignmentIdentifier':
                name = node[1]
                val = self._dict_to_ast(node[2])
                return AssignmentIdentifier(name, val)
            # for / lambda / new / super / instanceof / cast
            if t == 'ForStatement':
                var1 = node[1]
                var2 = node[2]
                iterable = self._dict_to_ast(node[3])
                body = self._dict_to_ast(node[4])
                return ForStatement(var1, var2, iterable, body)
            if t == 'Lambda':
                params = node[1] or []
                body = self._dict_to_ast(node[2])
                return Lambda(params, body)
            if t == 'NewExpression':
                cname = node[1]
                args = [self._dict_to_ast(a) for a in node[2]]
                return NewExpression(cname, args)
            if t == 'SuperExpression':
                mname = node[1]
                args = [self._dict_to_ast(a) for a in node[2]]
                return SuperExpression(mname, args)
            if t == 'InstanceOfExpression':
                expr = self._dict_to_ast(node[1])
                type_name = node[2]
                return InstanceOfExpression(expr, type_name)
            if t == 'CastExpression':
                expr = self._dict_to_ast(node[1])
                type_name = node[2]
                return CastExpression(expr, type_name)
            # declarations / module / concept / asm / pointer
            if t == 'ModuleDeclaration':
                name = node[1]
                body = self._dict_to_ast(node[2])
                return ModuleDeclaration(name, body)
            if t == 'ConceptDeclaration':
                name = node[1]
                body = self._dict_to_ast(node[2]) if node[2] else None
                return ConceptDeclaration(name, body)
            if t == 'AsmBlock':
                return AsmBlock(node[1])
            if t == 'PointerDereference':
                target = self._dict_to_ast(node[1])
                return PointerDereference(target)
            if t == 'ContinueStatement':
                return ContinueStatement()
            if t == 'BreakStatement':
                return BreakStatement()
            if t == 'CoroFunction':
                return CoroFunction(node[1], node[2] or [], self._dict_to_ast(node[3]))
        if not isinstance(node, dict):
            raise HSharpError("Invalid AST node from H# parser")
        t = node.get('type')
        if t == 'Program':
            stmts = [self._dict_to_ast(s) for s in node.get('statements', [])]
            return Program(stmts)
        if t == 'LetStatement':
            name = node.get('name')
            val = self._dict_to_ast(node.get('value'))
            return LetStatement(name, val)
        if t == 'PrintStatement':
            expr = self._dict_to_ast(node.get('expr'))
            return PrintStatement(expr)
        if t == 'ReturnStatement':
            expr = self._dict_to_ast(node.get('expr'))
            return ReturnStatement(expr)
        if t == 'Function':
            name = node.get('name')
            params = node.get('params', []) or []
            body = self._dict_to_ast(node.get('body'))
            return Function(name, params, body)
        if t == 'BlockStatement':
            stm = [self._dict_to_ast(s) for s in node.get('statements', [])]
            return BlockStatement(stm)
        if t == 'WhileStatement':
            cond = self._dict_to_ast(node.get('condition'))
            body = self._dict_to_ast(node.get('body'))
            return WhileStatement(cond, body)
        if t == 'IfStatement':
            cond = self._dict_to_ast(node.get('condition'))
            cons = self._dict_to_ast(node.get('consequence'))
            alt = self._dict_to_ast(node.get('alternative')) if node.get('alternative') else None
            return IfStatement(cond, cons, alt)
        if t == 'ForStatement':
            var1 = node.get('var1')
            var2 = node.get('var2')
            iterable = self._dict_to_ast(node.get('iterable'))
            body = self._dict_to_ast(node.get('body'))
            return ForStatement(var1, var2, iterable, body)
        # Expressions
        if t == 'Identifier':
            return Identifier(node.get('name'))
        if t == 'NumberLiteral':
            return NumberLiteral(node.get('value'))
        if t == 'StringLiteral':
            return StringLiteral(node.get('value'))
        if t == 'BooleanLiteral':
            return BooleanLiteral(node.get('value'))
        if t == 'NullLiteral':
            return NullLiteral()
        if t == 'ArrayLiteral':
            elems = [self._dict_to_ast(e) for e in node.get('elements', [])]
            return ArrayLiteral(elems)
        if t == 'DictLiteral':
            pairs = []
            for k, v in node.get('pairs', []):
                pairs.append((self._dict_to_ast(k), self._dict_to_ast(v)))
            return DictLiteral(pairs)
        if t == 'IndexExpression':
            left = self._dict_to_ast(node.get('left'))
            index = self._dict_to_ast(node.get('index'))
            return IndexExpression(left, index)
        if t == 'MemberExpression':
            left = self._dict_to_ast(node.get('left'))
            name = node.get('name')
            return MemberExpression(left, name)
        if t == 'CallExpression':
            func = self._dict_to_ast(node.get('func'))
            args = [self._dict_to_ast(a) for a in node.get('args', [])]
            return CallExpression(func, args)
        if t == 'BinaryOp':
            left = self._dict_to_ast(node.get('left'))
            right = self._dict_to_ast(node.get('right'))
            op = node.get('op')
            # map op name to TokenType if possible
            if isinstance(op, str):
                try:
                    op_token = getattr(TokenType, op)
                except Exception:
                    # map symbols
                    symmap = {'+':'PLUS','-':'MINUS','*':'STAR','/':'SLASH','==':'EQEQ','!=':'BANGEQ','>':'GT','<':'LT','>=':'GTE','<=':'LTE','&':'BITAND','|':'BITOR','^':'BITXOR','<<':'LSHIFT','>>':'RSHIFT'}
                    opname = symmap.get(op, None)
                    op_token = getattr(TokenType, opname) if opname else op
            else:
                op_token = op
            return BinaryOp(left, op_token, right)
        if t == 'UnaryOp':
            op = node.get('op')
            operand = self._dict_to_ast(node.get('operand'))
            # map op string to TokenType
            try:
                op_token = getattr(TokenType, op)
            except Exception:
                op_token = op
            return UnaryOp(op_token, operand)
        # assignments
        if t == 'AssignmentIndex':
            arr = self._dict_to_ast(node.get('array'))
            index = self._dict_to_ast(node.get('index'))
            val = self._dict_to_ast(node.get('value'))
            return AssignmentIndex(arr, index, val)
        if t == 'AssignmentMember':
            left = self._dict_to_ast(node.get('left'))
            name = node.get('name')
            val = self._dict_to_ast(node.get('value'))
            return AssignmentMember(left, name, val)
        if t == 'AssignmentIdentifier':
            name = node.get('name')
            val = self._dict_to_ast(node.get('value'))
            return AssignmentIdentifier(name, val)
        if t == 'CoroFunction':
            name = node.get('name')
            params = node.get('params', []) or []
            body = self._dict_to_ast(node.get('body'))
            return CoroFunction(name, params, body)
        # fallback
        raise HSharpError(f"Unsupported AST node type from H# parser: {t}")

    def interpret(self, program, env=None):
        env = env or self.global_env
        try:
            for stmt in program.statements:
                result = self.execute(stmt, env)
                if isinstance(result, ReturnException):
                    return result.value
        except HSharpError as e:
            print(f"Runtime Error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

    def execute(self, stmt, env):
        method_name = f'visit_{type(stmt).__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(stmt, env)

    def generic_visit(self, node, env):
        raise Exception(f'No visit_{type(node).__name__} method')

    def visit_LetStatement(self, stmt, env):
        value = self.eval_expr(stmt.value, env)
        env.define(stmt.name, value)

    def visit_PrintStatement(self, stmt, env):
        value = self.eval_expr(stmt.expr, env)
        print(value)

    def visit_ImportStatement(self, stmt, env):
        # stmt.path may be a string ("file.hto") or an Identifier (module name)
        path = stmt.path
        # import a local H# file when given a string literal
        if isinstance(path, str):
            if not path.endswith('.hto'):
                path += '.hto'
            if not os.path.exists(path):
                raise HSharpError(f"Module not found: {path}")
            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()
            # If an H# tokenizer `tokenize` is available in this interpreter (self.functions),
            # prefer to use it to produce tokens. If an H# `parse` is also available,
            # call it and convert the returned dict-structured AST into Python AST objects.
            program = None
            try:
                if 'tokenize' in self.functions:
                    call_tok = CallExpression(Identifier('tokenize'), [StringLiteral(code)])
                    tokens_list = self.visit_CallExpression(call_tok, env)
                    # if an H# parser is available, call it with tokens_list
                    if 'parse' in self.functions:
                        call_parse = CallExpression(Identifier('parse'), [Identifier('TOK_PLACEHOLDER')])
                        # direct call into H# parse: bypassing evaluation, so use visit_CallExpression but
                        # we need parse to accept raw Python list; our visit_CallExpression expects expressions,
                        # so instead call parse by invoking the callable directly if present in self.functions
                        parse_fn = self.functions.get('parse')
                        try:
                            ast_dict = None
                            # If parse_fn is a Python-callable (unlikely), call directly
                            if callable(parse_fn):
                                ast_dict = parse_fn(tokens_list)
                            else:
                                # otherwise, call via interpreter by creating a temporary callable wrapper
                                ast_dict = self.visit_CallExpression(CallExpression(Identifier('parse'), []), env)
                        except Exception:
                            ast_dict = None
                        if ast_dict is not None:
                            # convert serialized AST (dict) to h_ast objects
                            program = self._dict_to_ast(ast_dict)
                            if program is None:
                                # fallback to building parser stream
                                stream = HSharpTokenStream(tokens_list)
                                from parser import Parser
                                parser = Parser(stream)
                                program = parser.parse()
                            # else we have a Program
                    else:
                        # no H# parser: feed tokens into Python Parser via wrapper stream
                        stream = HSharpTokenStream(tokens_list)
                        from parser import Parser
                        parser = Parser(stream)
                        program = parser.parse()
            except Exception:
                program = None
            if program is None:
                from lexer import Lexer
                from parser import Parser
                lexer = Lexer(code)
                parser = Parser(lexer)
                program = parser.parse()
            # run in the current env (imported names populate current env)
            sub_interpreter = Interpreter(global_env=env, functions=self.functions)
            sub_interpreter.interpret(program, env)
            # merge interfaces from imported module
            if hasattr(sub_interpreter, 'interfaces'):
                self.interfaces.update(sub_interpreter.interfaces)
        else:
            # assume Identifier: try to import a Python module of that name
            if isinstance(path, Identifier):
                modname = path.name
            else:
                raise HSharpError('Unsupported import path')
            try:
                import importlib
                mod = importlib.import_module(modname)
            except Exception as e:
                raise HSharpError(f"Failed to import Python module '{modname}': {e}")
            # wrap module into a simple H#-friendly dict exposing attributes
            proxy = {}
            for attr in dir(mod):
                if attr.startswith('_'):
                    continue
                try:
                    val = getattr(mod, attr)
                except Exception:
                    continue
                # allow functions and simple objects; leave as-is
                proxy[attr] = val
            env.define(modname, proxy)

    def _builtin_thread_spawn(self, args):
        if len(args) != 1:
            raise HSharpError('thread_spawn(func) takes exactly 1 argument')
        fn = args[0]
        import threading

        def target_callable():
            try:
                if isinstance(fn, dict) and 'body' in fn:
                    # interpreter-style function/closure
                    call_env = Environment(parent=self.global_env)
                    for pname in fn.get('params', []):
                        # no args supported for now
                        call_env.define(pname, None)
                    self.visit_BlockStatement(fn['body'], call_env)
                elif isinstance(fn, dict) and 'bytecode' in fn:
                    # compiled function-like object for interpreter: run via VM
                    vm = VM({'instructions': fn['bytecode'], 'consts': fn.get('consts', [])})
                    vm.run()
                elif callable(fn):
                    fn()
                else:
                    raise HSharpError('Unsupported callable passed to thread_spawn')
            except Exception as e:
                print(f"Thread error: {e}")

        t = threading.Thread(target=target_callable)
        t.start()
        return t

    def _builtin_thread_join(self, args):
        if len(args) != 1:
            raise HSharpError('thread_join(t) takes exactly 1 argument')
        t = args[0]
        try:
            t.join()
            return None
        except Exception as e:
            raise HSharpError(f'Error joining thread: {e}')

    # --- Coroutine support (cooperative generator-style) ---
    def _builtin_coro_yield(self, args):
        # coro_yield(): plain yield
        # coro_yield(event_name:str): wait for event
        # coro_yield(seconds: number): sleep for seconds
        coro = self._current_coroutine
        if coro is None:
            raise HSharpError('coro_yield must be called inside a coroutine')
        if len(args) == 0:
            raise CoroYield()
        if len(args) == 1:
            a = args[0]
            if isinstance(a, (int, float)):
                coro.waiting = ('sleep', time.time() + float(a))
                raise CoroYield()
            if isinstance(a, str):
                coro.waiting = ('event', a)
                self._event_waiters.setdefault(a, []).append(coro)
                raise CoroYield()
        raise HSharpError('coro_yield takes 0 or 1 argument')

    def _builtin_coro_resume(self, args):
        if len(args) != 1:
            raise HSharpError('coro_resume(coro) takes exactly 1 argument')
        coro = args[0]
        if not isinstance(coro, Coroutine):
            raise HSharpError('Argument to coro_resume must be a coroutine')
        # debug: indicate resume called
        # print(f"DEBUG: coro_resume called on {coro}")
        return coro.resume()

    def _builtin_coro_sleep(self, args):
        if len(args) != 1:
            raise HSharpError('coro_sleep(seconds) takes exactly 1 argument')
        coro = self._current_coroutine
        if coro is None:
            raise HSharpError('coro_sleep must be called inside a coroutine')
        seconds = args[0]
        if not isinstance(seconds, (int, float)):
            raise HSharpError('coro_sleep requires numeric seconds')
        coro.waiting = ('sleep', time.time() + float(seconds))
        raise CoroYield()

    def _builtin_coro_wait(self, args):
        if len(args) != 1:
            raise HSharpError('coro_wait(event) takes exactly 1 argument')
        coro = self._current_coroutine
        if coro is None:
            raise HSharpError('coro_wait must be called inside a coroutine')
        ev = args[0]
        if not isinstance(ev, str):
            raise HSharpError('coro_wait requires an event name string')
        coro.waiting = ('event', ev)
        self._event_waiters.setdefault(ev, []).append(coro)
        raise CoroYield()

    def _builtin_coro_signal(self, args):
        if len(args) != 1:
            raise HSharpError('coro_signal(event) takes exactly 1 argument')
        ev = args[0]
        if not isinstance(ev, str):
            raise HSharpError('coro_signal requires an event name string')
        waiters = self._event_waiters.pop(ev, [])
        for c in waiters:
            if c.waiting and c.waiting[0] == 'event' and c.waiting[1] == ev:
                c.waiting = None
        return None

    def _builtin_coro_signal_io(self, args):
        # signal that an io handle is ready: coro_signal_io(handle)
        if len(args) != 1:
            raise HSharpError('coro_signal_io(handle) takes exactly 1 argument')
        handle = args[0]
        waiters = self._io_waiters.pop(handle, [])
        for c in waiters:
            if c.waiting and c.waiting[0] == 'io' and c.waiting[1] == handle:
                c.waiting = None
        return None

    def _builtin_scheduler_run(self, args):
        # scheduler_run(tasks) - tasks is a list of Coroutine or (Coroutine, priority)
        if len(args) != 1:
            raise HSharpError('scheduler_run(list) takes exactly 1 argument')
        lst = args[0]
        if not isinstance(lst, list):
            raise HSharpError('Argument to scheduler_run must be a list')
        # normalize to dicts with coro and priority
        tasks = []
        for item in lst:
            if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], Coroutine) and isinstance(item[1], (int, float)):
                c = item[0]
                c.priority = int(item[1])
                tasks.append(c)
            elif isinstance(item, Coroutine):
                tasks.append(item)
            else:
                # ignore non-coroutine entries
                continue

        # round-robin with priority: higher priority scheduled earlier each cycle
        while True:
            # filter out finished
            tasks = [c for c in tasks if not c.done]
            if not tasks:
                break
            # sort by priority desc
            tasks.sort(key=lambda c: getattr(c, 'priority', 0), reverse=True)
            progressed = False
            for c in list(tasks):
                # skip if waiting on event/sleep
                if c.waiting:
                    w = c.waiting
                    if w[0] == 'sleep':
                        if time.time() >= w[1]:
                            c.waiting = None
                        else:
                            continue
                    elif w[0] == 'event':
                        # still waiting until someone signals
                        continue
                    elif w[0] == 'io':
                        handle = w[1]
                        # determine readiness: handle can be callable or object with ready()
                        ready = False
                        try:
                            if callable(handle):
                                ready = bool(handle())
                            elif hasattr(handle, 'ready') and callable(getattr(handle, 'ready')):
                                ready = bool(handle.ready())
                            elif hasattr(handle, 'fileno'):
                                # try select on file/socket-like objects
                                try:
                                    import select
                                    r, w, x = select.select([handle], [], [], 0)
                                    ready = bool(r)
                                except Exception:
                                    try:
                                        fd = handle.fileno()
                                        import select
                                        r, w, x = select.select([fd], [], [], 0)
                                        ready = bool(r)
                                    except Exception:
                                        ready = False
                            else:
                                # not a callable/ready-able object; rely on external signal via coro_signal_io
                                ready = False
                        except Exception:
                            ready = False
                        # check timeout
                        until = w[2]
                        if not ready and until is not None and time.time() >= until:
                            # timeout reached; remove from io waiters and optionally call a timeout callback by setting waiting=None
                            c.waiting = None
                            # remove from mapping
                            lst = self._io_waiters.get(handle, [])
                            if c in lst:
                                lst.remove(c)
                            continue
                        if not ready:
                            continue
                        # ready
                        c.waiting = None
                        lst = self._io_waiters.get(handle, [])
                        if c in lst:
                            lst.remove(c)
                res = c.resume()
                progressed = True
            if not progressed:
                # deadlock or all waiting: sleep a short while to wait for timeouts/events
                time.sleep(0.001)
                # re-evaluate waiters; if still nothing progresses after sleep, break to avoid infinite loop
                still = any(not c.done and (c.waiting is None or (c.waiting[0] == 'sleep' and time.time() >= c.waiting[1])) for c in tasks)
                if not still:
                    break
        return None

    def visit_WhileStatement(self, stmt, env):
        while True:
            cond = self.eval_expr(stmt.condition, env)
            if not isinstance(cond, bool):
                raise HSharpError("While condition must be boolean")
            if not cond:
                break
            try:
                result = self.execute_block(stmt.body, env)
            except ContinueException:
                continue
            except BreakException:
                break
            if isinstance(result, ReturnException):
                return result

    def visit_IfStatement(self, stmt, env):
        cond = self.eval_expr(stmt.condition, env)
        if not isinstance(cond, bool):
            raise HSharpError("If condition must be boolean")
        if cond:
            return self.execute_block(stmt.consequence, env)
        elif stmt.alternative:
            if isinstance(stmt.alternative, IfStatement):
                return self.visit_IfStatement(stmt.alternative, env)
            return self.execute_block(stmt.alternative, env)

    def visit_AssignmentIdentifier(self, stmt, env):
        value = self.eval_expr(stmt.value, env)
        env.assign(stmt.name, value)
        return None

    def visit_ContinueStatement(self, stmt, env):
        raise ContinueException()

    def visit_BreakStatement(self, stmt, env):
        raise BreakException()

    def visit_ForStatement(self, stmt, env):
        iterable = self.eval_expr(stmt.iterable, env)
        loop_env = Environment(parent=env)
        if isinstance(iterable, list):
            for item in iterable:
                loop_env.define(stmt.var1, item)
                try:
                    result = self.execute_block(stmt.body, loop_env)
                except ContinueException:
                    continue
                except BreakException:
                    break
                if isinstance(result, ReturnException):
                    return result
        elif isinstance(iterable, dict):
            for k, v in iterable.items():
                loop_env.define(stmt.var1, k)
                if stmt.var2:
                    loop_env.define(stmt.var2, v)
                result = self.execute_block(stmt.body, loop_env)
                if isinstance(result, ReturnException):
                    return result
        elif isinstance(iterable, str):
            for char in iterable:
                loop_env.define(stmt.var1, char)
                try:
                    result = self.execute_block(stmt.body, loop_env)
                except ContinueException:
                    continue
                except BreakException:
                    break
                if isinstance(result, ReturnException):
                    return result
        else:
            raise HSharpError("Can only iterate over array, dict, or string")

    def execute_block(self, block, env):
        block_env = Environment(parent=env)
        for s in block.statements:
            result = self.execute(s, block_env)
            if isinstance(result, ReturnException):
                return result

    def visit_BlockStatement(self, stmt, env):
        # For normal (non-coroutine) execution, execute entire block.
        # For coroutine-driven execution, block stepping is handled by `execute_stmt_for_coro`.
        if self._current_coroutine is None:
            return self.execute_block(stmt, env)
        # if in coroutine, signal caller to push frame
        return None

    def execute_stmt_for_coro(self, stmt, env, coro):
        # Execute a single top-level statement in coroutine mode.
        # Return True if statement completed, False if control transferred (pushed new frame).
        # Handle common statement types directly to maintain frame/pc.
        if isinstance(stmt, BlockStatement):
            # push block's statements as a new frame
            coro.stack.append({'stmts': list(stmt.statements), 'pc': 0, 'env': Environment(parent=env)})
            return False
        if isinstance(stmt, LetStatement):
            self.visit_LetStatement(stmt, env)
            return True
        if isinstance(stmt, PrintStatement):
            self.visit_PrintStatement(stmt, env)
            return True
        if isinstance(stmt, ImportStatement):
            self.visit_ImportStatement(stmt, env)
            return True
        if isinstance(stmt, ReturnStatement):
            # execute return expression and raise to unwind
            val = self.eval_expr(stmt.expr, env)
            raise ReturnException(val)
        if isinstance(stmt, Function):
            self.visit_Function(stmt, env)
            return True
        if isinstance(stmt, ClassDeclaration):
            self.visit_ClassDeclaration(stmt, env)
            return True
        if isinstance(stmt, InterfaceDeclaration):
            self.visit_InterfaceDeclaration(stmt, env)
            return True
        if isinstance(stmt, IfStatement):
            cond = self.eval_expr(stmt.condition, env)
            if not isinstance(cond, bool):
                raise HSharpError("If condition must be boolean")
            if cond:
                coro.stack.append({'stmts': list(stmt.consequence.statements), 'pc': 0, 'env': Environment(parent=env)})
            elif stmt.alternative:
                if isinstance(stmt.alternative, IfStatement):
                    coro.stack.append({'stmts': [stmt.alternative], 'pc': 0, 'env': Environment(parent=env)})
                else:
                    coro.stack.append({'stmts': list(stmt.alternative.statements), 'pc': 0, 'env': Environment(parent=env)})
            return False
        if isinstance(stmt, WhileStatement):
            cond = self.eval_expr(stmt.condition, env)
            if not isinstance(cond, bool):
                raise HSharpError("While condition must be boolean")
            if cond:
                # push a frame that will re-evaluate the condition after body finishes
                coro.stack.append({'stmts': list(stmt.body.statements), 'pc': 0, 'env': Environment(parent=env)})
                # push a sentinel frame to re-check the while (we'll re-push the while stmt)
                coro.stack.append({'stmts': [stmt], 'pc': 0, 'env': env})
            return False
        if isinstance(stmt, ForStatement):
            iterable = self.eval_expr(stmt.iterable, env)
            if isinstance(iterable, list):
                # create a sequence of let assignments + body frames
                combined = []
                for item in iterable:
                    # let var1 = item; then body
                    combined.append(LetStatement(stmt.var1, NumberLiteral(item) if isinstance(item, int) else Identifier(item) if isinstance(item, str) else NumberLiteral(0)))
                    combined.extend(stmt.body.statements)
                coro.stack.append({'stmts': combined, 'pc': 0, 'env': Environment(parent=env)})
                return False
            else:
                raise HSharpError("Can only iterate over array, dict, or string in coroutine for-statement simplified support")
        # Expression statements (call, assignment, member assignment, index assignment)
        # Evaluate expression for side-effects using generator-based evaluator
        if isinstance(stmt, (CallExpression, BinaryOp, UnaryOp, MemberExpression, IndexExpression, AssignmentIndex, AssignmentMember)):
            gen = self.gen_eval_expr(stmt, env)
            coro.stack.append({'gen': gen, 'env': env})
            return False
        # fall back to normal evaluation for other kinds
        try:
            self.eval_expr(stmt, env)
        except CoroYield:
            raise
        return True

    def gen_eval_expr(self, expr, env):
        # Generator-based evaluator for expressions. Yields ('suspend', info) when coroutine should suspend.
        # Always defined as generator.
        if False:
            yield None
        # Literals
        if isinstance(expr, NumberLiteral):
            return expr.value
        if isinstance(expr, StringLiteral):
            return expr.value
        if isinstance(expr, BooleanLiteral):
            return expr.value
        if isinstance(expr, NullLiteral):
            return None
        if isinstance(expr, Identifier):
            return env.lookup(expr.name)
        # Array
        if isinstance(expr, ArrayLiteral):
            res = []
            for e in expr.elements:
                v = yield from self.gen_eval_expr(e, env)
                res.append(v)
            return res
        # Dict
        if isinstance(expr, DictLiteral):
            d = {}
            for kexpr, vexpr in expr.pairs:
                k = yield from self.gen_eval_expr(kexpr, env)
                val = yield from self.gen_eval_expr(vexpr, env)
                d[k] = val
            return d
        # Index
        if isinstance(expr, IndexExpression):
            left = yield from self.gen_eval_expr(expr.left, env)
            index = yield from self.gen_eval_expr(expr.index, env)
            if isinstance(left, list):
                if not isinstance(index, int):
                    raise HSharpError("Array index must be integer")
                if index < 0 or index >= len(left):
                    raise HSharpError("Array index out of bounds")
                return left[index]
            elif isinstance(left, str):
                if not isinstance(index, int):
                    raise HSharpError("String index must be integer")
                if index < 0 or index >= len(left):
                    raise HSharpError("String index out of bounds")
                return left[index]
            elif isinstance(left, dict):
                if index not in left:
                    raise HSharpError(f"Key '{index}' not found in dictionary")
                return left[index]
            else:
                raise HSharpError("Can only index arrays, strings, or dictionaries")
        # Member
        if isinstance(expr, MemberExpression):
            left = yield from self.gen_eval_expr(expr.left, env)
            if isinstance(left, dict) and '__class__' in left:
                if expr.name in left:
                    return left[expr.name]
                class_obj = left['__class__']
                fields = class_obj.get('fields', {})
                if expr.name in fields:
                    return fields[expr.name]
                raise HSharpError(f"Attribute '{expr.name}' not found on instance")
            if isinstance(left, dict):
                if expr.name in left:
                    return left[expr.name]
            raise HSharpError(f"Cannot access attribute '{expr.name}' on non-object")
        # Lambda
        if isinstance(expr, Lambda):
            return {'params': expr.params, 'body': expr.body, 'closure_env': env}
        # New expression
        if isinstance(expr, NewExpression):
            cname = expr.class_name.name if isinstance(expr.class_name, Identifier) else None
            args = []
            for a in expr.args:
                args.append((yield from self.gen_eval_expr(a, env)))
            if cname in self.functions:
                cls = self.functions[cname]
                # naive instantiation
                inst = {'__class__': cls}
                # initialize fields
                for k, v in cls.get('fields', {}).items():
                    inst[k] = v
                return inst
            raise HSharpError(f"Class '{cname}' not found")
        # Call expression
        if isinstance(expr, CallExpression):
            func_node = expr.func
            # evaluate callee
            if isinstance(func_node, Identifier):
                name = func_node.name
                # handle coroutine builtins specially
                if name in ('coro_yield', 'coro_sleep', 'coro_wait'):
                    # evaluate arg if present
                    if expr.args:
                        av = yield from self.gen_eval_expr(expr.args[0], env)
                    else:
                        av = None
                    coro = self._current_coroutine
                    if coro is None:
                        raise HSharpError(f"{name} must be called inside a coroutine")
                    if name == 'coro_yield':
                        if av is None:
                            # plain yield
                            yield ('suspend', None)
                            return None
                        if isinstance(av, (int, float)):
                            coro.waiting = ('sleep', time.time() + float(av))
                            yield ('suspend', ('sleep', coro.waiting[1]))
                            return None
                        if isinstance(av, str):
                            coro.waiting = ('event', av)
                            self._event_waiters.setdefault(av, []).append(coro)
                            yield ('suspend', ('event', av))
                            return None
                    if name == 'coro_sleep':
                        seconds = av
                        if not isinstance(seconds, (int, float)):
                            raise HSharpError('coro_sleep requires numeric seconds')
                        coro.waiting = ('sleep', time.time() + float(seconds))
                        yield ('suspend', ('sleep', coro.waiting[1]))
                        return None
                    if name == 'coro_wait':
                        ev = av
                        if not isinstance(ev, str):
                            raise HSharpError('coro_wait requires event name string')
                        coro.waiting = ('event', ev)
                        self._event_waiters.setdefault(ev, []).append(coro)
                        yield ('suspend', ('event', ev))
                        return None
                    if name == 'coro_wait_io':
                        # coro_wait_io(handle, timeout_seconds=None)
                        handle = av
                        timeout = None
                        if len(expr.args) > 1:
                            timeout = yield from self.gen_eval_expr(expr.args[1], env)
                        if handle is None:
                            raise HSharpError('coro_wait_io requires a handle')
                        until = None
                        if timeout is not None:
                            if not isinstance(timeout, (int, float)):
                                raise HSharpError('timeout must be numeric')
                            until = time.time() + float(timeout)
                        coro.waiting = ('io', handle, until)
                        self._io_waiters.setdefault(handle, []).append(coro)
                        yield ('suspend', ('io', handle, until))
                        return None
                if name == 'coro_signal':
                    ev = None
                    if expr.args:
                        ev = yield from self.gen_eval_expr(expr.args[0], env)
                    if not isinstance(ev, str):
                        raise HSharpError('coro_signal requires event name string')
                    waiters = self._event_waiters.pop(ev, [])
                    for c in waiters:
                        if c.waiting and c.waiting[0] == 'event' and c.waiting[1] == ev:
                            c.waiting = None
                    return None
                # normal function lookup
                # first check builtins
                if name in self.builtins:
                    # evaluate args
                    args = []
                    for a in expr.args:
                        args.append((yield from self.gen_eval_expr(a, env)))
                    # call builtin synchronously
                    return self.builtins[name](args)
                # lookup variable/function
                val = env.lookup(name)
                if callable(val):
                    args = []
                    for a in expr.args:
                        args.append((yield from self.gen_eval_expr(a, env)))
                    return val(*args)
                if isinstance(val, dict) and 'body' in val:
                    # interpreter closure
                    args = []
                    for a in expr.args:
                        args.append((yield from self.gen_eval_expr(a, env)))
                    call_env = Environment(parent=val.get('closure_env', self.global_env))
                    for pname, argval in zip(val.get('params', []), args):
                        call_env.define(pname, argval)
                    # push function body as new frame
                    gen = self.gen_eval_stmt_block(val['body'], call_env)
                    result = yield from gen
                    return result
                # otherwise it might be a named function in self.functions
                if name in self.functions:
                    func = self.functions[name]
                    # evaluate args first
                    args = []
                    for a in expr.args:
                        args.append((yield from self.gen_eval_expr(a, env)))
                    # coroutine function: return Coroutine object
                    if isinstance(func, Function) and getattr(func, 'is_coro', False):
                        coro = Coroutine(func, self, args)
                        return coro
                    if isinstance(func, Function):
                        # create new environment and execute function body as generator
                        call_env = Environment(parent=self.global_env)
                        for pname, argval in zip(func.params, args):
                            call_env.define(pname, argval)
                        gen = self.gen_eval_stmt_block(func.body, call_env)
                        result = yield from gen
                        return result
                    elif isinstance(func, dict) and 'methods' in func:
                        raise HSharpError(f"'{name}' is a class, cannot call directly")
            else:
                # callee is an expression
                callee = yield from self.gen_eval_expr(func_node, env)
                args = []
                for a in expr.args:
                    args.append((yield from self.gen_eval_expr(a, env)))
                if callable(callee):
                    return callee(*args)
                if isinstance(callee, dict) and 'body' in callee:
                    call_env = Environment(parent=callee.get('closure_env', self.global_env))
                    for pname, argval in zip(callee.get('params', []), args):
                        call_env.define(pname, argval)
                    gen = self.gen_eval_stmt_block(callee['body'], call_env)
                    result = yield from gen
                    return result
                raise HSharpError('Unsupported call expression')
        # BinaryOp
        if isinstance(expr, BinaryOp):
            left = yield from self.gen_eval_expr(expr.left, env)
            right = yield from self.gen_eval_expr(expr.right, env)
            op = expr.op
            if op == TokenType.PLUS:
                if isinstance(left, str) or isinstance(right, str):
                    return str(left) + str(right)
                if isinstance(left, list) and isinstance(right, list):
                    return left + right
                self._ensure_number(left, right)
                return left + right
            elif op == TokenType.MINUS:
                self._ensure_number(left, right)
                return left - right
            elif op == TokenType.STAR:
                self._ensure_number(left, right)
                return left * right
            elif op == TokenType.SLASH:
                self._ensure_number(left, right)
                if right == 0:
                    raise HSharpError("Division by zero")
                return left // right
            elif op == TokenType.EQEQ:
                return left == right
            elif op == TokenType.BANGEQ:
                return left != right
            elif op == TokenType.GT:
                self._ensure_comparable(left, right)
                return left > right
            elif op == TokenType.LT:
                self._ensure_comparable(left, right)
                return left < right
            elif op == TokenType.GTE:
                self._ensure_comparable(left, right)
                return left >= right
            elif op == TokenType.LTE:
                self._ensure_comparable(left, right)
                return left <= right
            elif op == TokenType.AND:
                if not isinstance(left, bool):
                    raise HSharpError("Operands of 'and' must be boolean")
                if not left:
                    return False
                if not isinstance(right, bool):
                    raise HSharpError("Operands of 'and' must be boolean")
                return right
            elif op == TokenType.OR:
                if not isinstance(left, bool):
                    raise HSharpError("Operands of 'or' must be boolean")
                if left:
                    return True
                if not isinstance(right, bool):
                    raise HSharpError("Operands of 'or' must be boolean")
                return right
            elif op == TokenType.BITAND:
                if not isinstance(left, int) or not isinstance(right, int):
                    raise HSharpError('Bitwise operations require integer operands')
                return left & right
            elif op == TokenType.BITOR:
                if not isinstance(left, int) or not isinstance(right, int):
                    raise HSharpError('Bitwise operations require integer operands')
                return left | right
            elif op == TokenType.BITXOR:
                if not isinstance(left, int) or not isinstance(right, int):
                    raise HSharpError('Bitwise operations require integer operands')
                return left ^ right
            elif op == TokenType.LSHIFT:
                if not isinstance(left, int) or not isinstance(right, int):
                    raise HSharpError('Shift operations require integer operands')
                return left << right
            elif op == TokenType.RSHIFT:
                if not isinstance(left, int) or not isinstance(right, int):
                    raise HSharpError('Shift operations require integer operands')
                return left >> right
            else:
                raise HSharpError(f"Unknown operator: {op}")
        # UnaryOp
        if isinstance(expr, UnaryOp):
            if expr.op == TokenType.NOT:
                val = yield from self.gen_eval_expr(expr.operand, env)
                if not isinstance(val, bool):
                    raise HSharpError("'not' operand must be boolean")
                return not val
            elif expr.op == TokenType.TILDE:
                val = yield from self.gen_eval_expr(expr.operand, env)
                if not isinstance(val, int):
                    raise HSharpError("'~' operand must be integer")
                return ~val
            else:
                raise HSharpError(f"Unknown unary operator: {expr.op}")
        raise HSharpError(f"Unknown expression: {expr}")

    def gen_eval_stmt_block(self, block, env):
        # generator that evaluates all statements in a block sequentially
        for s in block.statements:
            # for each statement, if it's an expression-type, yield from its generator
            if isinstance(s, (CallExpression, BinaryOp, UnaryOp, MemberExpression, IndexExpression, AssignmentIndex, AssignmentMember)):
                yield from self.gen_eval_expr(s, env)
            else:
                # reuse existing visit_ methods for side-effects
                self.execute(s, env)
        return None

    def visit_ReturnStatement(self, stmt, env):
        value = self.eval_expr(stmt.expr, env)
        raise ReturnException(value)

    def visit_Function(self, stmt, env):
        self.functions[stmt.name] = stmt

    def visit_CoroFunction(self, stmt, env):
        # register coroutine function; mark as coroutine for runtime
        try:
            setattr(stmt, 'is_coro', True)
        except Exception:
            pass
        self.functions[stmt.name] = stmt

    def visit_ModuleDeclaration(self, stmt, env):
        # execute module body in isolated env and expose as dict
        mod_env = Environment()
        # run statements in module body
        for s in stmt.body.statements:
            self.execute(s, mod_env)
        # export names
        proxy = {}
        for k, v in mod_env.vars.items():
            proxy[k] = v
        try:
            env.define(stmt.name, proxy)
        except Exception:
            self.global_env.define(stmt.name, proxy)

    def visit_ConceptDeclaration(self, stmt, env):
        # store concept as interface-like entry
        methods = {}
        if stmt.body:
            for s in stmt.body.statements:
                if isinstance(s, Function):
                    methods[s.name] = s
        iface = {'name': stmt.name, 'methods': methods, 'body': stmt.body}
        self.interfaces[stmt.name] = iface

    def visit_AsmBlock(self, stmt, env):
        # Inline asm placeholder - store raw code under a special name or ignore
        # For now we simply attach asm text to env as `_last_asm` and return None
        env.define('_last_asm', stmt.code)
        return None

    def visit_ClassDeclaration(self, stmt, env):
        # collect methods and fields, support inheritance and private fields
        methods = {}
        fields = {}
        private = []
        for s in stmt.body.statements:
            if isinstance(s, Function):
                if getattr(s, 'is_static', False):
                    methods.setdefault('__static__', {})[s.name] = s
                else:
                    methods[s.name] = s
            elif isinstance(s, FieldDeclaration):
                # evaluate default in global env (only simple literals expected)
                fields[s.name] = self.eval_expr(s.value, self.global_env)
                if s.is_private:
                    private.append(s.name)
        class_obj = {'name': stmt.name, 'methods': methods, 'fields': fields, 'private': private}
        # handle inheritance by merging base if present
        if getattr(stmt, 'base', None):
            base_name = stmt.base
            base = None
            try:
                base = self.functions.get(base_name) or self.global_env.lookup(base_name)
            except HSharpError:
                base = None
            if not base:
                raise HSharpError(f"Base class not found: {base_name}")
            # merge base methods/fields/private
            merged_methods = {}
            merged_fields = {}
            merged_private = []
            if isinstance(base, dict):
                merged_methods.update(base.get('methods', {}))
                merged_fields.update(base.get('fields', {}))
                merged_private.extend(base.get('private', []))
            merged_methods.update(methods)
            merged_fields.update(fields)
            merged_private.extend(private)
            class_obj['methods'] = merged_methods
            class_obj['fields'] = merged_fields
            class_obj['private'] = merged_private

        # expose static methods at top-level for easier lookup
        if '__static__' in class_obj.get('methods', {}):
            class_obj['__static__'] = class_obj['methods'].pop('__static__')

        self.functions[stmt.name] = class_obj
        # also expose class name in the current environment for lookup (e.g. A.hello())
        try:
            env.define(stmt.name, class_obj)
        except Exception:
            # if env doesn't support define, fallback to global env
            self.global_env.define(stmt.name, class_obj)
        # verify interface implementations
        for iface_name in getattr(stmt, 'implements', []) or []:
            iface = self.interfaces.get(iface_name)
            if iface is None:
                raise HSharpError(f"Interface '{iface_name}' not found for class '{stmt.name}'")
            # iface.methods contains merged methods from bases; entries may be Function nodes (with body for defaults)
            for mname, sig in iface.get('methods', {}).items():
                found = class_obj['methods'].get(mname)
                if not found:
                    # if interface provides a default implementation (Function with body), copy it into class
                    if isinstance(sig, Function) and sig.body is not None:
                        class_obj['methods'][mname] = sig
                        continue
                    raise HSharpError(f"Class '{stmt.name}' does not implement interface method '{mname}' from '{iface_name}'")
                # check arity
                if len(found.params) != len(sig.params):
                    raise HSharpError(f"Method '{mname}' in class '{stmt.name}' has wrong arity for interface '{iface_name}'")

    def visit_CallExpression(self, expr, env):
        args = [self.eval_expr(arg, env) for arg in expr.args]
        # function can be Identifier or MemberExpression or other
        if isinstance(expr.func, Identifier):
            name = expr.func.name
            if name in self.builtins:
                return self.builtins[name](args)
            # first check local/global variables (let-bound functions or values)
            try:
                val = env.lookup(name)
            except HSharpError:
                val = None
            if val is not None:
                # variable may be a callable value (closure or Python callable)
                if callable(val):
                    try:
                        return val(*args)
                    except Exception as e:
                        raise HSharpError(f'Error calling external function: {e}')
                if isinstance(val, dict):
                    # interpreter lambda/closure representation
                    if 'body' in val:
                        closure = val.get('closure_env', self.global_env)
                        call_env = Environment(parent=closure)
                        if len(args) != len(val.get('params', [])):
                            raise HSharpError(f"Function expects {len(val.get('params', []))} arguments, got {len(args)}")
                        for param, arg in zip(val.get('params', []), args):
                            call_env.define(param, arg)
                        try:
                            self.visit_BlockStatement(val['body'], call_env)
                        except ReturnException as e:
                            return e.value
                        return None
                # fallthrough to error if not callable
                raise HSharpError(f"Variable '{name}' is not a function")
            if name not in self.functions:
                raise HSharpError(f"Function '{name}' not defined")
            func = self.functions[name]
            if isinstance(func, dict) and 'methods' in func:
                raise HSharpError(f"'{name}' is a class, cannot call directly")
            # coroutine function: return a Coroutine object (cooperative)
            if (isinstance(func, Function) or isinstance(func, CoroFunction)) and getattr(func, 'is_coro', False):
                coro = Coroutine(func, self, args)
                return coro
            if len(args) != len(func.params):
                raise HSharpError(f"Function '{name}' expects {len(func.params)} arguments, got {len(args)}")
            call_env = Environment(parent=self.global_env)
            for param, arg in zip(func.params, args):
                call_env.define(param, arg)
            try:
                self.visit_BlockStatement(func.body, call_env)
            except ReturnException as e:
                return e.value
            return None
        elif isinstance(expr.func, MemberExpression):
            # method call: evaluate left to get instance
                left = self.eval_expr(expr.func.left, env)
                attr = expr.func.name
                # If left is a Python module proxy (dict), allow calling its callable attributes
                if isinstance(left, dict) and attr in left:
                    val = left.get(attr)
                    if callable(val):
                        try:
                            return val(*args)
                        except Exception as e:
                            raise HSharpError(f"Error calling external function '{attr}': {e}")
                    else:
                        raise HSharpError(f"Attribute '{attr}' on module is not callable")
                # If left is a class object (dict without '__class__'), support static methods
                if isinstance(left, dict) and '__class__' not in left:
                    static_map = left.get('__static__', {})
                    if attr in static_map:
                        method = static_map[attr]
                        if len(args) != len(method.params):
                            raise HSharpError(f"Method '{attr}' expects {len(method.params)} arguments, got {len(args)}")
                        call_env = Environment(parent=self.global_env)
                        for param, arg in zip(method.params, args):
                            call_env.define(param, arg)
                        try:
                            self.visit_BlockStatement(method.body, call_env)
                        except ReturnException as e:
                            return e.value
                        return None
                # If left is a real Python object (module or other), try getattr
                try:
                    if not isinstance(left, dict) and hasattr(left, attr):
                        val = getattr(left, attr)
                        if callable(val):
                            try:
                                return val(*args)
                            except Exception as e:
                                raise HSharpError(f"Error calling external function '{attr}': {e}")
                        else:
                            raise HSharpError(f"Attribute '{attr}' on object is not callable")
                except Exception:
                    # fallthrough to existing H# object method handling
                    pass
                # method call on H# object instances
                if not isinstance(left, dict) or '__class__' not in left:
                    raise HSharpError('Left side of member call is not an object')
                class_obj = left['__class__']
                methods = class_obj.get('methods', {})
                if attr not in methods:
                    # may be callable field
                    val = left.get(attr)
                    if callable(val):
                        return val(*args)
                    raise HSharpError(f"Attribute '{attr}' not found on instance")
                method = methods[attr]
                call_env = Environment(parent=self.global_env)
                call_env.define('self', left)
                if len(args) != len(method.params):
                    raise HSharpError(f"Method '{attr}' expects {len(method.params)} arguments, got {len(args)}")
                for param, arg in zip(method.params, args):
                    call_env.define(param, arg)
                try:
                    self.visit_BlockStatement(method.body, call_env)
                except ReturnException as e:
                    return e.value
                return None
        else:
            # general callable value: evaluate function value then call
            func_val = self.eval_expr(expr.func, env)
            # Python callable
            if callable(func_val):
                try:
                    return func_val(*args)
                except Exception as e:
                    raise HSharpError(f'Error calling external function: {e}')
            # interpreter lambda/closure representation
            if isinstance(func_val, dict) and 'body' in func_val:
                closure = func_val.get('closure_env', self.global_env)
                call_env = Environment(parent=closure)
                if len(args) != len(func_val.get('params', [])):
                    raise HSharpError(f'Function expects {len(func_val.get("params", []))} arguments, got {len(args)}')
                for param, arg in zip(func_val.get('params', []), args):
                    call_env.define(param, arg)
                try:
                    self.visit_BlockStatement(func_val['body'], call_env)
                except ReturnException as e:
                    return e.value
                return None
            raise HSharpError('Unsupported call expression')
    def visit_SuperExpression(self, expr, env):
        # Get self from current environment
        if 'self' not in env.vars:
            raise HSharpError("super() can only be called within a method")
        
        self_obj = env.lookup('self')
        if not isinstance(self_obj, dict) or '__class__' not in self_obj:
            raise HSharpError("super() can only be called within a class method")
        
        class_obj = self_obj['__class__']
        base_name = class_obj.get('base')
        if not base_name:
            raise HSharpError(f"Class '{class_obj.get('name', 'Unknown')}' has no parent class")
        
        # Get base class
        try:
            base = self.functions.get(base_name)
            if not base:
                base = self.global_env.lookup(base_name)
        except HSharpError:
            raise HSharpError(f"Base class '{base_name}' not found")
        
        if not isinstance(base, dict) or 'methods' not in base:
            raise HSharpError(f"'{base_name}' is not a valid class")
        
        # Get method from base class
        methods = base.get('methods', {})
        method_name = expr.method_name
        if method_name not in methods:
            raise HSharpError(f"Method '{method_name}' not found in base class '{base_name}'")
        
        method = methods[method_name]
        args = [self.eval_expr(arg, env) for arg in expr.args]
        
        # Create new environment for method call
        call_env = Environment(parent=self.global_env)
        call_env.define('self', self_obj)
        if len(args) != len(method.params):
            raise HSharpError(f"Method '{method_name}' expects {len(method.params)} arguments, got {len(args)}")
        
        for param, arg in zip(method.params, args):
            call_env.define(param, arg)
        
        try:
            self.visit_BlockStatement(method.body, call_env)
        except ReturnException as e:
            return e.value
        return None

    def visit_InstanceOfExpression(self, expr, env):
        obj = self.eval_expr(expr.expr, env)
        if not isinstance(obj, dict) or '__class__' not in obj:
            return False
        
        class_obj = obj['__class__']
        type_name = expr.type_name
        
        # Check if object is instance of type_name or its subclass
        def is_instance(class_obj, type_name):
            if class_obj.get('name') == type_name:
                return True
            # Check base class
            base_name = class_obj.get('base')
            if base_name:
                try:
                    base = self.functions.get(base_name)
                    if not base:
                        base = self.global_env.lookup(base_name)
                    if is_instance(base, type_name):
                        return True
                except HSharpError:
                    pass
            # Check interfaces
            interfaces = class_obj.get('implements', [])
            if type_name in interfaces:
                return True
            return False
        
        return is_instance(class_obj, type_name)

    def visit_SuperExpression(self, expr, env):
        # Get self from current environment
        if 'self' not in env.vars:
            raise HSharpError("super() can only be called within a method")
        
        self_obj = env.lookup('self')
        if not isinstance(self_obj, dict) or '__class__' not in self_obj:
            raise HSharpError("super() can only be called within a class method")
        
        class_obj = self_obj['__class__']
        base_name = class_obj.get('base')
        if not base_name:
            raise HSharpError(f"Class '{class_obj.get('name', 'Unknown')}' has no parent class")
        
        # Get base class
        try:
            base = self.functions.get(base_name)
            if not base:
                base = self.global_env.lookup(base_name)
        except HSharpError:
            raise HSharpError(f"Base class '{base_name}' not found")
        
        if not isinstance(base, dict) or 'methods' not in base:
            raise HSharpError(f"'{base_name}' is not a valid class")
        
        # Get method from base class
        methods = base.get('methods', {})
        method_name = expr.method_name
        if method_name not in methods:
            raise HSharpError(f"Method '{method_name}' not found in base class '{base_name}'")
        
        method = methods[method_name]
        args = [self.eval_expr(arg, env) for arg in expr.args]
        
        # Create new environment for method call
        call_env = Environment(parent=self.global_env)
        call_env.define('self', self_obj)
        if len(args) != len(method.params):
            raise HSharpError(f"Method '{method_name}' expects {len(method.params)} arguments, got {len(args)}")
        
        for param, arg in zip(method.params, args):
            call_env.define(param, arg)
        
        try:
            self.visit_BlockStatement(method.body, call_env)
        except ReturnException as e:
            return e.value
        return None

    def visit_InstanceOfExpression(self, expr, env):
        obj = self.eval_expr(expr.expr, env)
        if not isinstance(obj, dict) or '__class__' not in obj:
            return False
        
        class_obj = obj['__class__']
        type_name = expr.type_name
        
        # Check if object is instance of type_name or its subclass
        def is_instance(class_obj, type_name):
            if class_obj.get('name') == type_name:
                return True
            # Check base class
            base_name = class_obj.get('base')
            if base_name:
                try:
                    base = self.functions.get(base_name)
                    if not base:
                        base = self.global_env.lookup(base_name)
                    if is_instance(base, type_name):
                        return True
                except HSharpError:
                    pass
            # Check interfaces
            interfaces = class_obj.get('implements', [])
            if type_name in interfaces:
                return True
            return False
        
        return is_instance(class_obj, type_name)

    def visit_ArrayLiteral(self, expr, env):
        return [self.eval_expr(e, env) for e in expr.elements]

    def visit_DictLiteral(self, expr, env):
        d = {}
        for key_expr, val_expr in expr.pairs:
            key = self.eval_expr(key_expr, env)
            if not isinstance(key, (str, int)):
                raise HSharpError("Dictionary keys must be strings or integers")
            val = self.eval_expr(val_expr, env)
            d[key] = val
        return d

    def visit_IndexExpression(self, expr, env):
        left = self.eval_expr(expr.left, env)
        index = self.eval_expr(expr.index, env)
        if isinstance(left, list):
            if not isinstance(index, int):
                raise HSharpError("Array index must be integer")
            if index < 0 or index >= len(left):
                raise HSharpError("Array index out of bounds")
            return left[index]
        elif isinstance(left, str):
            if not isinstance(index, int):
                raise HSharpError("String index must be integer")
            if index < 0 or index >= len(left):
                raise HSharpError("String index out of bounds")
            return left[index]
        elif isinstance(left, dict):
            if index not in left:
                raise HSharpError(f"Key '{index}' not found in dictionary")
            return left[index]
        else:
            raise HSharpError("Can only index arrays, strings, or dictionaries")

    def visit_AssignmentIndex(self, stmt, env):
        arr = self.eval_expr(stmt.array, env)
        index = self.eval_expr(stmt.index, env)
        value = self.eval_expr(stmt.value, env)
        if isinstance(arr, list):
            if not isinstance(index, int):
                raise HSharpError("Array index must be integer")
            if index < 0 or index >= len(arr):
                raise HSharpError("Array index out of bounds")
            arr[index] = value
        elif isinstance(arr, dict):
            arr[index] = value
        else:
            raise HSharpError("Can only assign to array or dictionary elements")
        return value

    def visit_AssignmentMember(self, stmt, env):
        obj = self.eval_expr(stmt.left, env)
        if not isinstance(obj, dict) or '__class__' not in obj:
            raise HSharpError('Left side of member assignment is not an object')
        value = self.eval_expr(stmt.value, env)
        obj[stmt.name] = value
        return value

    def visit_InterfaceDeclaration(self, stmt, env):
        # store interface signatures and default implementations; support interface inheritance
        methods = {}
        for s in stmt.body.statements:
            if isinstance(s, Function):
                methods[s.name] = s
            else:
                raise HSharpError('Invalid member in interface')

        # merge bases
        merged_methods = {}
        for base_name in getattr(stmt, 'bases', []) or []:
            base_iface = self.interfaces.get(base_name)
            if base_iface is None:
                raise HSharpError(f"Interface base '{base_name}' not found for interface '{stmt.name}'")
            merged_methods.update(base_iface.get('methods', {}))
        # then overlay this interface's methods
        merged_methods.update(methods)

        iface = {'name': stmt.name, 'methods': merged_methods, 'body': stmt.body, 'bases': getattr(stmt, 'bases', []) or []}
        self.interfaces[stmt.name] = iface

    def eval_expr(self, expr, env):
        if isinstance(expr, Identifier):
            return env.lookup(expr.name)
        elif isinstance(expr, NumberLiteral):
            return expr.value
        elif isinstance(expr, StringLiteral):
            return expr.value
        elif isinstance(expr, NullLiteral):
            return None
        elif isinstance(expr, BooleanLiteral):
            return expr.value
        elif isinstance(expr, ArrayLiteral):
            return self.visit_ArrayLiteral(expr, env)
        elif isinstance(expr, DictLiteral):
            return self.visit_DictLiteral(expr, env)
        elif isinstance(expr, IndexExpression):
            return self.visit_IndexExpression(expr, env)
        elif isinstance(expr, BinaryOp):
            left = self.eval_expr(expr.left, env)
            right = self.eval_expr(expr.right, env)
            op = expr.op
            if op == TokenType.PLUS:
                if isinstance(left, str) or isinstance(right, str):
                    return str(left) + str(right)
                if isinstance(left, list) and isinstance(right, list):
                    return left + right
                self._ensure_number(left, right)
                return left + right
            elif op == TokenType.MINUS:
                self._ensure_number(left, right)
                return left - right
            elif op == TokenType.STAR:
                self._ensure_number(left, right)
                return left * right
            elif op == TokenType.SLASH:
                self._ensure_number(left, right)
                if right == 0:
                    raise HSharpError("Division by zero")
                return left // right
            elif op == TokenType.EQEQ:
                return left == right
            elif op == TokenType.BANGEQ:
                return left != right
            elif op == TokenType.GT:
                self._ensure_comparable(left, right)
                return left > right
            elif op == TokenType.LT:
                self._ensure_comparable(left, right)
                return left < right
            elif op == TokenType.GTE:
                self._ensure_comparable(left, right)
                return left >= right
            elif op == TokenType.LTE:
                self._ensure_comparable(left, right)
                return left <= right
            elif op == TokenType.AND:
                if not isinstance(left, bool):
                    raise HSharpError("Operands of 'and' must be boolean")
                if not left:
                    return False
                if not isinstance(right, bool):
                    raise HSharpError("Operands of 'and' must be boolean")
                return right
            elif op == TokenType.OR:
                if not isinstance(left, bool):
                    raise HSharpError("Operands of 'or' must be boolean")
                if left:
                    return True
                if not isinstance(right, bool):
                    raise HSharpError("Operands of 'or' must be boolean")
                return right
            elif op == TokenType.BITAND:
                if not isinstance(left, int) or not isinstance(right, int):
                    raise HSharpError('Bitwise operations require integer operands')
                return left & right
            elif op == TokenType.BITOR:
                if not isinstance(left, int) or not isinstance(right, int):
                    raise HSharpError('Bitwise operations require integer operands')
                return left | right
            elif op == TokenType.BITXOR:
                if not isinstance(left, int) or not isinstance(right, int):
                    raise HSharpError('Bitwise operations require integer operands')
                return left ^ right
            elif op == TokenType.LSHIFT:
                if not isinstance(left, int) or not isinstance(right, int):
                    raise HSharpError('Shift operations require integer operands')
                return left << right
            elif op == TokenType.RSHIFT:
                if not isinstance(left, int) or not isinstance(right, int):
                    raise HSharpError('Shift operations require integer operands')
                return left >> right
            else:
                raise HSharpError(f"Unknown operator: {op}")
        elif isinstance(expr, UnaryOp):
            if expr.op == TokenType.NOT:
                val = self.eval_expr(expr.operand, env)
                if not isinstance(val, bool):
                    raise HSharpError("'not' operand must be boolean")
                return not val
            elif expr.op == TokenType.TILDE:
                val = self.eval_expr(expr.operand, env)
                if not isinstance(val, int):
                    raise HSharpError("'~' operand must be integer")
                return ~val
            else:
                raise HSharpError(f"Unknown unary operator: {expr.op}")
        elif isinstance(expr, PointerDereference):
            # pseudo-pointer: evaluate target and return value (no real pointer semantics)
            return self.eval_expr(expr.target, env)
        elif isinstance(expr, CallExpression):
            return self.visit_CallExpression(expr, env)
        elif isinstance(expr, Lambda):
            # return a callable representation capturing the current environment
            return {'params': expr.params, 'body': expr.body, 'closure_env': env}
        elif isinstance(expr, MemberExpression):
            left = self.eval_expr(expr.left, env)
            if isinstance(left, dict) and '__class__' in left:
                # return field value if exists
                if expr.name in left:
                    return left[expr.name]
                # fallback to class default field
                class_obj = left['__class__']
                fields = class_obj.get('fields', {})
                if expr.name in fields:
                    return fields[expr.name]
                # methods are not returned directly here
                raise HSharpError(f"Attribute '{expr.name}' not found on instance")
            # property access on dict-like
            if isinstance(left, dict):
                if expr.name in left:
                    return left[expr.name]
            raise HSharpError(f"Cannot access attribute '{expr.name}' on non-object")
        else:
            raise HSharpError(f"Unknown expression: {expr}")

    def _ensure_number(self, a, b):
        if not isinstance(a, int) or not isinstance(b, int):
            raise HSharpError("Operands must be numbers")

    def _ensure_comparable(self, a, b):
        if type(a) != type(b):
            raise HSharpError("Cannot compare different types")
        if not isinstance(a, (int, str)):
            raise HSharpError("Can only compare numbers or strings")