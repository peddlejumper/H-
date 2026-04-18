from h_ast import *
from tokens import TokenType

class CompileError(Exception):
    pass

class SuperExpression(AST):
    def __init__(self, method_name, args):
        self.method_name = method_name
        self.args = args

class InstanceOfExpression(AST):
    def __init__(self, expr, type_name):
        self.expr = expr
        self.type_name = type_name

class Compiler:
    def __init__(self):
        self.consts = []
        self.instructions = []
        self._labels = []
        self.interfaces = {}

    def add_const(self, value):
        try:
            idx = self.consts.index(value)
        except ValueError:
            idx = len(self.consts)
            self.consts.append(value)
        return idx

    def emit(self, opname, arg=None):
        self.instructions.append((opname, arg))

    def compile(self, program):
        # program: Program AST
        for stmt in program.statements:
            self.compile_stmt(stmt)
        self.emit('HALT')
        return {'instructions': self.instructions, 'consts': self.consts}

    def _find_free_vars_in_stmt(self, node, bound):
        free = set()
        from h_ast import Identifier, LetStatement, Function, Lambda, BlockStatement, CallExpression, MemberExpression
        def visit(n, local_bound):
            if isinstance(n, Identifier):
                if n.name not in local_bound:
                    free.add(n.name)
            elif isinstance(n, LetStatement):
                visit(n.value, local_bound)
                local_bound = set(local_bound)
                local_bound.add(n.name)
            elif isinstance(n, Function):
                # function declaration introduces its own bound names
                return
            elif isinstance(n, Lambda):
                # scan lambda body with its params bound
                b = set(local_bound)|set(n.params)
                for s in n.body.statements:
                    visit(s, b)
            elif isinstance(n, BlockStatement):
                for s in n.statements:
                    visit(s, local_bound)
            elif isinstance(n, CallExpression):
                visit(n.func, local_bound)
                for a in n.args:
                    visit(a, local_bound)
            elif isinstance(n, MemberExpression):
                visit(n.left, local_bound)
            else:
                # generic traversal for attributes
                for attr in getattr(n, '__dict__', {}):
                    v = getattr(n, attr)
                    if isinstance(v, list):
                        for item in v:
                            if hasattr(item, '__dict__'):
                                visit(item, local_bound)
                    elif hasattr(v, '__dict__'):
                        visit(v, local_bound)
        visit(node, set(bound))
        return list(free)

    def compile_stmt(self, stmt):
        from h_ast import ClassDeclaration, AssignmentMember, MemberExpression, NewExpression
        if isinstance(stmt, LetStatement):
            self.compile_expr(stmt.value)
            self.emit('STORE_NAME', stmt.name)
        elif isinstance(stmt, PrintStatement):
            self.compile_expr(stmt.expr)
            self.emit('PRINT')
        elif isinstance(stmt, Function):
            # compile function body into its own bytecode object
            comp = Compiler()
            for s in stmt.body.statements:
                comp.compile_stmt(s)
            comp.emit('RETURN_VALUE')
            func_obj = {'args': stmt.params, 'bytecode': comp.instructions, 'consts': comp.consts}
            idx = self.add_const(func_obj)
            self.emit('LOAD_CONST', idx)
            self.emit('STORE_NAME', stmt.name)
        elif isinstance(stmt, ReturnStatement):
            self.compile_expr(stmt.expr)
            self.emit('RETURN_VALUE')
        elif isinstance(stmt, WhileStatement):
            start = len(self.instructions)
            self.compile_expr(stmt.condition)
            # placeholder for jump
            self.emit('JUMP_IF_FALSE', None)
            jmp_false_pos = len(self.instructions)-1
            for s in stmt.body.statements:
                self.compile_stmt(s)
            self.emit('JUMP', start)
            end = len(self.instructions)
            # backpatch
            self.instructions[jmp_false_pos] = ('JUMP_IF_FALSE', end)
        elif isinstance(stmt, IfStatement):
            self.compile_expr(stmt.condition)
            self.emit('JUMP_IF_FALSE', None)
            jmp_false_pos = len(self.instructions)-1
            # consequence
            for s in stmt.consequence.statements:
                self.compile_stmt(s)
            if stmt.alternative:
                self.emit('JUMP', None)
                jmp_end_pos = len(self.instructions)-1
                alt_start = len(self.instructions)
                self.instructions[jmp_false_pos] = ('JUMP_IF_FALSE', alt_start)
                for s in stmt.alternative.statements:
                    self.compile_stmt(s)
                end = len(self.instructions)
                self.instructions[jmp_end_pos] = ('JUMP', end)
            else:
                end = len(self.instructions)
                self.instructions[jmp_false_pos] = ('JUMP_IF_FALSE', end)
        elif isinstance(stmt, ImportStatement):
            # Emit import opcodes so the VM can perform imports at runtime.
            # stmt.path may be a string ("file.hto") or an Identifier (module name)
            if isinstance(stmt.path, str):
                self.emit('IMPORT_FILE', stmt.path)
            else:
                # assume Identifier
                self.emit('IMPORT_NAME', stmt.path.name)
            return
        elif isinstance(stmt, ClassDeclaration):
            # compile methods and default fields into a class object constant
            methods = {}
            fields = {}
            private_fields = []
            for s in stmt.body.statements:
                if isinstance(s, Function):
                    comp = Compiler()
                    for sub in s.body.statements:
                        comp.compile_stmt(sub)
                    comp.emit('RETURN_VALUE')
                    func_obj = {'args': s.params, 'bytecode': comp.instructions, 'consts': comp.consts}
                    if getattr(s, 'is_static', False):
                        # store static methods as top-level attributes on the class object
                        # they will be callable via ClassName.method(...)
                        methods.setdefault('__static__', {})[s.name] = func_obj
                    else:
                        methods[s.name] = func_obj
                elif isinstance(s, FieldDeclaration):
                    # only support literal defaults at compile time
                    def eval_literal(node):
                        if isinstance(node, NumberLiteral):
                            return node.value
                        if isinstance(node, StringLiteral):
                            return node.value
                        if isinstance(node, BooleanLiteral):
                            return node.value
                        if isinstance(node, ArrayLiteral):
                            return [eval_literal(e) for e in node.elements]
                        if isinstance(node, DictLiteral):
                            d = {}
                            for k, v in node.pairs:
                                kk = eval_literal(k)
                                vv = eval_literal(v)
                                d[kk] = vv
                            return d
                        return None
                    val = eval_literal(s.value)
                    fields[s.name] = val
                    if s.is_private:
                        private_fields.append(s.name)
            # if class implements interfaces, ensure default methods from interfaces are copied in
            for iface_name in getattr(stmt, 'implements', []) or []:
                iface = self.interfaces.get(iface_name)
                if iface is None:
                    raise CompileError(f"Interface '{iface_name}' not found for class '{stmt.name}'")
                for mname, sig in iface.get('methods', {}).items():
                    if mname not in methods:
                        if sig.get('bytecode') is not None:
                            methods[mname] = sig
                        else:
                            raise CompileError(f"Class '{stmt.name}' does not implement interface method '{mname}' from '{iface_name}'")
                    else:
                        # check arity
                        if len(methods[mname].get('args', [])) != len(sig.get('args', [])):
                            raise CompileError(f"Method '{mname}' in class '{stmt.name}' has wrong arity for interface '{iface_name}'")

            class_obj = {'name': stmt.name, 'methods': methods, 'fields': fields, 'private': private_fields}
            if getattr(stmt, 'base', None):
                class_obj['base'] = stmt.base
            if getattr(stmt, 'implements', None):
                class_obj['implements'] = stmt.implements
            # move any static methods recorded under methods['__static__'] to top-level for runtime
            if '__static__' in class_obj['methods']:
                class_obj['__static__'] = class_obj['methods'].pop('__static__')
            idx = self.add_const(class_obj)
            self.emit('LOAD_CONST', idx)
            self.emit('STORE_NAME', stmt.name)
        elif isinstance(stmt, InterfaceDeclaration):
            # compile interface methods (store defaults) and record in compiler.interfaces
            methods = {}
            for s in stmt.body.statements:
                if isinstance(s, Function):
                    if s.body is None:
                        # signature only
                        methods[s.name] = {'args': s.params, 'bytecode': None, 'consts': []}
                    else:
                        comp = Compiler()
                        for sub in s.body.statements:
                            comp.compile_stmt(sub)
                        comp.emit('RETURN_VALUE')
                        methods[s.name] = {'args': s.params, 'bytecode': comp.instructions, 'consts': comp.consts}
                else:
                    raise CompileError('Invalid member in interface')
            # merge base interfaces
            merged = {}
            for base_name in getattr(stmt, 'bases', []) or []:
                base_iface = self.interfaces.get(base_name)
                if base_iface is None:
                    raise CompileError(f"Interface base '{base_name}' not found for interface '{stmt.name}'")
                merged.update(base_iface.get('methods', {}))
            merged.update(methods)
            iface_obj = {'name': stmt.name, 'methods': merged, 'bases': getattr(stmt, 'bases', []) or []}
            self.interfaces[stmt.name] = iface_obj
        elif isinstance(stmt, InterfaceDeclaration):
            # interfaces are a compile-time construct; ignore at bytecode level
            return
        elif isinstance(stmt, BlockStatement):
            for s in stmt.statements:
                self.compile_stmt(s)
        elif isinstance(stmt, AssignmentIndex):
            # arr[index] = value
            self.compile_expr(stmt.array)
            self.compile_expr(stmt.index)
            self.compile_expr(stmt.value)
            self.emit('SET_ITEM')
        elif isinstance(stmt, AssignmentMember):
            # obj.attr = value
            self.compile_expr(stmt.left)
            self.compile_expr(stmt.value)
            self.emit('STORE_ATTR', stmt.name)
        else:
            # expression statements
            self.compile_expr(stmt)
            self.emit('POP_TOP')

    def compile_expr(self, expr):
        if isinstance(expr, NumberLiteral):
            idx = self.add_const(expr.value)
            self.emit('LOAD_CONST', idx)
        elif isinstance(expr, StringLiteral):
            idx = self.add_const(expr.value)
            self.emit('LOAD_CONST', idx)
        elif isinstance(expr, BooleanLiteral):
            idx = self.add_const(expr.value)
            self.emit('LOAD_CONST', idx)
        elif isinstance(expr, Identifier):
            self.emit('LOAD_NAME', expr.name)
        elif isinstance(expr, NullLiteral):
            idx = self.add_const(None)
            self.emit('LOAD_CONST', idx)
        elif isinstance(expr, Lambda):
            # compile lambda into a function constant (no capture support in this MVP)
            comp = Compiler()
            for s in expr.body.statements:
                comp.compile_stmt(s)
            comp.emit('RETURN_VALUE')
            # capture free vars from current compilation scope
            freevars = self._find_free_vars_in_stmt(expr, expr.params)
            func_obj = {'args': expr.params, 'bytecode': comp.instructions, 'consts': comp.consts, 'freevars': freevars}
            idx = self.add_const(func_obj)
            self.emit('LOAD_CONST', idx)
        elif isinstance(expr, ArrayLiteral):
            for e in expr.elements:
                self.compile_expr(e)
            self.emit('MAKE_LIST', len(expr.elements))
        elif isinstance(expr, DictLiteral):
            for k, v in expr.pairs:
                self.compile_expr(k)
                self.compile_expr(v)
            self.emit('MAKE_DICT', len(expr.pairs))
        elif isinstance(expr, IndexExpression):
            self.compile_expr(expr.left)
            self.compile_expr(expr.index)
            self.emit('GET_ITEM')
        elif isinstance(expr, MemberExpression):
            # push attribute value: compile left (instance) then load attribute
            self.compile_expr(expr.left)
            self.emit('LOAD_ATTR', expr.name)
        elif isinstance(expr, BinaryOp):
            op = expr.op
            if op in (TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.SLASH,
                      TokenType.EQEQ, TokenType.BANGEQ, TokenType.GT, TokenType.LT, TokenType.GTE, TokenType.LTE):
                # simple binary ops: compile left then right
                self.compile_expr(expr.left)
                self.compile_expr(expr.right)
                if op == TokenType.PLUS:
                    self.emit('BINARY_ADD')
                elif op == TokenType.MINUS:
                    self.emit('BINARY_SUB')
                elif op == TokenType.STAR:
                    self.emit('BINARY_MUL')
                elif op == TokenType.SLASH:
                    self.emit('BINARY_DIV')
                else:
                    # comparison
                    self.emit('COMPARE_OP', op.value)
            elif op == TokenType.AND:
                # short-circuit: if left is false -> push False; else evaluate right
                self.compile_expr(expr.left)
                # placeholder
                self.emit('JUMP_IF_FALSE', None)
                jmp_false_pos = len(self.instructions)-1
                # evaluate right (if left true)
                self.compile_expr(expr.right)
                # after right, skip false-constant
                self.emit('JUMP', None)
                jmp_end_pos = len(self.instructions)-1
                false_pos = len(self.instructions)
                idx_false = self.add_const(False)
                self.emit('LOAD_CONST', idx_false)
                end_pos = len(self.instructions)
                self.instructions[jmp_false_pos] = ('JUMP_IF_FALSE', false_pos)
                self.instructions[jmp_end_pos] = ('JUMP', end_pos)
            elif op == TokenType.OR:
                # short-circuit: if left is true -> push True; else evaluate right
                self.compile_expr(expr.left)
                # if left is false, jump to eval right
                self.emit('JUMP_IF_FALSE', None)
                jmp_eval_right = len(self.instructions)-1
                # left was true (did not jump): push True and skip right
                idx_true = self.add_const(True)
                self.emit('LOAD_CONST', idx_true)
                self.emit('JUMP', None)
                jmp_end = len(self.instructions)-1
                eval_right_pos = len(self.instructions)
                self.instructions[jmp_eval_right] = ('JUMP_IF_FALSE', eval_right_pos)
                # evaluate right
                self.compile_expr(expr.right)
                end_pos = len(self.instructions)
                self.instructions[jmp_end] = ('JUMP', end_pos)
            else:
                raise CompileError(f'Unsupported binary op: {op}')
        elif isinstance(expr, UnaryOp):
            if expr.op == TokenType.NOT:
                self.compile_expr(expr.operand)
                self.emit('UNARY_NOT')
            else:
                raise CompileError(f'Unsupported unary op: {expr.op}')
        elif isinstance(expr, CallExpression):
            # support calls like func(...), or obj.method(...)
            # func can be Identifier or MemberExpression
            if isinstance(expr.func, Identifier):
                for arg in expr.args:
                    self.compile_expr(arg)
                self.emit('CALL_FUNCTION', (expr.func.name, len(expr.args)))
            elif isinstance(expr.func, MemberExpression):
                # for method call, compile left (instance), then args, then CALL_METHOD
                self.compile_expr(expr.func.left)
                for arg in expr.args:
                    self.compile_expr(arg)
                self.emit('CALL_METHOD', (expr.func.name, len(expr.args)))
            else:
                # general callable expression: compile the function expression
                self.compile_expr(expr.func)
                for arg in expr.args:
                    self.compile_expr(arg)
                self.emit('CALL_VALUE', len(expr.args))
        elif isinstance(expr, NewExpression):
            # compile class expression (usually Identifier)
            # emit LOAD_NAME for class then args then CALL_NEW
            if isinstance(expr.class_name, Identifier):
                self.emit('LOAD_NAME', expr.class_name.name)
            else:
                self.compile_expr(expr.class_name)
            for arg in expr.args:
                self.compile_expr(arg)
            self.emit('CALL_NEW', len(expr.args))
        elif isinstance(expr, SuperExpression):
            # super.method(args) - compile as special call
            # Need special opcode for super calls
            for arg in expr.args:
                self.compile_expr(arg)
            self.emit('CALL_SUPER', (expr.method_name, len(expr.args)))
        elif isinstance(expr, InstanceOfExpression):
            # expr is TypeName
            self.compile_expr(expr.expr)
            self.emit('INSTANCEOF', expr.type_name)
        else:
            raise CompileError(f'Unsupported expression type: {type(expr)}')