import sys
import copy
from collections import deque

class BytecodeRuntimeError(Exception):
    pass

class VM:
    def __init__(self, bytecode, consts=None):
        self.instructions = bytecode.get('instructions', [])
        self.consts = bytecode.get('consts', []) if consts is None else consts
        self.stack = []
        self.env = {}
        self.functions = {}
        self.pc = 0
        self.parent = None
        self.builtins = {
            'len': lambda args: len(args[0]) if len(args)==1 else (_ for _ in ()).throw(BytecodeRuntimeError('len() takes 1 arg')),
            'push': lambda args: (args[0].append(args[1]) or None),
            'pop': lambda args: args[0].pop(),
            'read_file': lambda args: open(args[0], 'r', encoding='utf-8').read(),
            'write_file': lambda args: (open(args[0], 'w', encoding='utf-8').write(args[1]) or None),
            'thread_spawn': self._builtin_thread_spawn,
            'thread_join': self._builtin_thread_join,
        }

    def run(self):
        instrs = self.instructions
        while self.pc < len(instrs):
            opname, arg = instrs[self.pc]
            self.pc += 1
            if opname == 'LOAD_CONST':
                self.stack.append(self.consts[arg])
            elif opname == 'LOAD_NAME':
                name = arg
                val = self._lookup_name(name)
                self.stack.append(val)
            elif opname == 'STORE_NAME':
                val = self.stack.pop()
                self.env[arg] = val
            elif opname == 'PRINT':
                val = self.stack.pop()
                print(val)
            elif opname == 'POP_TOP':
                self.stack.pop()
            elif opname == 'MAKE_LIST':
                n = arg
                items = [self.stack.pop() for _ in range(n)][::-1]
                self.stack.append(items)
            elif opname == 'MAKE_DICT':
                n = arg
                d = {}
                for _ in range(n):
                    val = self.stack.pop()
                    key = self.stack.pop()
                    d[key] = val
                self.stack.append(d)
            elif opname == 'GET_ITEM':
                idx = self.stack.pop()
                left = self.stack.pop()
                self.stack.append(left[idx])
            elif opname == 'LOAD_ATTR':
                name = arg
                obj = self.stack.pop()
                # object attribute lookup
                if isinstance(obj, dict):
                    if name in obj:
                        self.stack.append(obj[name])
                        continue
                    if '__class__' in obj:
                        class_obj = obj['__class__']
                        # check private access: only allowed when caller self == obj
                        private = class_obj.get('private', [])
                        caller_self = self.env.get('self')
                        if name in private and caller_self is not obj:
                            raise BytecodeRuntimeError(f"Private attribute '{name}' access denied")
                        # instance fields defaults
                        fields = class_obj.get('fields', {})
                        if name in fields:
                            self.stack.append(fields[name])
                            continue
                        # methods: return bound method wrapper
                        methods = class_obj.get('methods', {})
                        if name in methods:
                            self.stack.append({'__method__': methods[name], '__self__': obj})
                            continue
                raise BytecodeRuntimeError(f"Attribute '{name}' not found on object")
            elif opname == 'STORE_ATTR':
                name = arg
                val = self.stack.pop()
                obj = self.stack.pop()
                if not isinstance(obj, dict):
                    raise BytecodeRuntimeError('STORE_ATTR target is not an object')
                # enforce private write
                class_obj = obj.get('__class__')
                if class_obj and name in class_obj.get('private', []) and self.env.get('self') is not obj:
                    raise BytecodeRuntimeError(f"Private attribute '{name}' write denied")
                obj[name] = val
                self.stack.append(val)
            elif opname == 'SET_ITEM':
                val = self.stack.pop()
                idx = self.stack.pop()
                left = self.stack.pop()
                left[idx] = val
                self.stack.append(val)
            elif opname == 'BINARY_ADD':
                b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a + b)
            elif opname == 'BINARY_SUB':
                b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a - b)
            elif opname == 'BINARY_MUL':
                b = self.stack.pop(); a = self.stack.pop(); self.stack.append(a * b)
            elif opname == 'BINARY_DIV':
                b = self.stack.pop(); a = self.stack.pop();
                if b == 0:
                    raise BytecodeRuntimeError('division by zero')
                self.stack.append(a // b)
            elif opname == 'UNARY_NOT':
                a = self.stack.pop()
                if not isinstance(a, bool):
                    raise BytecodeRuntimeError("'not' operand must be boolean")
                self.stack.append(not a)
            elif opname == 'COMPARE_OP':
                op = arg
                b = self.stack.pop(); a = self.stack.pop()
                if op == 'EQEQ':
                    self.stack.append(a == b)
                elif op == 'BANGEQ':
                    self.stack.append(a != b)
                elif op == 'GT':
                    self.stack.append(a > b)
                elif op == 'LT':
                    self.stack.append(a < b)
                elif op == 'GTE':
                    self.stack.append(a >= b)
                elif op == 'LTE':
                    self.stack.append(a <= b)
                else:
                    raise BytecodeRuntimeError(f'Unknown compare op {op}')
            elif opname == 'JUMP_IF_FALSE':
                target = arg
                cond = self.stack.pop()
                if not cond:
                    self.pc = target
            elif opname == 'JUMP':
                self.pc = arg
            elif opname == 'CALL_FUNCTION':
                name, argc = arg
                args = [self.stack.pop() for _ in range(argc)][::-1]
                # builtins
                if name in self.builtins:
                    res = self.builtins[name](args)
                    self.stack.append(res)
                elif name in self.env and isinstance(self.env[name], dict):
                    func = self.env[name]
                    # user function represented as dict with keys 'args', 'bytecode', 'consts'
                    fargs = func.get('args', [])
                    if len(fargs) != len(args):
                        raise BytecodeRuntimeError(f"Function {name} expects {len(fargs)} args")
                    # setup new VM for function
                    bc = {'instructions': func['bytecode'], 'consts': func.get('consts', [])}
                    vm2 = VM(bc)
                    # populate freevars captured by this function
                    for fv in func.get('freevars', []):
                        try:
                            vm2.env[fv] = self._lookup_name(fv)
                        except Exception:
                            vm2.env[fv] = None
                    # set parameters
                    for pname, pval in zip(fargs, args):
                        vm2.env[pname] = pval
                    vm2.functions = self.functions
                    res = vm2.run()
                    self.stack.append(res)
                else:
                    raise BytecodeRuntimeError(f'Unknown function: {name}')
            elif opname == 'RETURN_VALUE':
                if self.stack:
                    return self.stack.pop()
                return None
            elif opname == 'CALL_METHOD':
                name, argc = arg
                args = [self.stack.pop() for _ in range(argc)][::-1]
                inst = self.stack.pop()
                # Special-case: module proxy (dict) attribute call
                if isinstance(inst, dict) and '__class__' not in inst:
                    # module-like dict or class object (for static methods)
                    # direct attribute (python proxy) call
                    if name in inst:
                        val = inst[name]
                        if callable(val):
                            try:
                                res = val(*args)
                                self.stack.append(res)
                                continue
                            except Exception as e:
                                raise BytecodeRuntimeError(f"Error calling external function '{name}': {e}")
                        # user-defined function stored as dict (static method on class)
                        if isinstance(val, dict) and 'bytecode' in val:
                            func = val
                            fargs = func.get('args', [])
                            if len(fargs) != len(args):
                                raise BytecodeRuntimeError(f"Method {name} expects {len(fargs)} args")
                            bc = {'instructions': func['bytecode'], 'consts': func.get('consts', [])}
                            vm2 = VM(bc)
                            for pname, pval in zip(fargs, args):
                                vm2.env[pname] = pval
                            vm2.functions = self.functions
                            res = vm2.run()
                            self.stack.append(res)
                            continue
                        else:
                            raise BytecodeRuntimeError(f"Attribute '{name}' on module is not callable")
                    # support static methods stored under special container
                    static_map = inst.get('__static__') if isinstance(inst, dict) else None
                    if static_map and name in static_map:
                        func = static_map[name]
                        fargs = func.get('args', [])
                        if len(fargs) != len(args):
                            raise BytecodeRuntimeError(f"Method {name} expects {len(fargs)} args")
                        bc = {'instructions': func['bytecode'], 'consts': func.get('consts', [])}
                        vm2 = VM(bc)
                        for pname, pval in zip(fargs, args):
                            vm2.env[pname] = pval
                        vm2.functions = self.functions
                        res = vm2.run()
                        self.stack.append(res)
                        continue
                    raise BytecodeRuntimeError(f"Attribute '{name}' not found on module/class")
                # If inst is a real Python module/object with attribute, try to call it
                if not isinstance(inst, dict) or '__class__' not in inst:
                    if not isinstance(inst, dict) and hasattr(inst, name):
                        val = getattr(inst, name)
                        if callable(val):
                            try:
                                res = val(*args)
                                self.stack.append(res)
                                continue
                            except Exception as e:
                                raise BytecodeRuntimeError(f"Error calling external attribute '{name}': {e}")
                        else:
                            raise BytecodeRuntimeError(f"Attribute '{name}' on object is not callable")
                    raise BytecodeRuntimeError(f"CALL_METHOD on non-instance (inst={type(inst).__name__} {str(inst)[:80]})")
                class_obj = inst['__class__']
                methods = class_obj.get('methods', {})
                if name not in methods:
                    raise BytecodeRuntimeError(f"Method '{name}' not found on class")
                method = methods[name]
                fargs = method.get('args', [])
                if len(fargs) != len(args):
                    raise BytecodeRuntimeError(f"Method {name} expects {len(fargs)} args")
                bc = {'instructions': method['bytecode'], 'consts': method.get('consts', [])}
                vm2 = VM(bc)
                # set parameters and self
                vm2.env['self'] = inst
                vm2.parent = self
                for pname, pval in zip(fargs, args):
                    vm2.env[pname] = pval
                vm2.functions = self.functions
                res = vm2.run()
                self.stack.append(res)
            elif opname == 'CALL_SUPER':
                name, argc = arg
                args = [self.stack.pop() for _ in range(argc)][::-1]
                # Get self from environment
                inst = self.env.get('self')
                if inst is None:
                    raise BytecodeRuntimeError("super() can only be called within a method")
                
                if not isinstance(inst, dict) or '__class__' not in inst:
                    raise BytecodeRuntimeError("super() can only be called within a class method")
                
                class_obj = inst['__class__']
                base_name = class_obj.get('base')
                if not base_name:
                    raise BytecodeRuntimeError(f"Class '{class_obj.get('name', 'Unknown')}' has no parent class")
                
                # Get base class
                base = self.env.get(base_name) or self.functions.get(base_name)
                if not base:
                    raise BytecodeRuntimeError(f"Base class '{base_name}' not found")
                
                if not isinstance(base, dict) or 'methods' not in base:
                    raise BytecodeRuntimeError(f"'{base_name}' is not a valid class")
                
                # Get method from base class
                methods = base.get('methods', {})
                if name not in methods:
                    raise BytecodeRuntimeError(f"Method '{name}' not found in base class '{base_name}'")
                
                method = methods[name]
                fargs = method.get('args', [])
                if len(fargs) != len(args):
                    raise BytecodeRuntimeError(f"Method {name} expects {len(fargs)} args")
                
                bc = {'instructions': method['bytecode'], 'consts': method.get('consts', [])}
                vm2 = VM(bc)
                vm2.env['self'] = inst
                vm2.parent = self
                for pname, pval in zip(fargs, args):
                    vm2.env[pname] = pval
                vm2.functions = self.functions
                res = vm2.run()
                self.stack.append(res)
            elif opname == 'CALL_VALUE':
                argc = arg
                args = [self.stack.pop() for _ in range(argc)][::-1]
                func = self.stack.pop()
                # Python callable
                if callable(func):
                    try:
                        res = func(*args)
                        self.stack.append(res)
                        continue
                    except Exception as e:
                        raise BytecodeRuntimeError(f"Error calling external function: {e}")
                # compiled H# function object
                if isinstance(func, dict) and 'bytecode' in func:
                    fargs = func.get('args', [])
                    if len(fargs) != len(args):
                        raise BytecodeRuntimeError(f"Function expects {len(fargs)} args")
                    bc = {'instructions': func['bytecode'], 'consts': func.get('consts', [])}
                    vm2 = VM(bc)
                    # populate freevars into function env from current VM
                    for fv in func.get('freevars', []):
                        try:
                            vm2.env[fv] = self._lookup_name(fv)
                        except Exception:
                            vm2.env[fv] = None
                    for pname, pval in zip(fargs, args):
                        vm2.env[pname] = pval
                    vm2.functions = self.functions
                    res = vm2.run()
                    self.stack.append(res)
                    continue
                raise BytecodeRuntimeError('CALL_VALUE on non-callable')
            elif opname == 'INSTANCEOF':
                type_name = arg
                obj = self.stack.pop()
                if not isinstance(obj, dict) or '__class__' not in obj:
                    self.stack.append(False)
                    continue
                
                class_obj = obj['__class__']
                
                def is_instance(class_obj, type_name):
                    if class_obj.get('name') == type_name:
                        return True
                    # Check base class
                    base_name = class_obj.get('base')
                    if base_name:
                        base = self.env.get(base_name) or self.functions.get(base_name)
                        if base and is_instance(base, type_name):
                            return True
                    # Check interfaces
                    interfaces = class_obj.get('implements', [])
                    if type_name in interfaces:
                        return True
                    return False
                
                result = is_instance(class_obj, type_name)
                self.stack.append(result)
            elif opname == 'CALL_NEW':
                argc = arg
                args = [self.stack.pop() for _ in range(argc)][::-1]
                class_obj = self.stack.pop()
                if not isinstance(class_obj, dict) or 'methods' not in class_obj:
                    raise BytecodeRuntimeError('CALL_NEW on non-class object')
                # resolve inheritance chain by merging base classes
                def resolve_class(cobj):
                    if not isinstance(cobj, dict):
                        return cobj
                    base_name = cobj.get('base')
                    if not base_name:
                        return cobj
                    base = self.env.get(base_name) or self.functions.get(base_name)
                    if not base:
                        raise BytecodeRuntimeError(f'Base class {base_name} not found')
                    base_resolved = resolve_class(base)
                    merged = {'name': cobj.get('name'), 'methods': {}, 'fields': {}, 'private': []}
                    merged['methods'].update(base_resolved.get('methods', {}))
                    merged['fields'].update(base_resolved.get('fields', {}))
                    merged['private'].extend(base_resolved.get('private', []))
                    # then overlay child
                    merged['methods'].update(cobj.get('methods', {}))
                    merged['fields'].update(cobj.get('fields', {}))
                    merged['private'].extend(cobj.get('private', []))
                    return merged

                resolved = resolve_class(class_obj)
                inst = {}
                inst['__class__'] = resolved
                # copy default fields
                for k, v in resolved.get('fields', {}).items():
                    inst[k] = copy.deepcopy(v)
                # call constructor if present
                if '__init__' in resolved.get('methods', {}):
                    method = resolved['methods']['__init__']
                    fargs = method.get('args', [])
                    if len(fargs) != len(args):
                        raise BytecodeRuntimeError('__init__ args mismatch')
                    bc = {'instructions': method['bytecode'], 'consts': method.get('consts', [])}
                    vm2 = VM(bc)
                    vm2.parent = self
                    vm2.env['self'] = inst
                    for pname, pval in zip(fargs, args):
                        vm2.env[pname] = pval
                    vm2.functions = self.functions
                    vm2.run()
                self.stack.append(inst)
            elif opname == 'HALT':
                return None
            elif opname == 'IMPORT_NAME':
                modname = arg
                try:
                    import importlib
                    mod = importlib.import_module(modname)
                except Exception as e:
                    raise BytecodeRuntimeError(f"Failed to import Python module '{modname}': {e}")
                proxy = {}
                for attr in dir(mod):
                    if attr.startswith('_'):
                        continue
                    try:
                        val = getattr(mod, attr)
                    except Exception:
                        continue
                    proxy[attr] = val
                self.env[modname] = proxy
            elif opname == 'IMPORT_FILE':
                # import a local H# file at runtime: parse and interpret in the current environment
                path = arg
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        code = f.read()
                except Exception as e:
                    raise BytecodeRuntimeError(f"Failed to read import file '{path}': {e}")
                try:
                    from lexer import Lexer
                    from parser import Parser
                    from interpreter import Interpreter
                    lexer = Lexer(code)
                    parser = Parser(lexer)
                    program = parser.parse()
                    interp = Interpreter(global_env=None, functions=self.functions)
                    # interpret into a fresh interpreter but share top-level env with this VM
                    interp.interpret(program, env=None)
                    # merge interfaces if present
                    if hasattr(interp, 'interfaces'):
                        # store into this VM as needed (not used heavily in bytecode VM)
                        pass
                except Exception as e:
                    raise BytecodeRuntimeError(f"Error importing H# file '{path}': {e}")
            else:
                raise BytecodeRuntimeError(f'Unknown opcode: {opname}')

        return None

    def _builtin_thread_spawn(self, args):
        if len(args) != 1:
            raise BytecodeRuntimeError('thread_spawn(func) takes exactly 1 argument')
        fn = args[0]
        import threading

        def target_callable():
            try:
                if isinstance(fn, dict) and 'bytecode' in fn:
                    vm = VM({'instructions': fn['bytecode'], 'consts': fn.get('consts', [])})
                    vm.run()
                elif callable(fn):
                    fn()
                else:
                    raise BytecodeRuntimeError('Unsupported callable passed to thread_spawn')
            except Exception as e:
                sys.__stderr__.write(f"Thread error: {e}\n")

        t = threading.Thread(target=target_callable)
        t.start()
        return t

    def _builtin_thread_join(self, args):
        if len(args) != 1:
            raise BytecodeRuntimeError('thread_join(t) takes exactly 1 argument')
        t = args[0]
        try:
            t.join()
            return None
        except Exception as e:
            raise BytecodeRuntimeError(f'Error joining thread: {e}')

    def _lookup_name(self, name):
        # search local env, then functions, then parent chain, then builtins
        node = self
        while node is not None:
            if name in node.env:
                return node.env[name]
            if name in node.functions:
                return node.functions[name]
            node = node.parent
        if name in self.builtins:
            return self.builtins[name]
        raise BytecodeRuntimeError(f"Undefined name: {name}")