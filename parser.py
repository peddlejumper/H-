from tokens import TokenType
from h_ast import *

class Parser:
    def __init__(self, lexer):
        self.lexer = lexer
        self.current_token = self.lexer.get_next_token()

    def eat(self, token_type):
        if self.current_token[0] == token_type:
            self.current_token = self.lexer.get_next_token()
        else:
            raise SyntaxError(f"Expected {token_type}, got {self.current_token}")

    def parse(self):
        statements = []
        while self.current_token[0] != TokenType.EOF:
            stmt = self.statement()
            statements.append(stmt)
        return Program(statements)

    def statement(self):
        # module / concept / asm / coro support
        if self.current_token[0] == TokenType.MODULE:
            return self.module_declaration()
        if self.current_token[0] == TokenType.CONCEPT:
            return self.concept_declaration()
        if self.current_token[0] == TokenType.ASM:
            return self.asm_statement()
        if self.current_token[0] == TokenType.CORO:
            # coro fn ...
            self.eat(TokenType.CORO)
            fn = self.function_declaration(is_coro=True)
            return fn
        if self.current_token[0] == TokenType.LET:
            return self.let_statement()
        elif self.current_token[0] == TokenType.PRINT:
            return self.print_statement()
        elif self.current_token[0] == TokenType.FN:
            return self.function_declaration()
        elif self.current_token[0] == TokenType.CLASS:
            return self.class_declaration()
        elif self.current_token[0] == TokenType.INTERFACE:
            return self.interface_declaration()
        elif self.current_token[0] == TokenType.WHILE:
            return self.while_statement()
        elif self.current_token[0] == TokenType.IF:
            return self.if_statement()
        elif self.current_token[0] == TokenType.CONTINUE:
            self.eat(TokenType.CONTINUE)
            self.eat(TokenType.SEMI)
            return ContinueStatement()
        elif self.current_token[0] == TokenType.BREAK:
            self.eat(TokenType.BREAK)
            self.eat(TokenType.SEMI)
            return BreakStatement()
        elif self.current_token[0] == TokenType.FOR:
            return self.for_statement()
        elif self.current_token[0] == TokenType.IMPORT:
            return self.import_statement()
        elif self.current_token[0] == TokenType.RETURN:
            return self.return_statement()
        else:
            expr = self.expression()
            if isinstance(expr, IndexExpression) and self.current_token[0] == TokenType.EQ:
                self.eat(TokenType.EQ)
                value = self.expression()
                self.eat(TokenType.SEMI)
                return AssignmentIndex(expr.left, expr.index, value)
            if isinstance(expr, Identifier) and self.current_token[0] == TokenType.EQ:
                self.eat(TokenType.EQ)
                value = self.expression()
                self.eat(TokenType.SEMI)
                return AssignmentIdentifier(expr.name, value)
            if isinstance(expr, MemberExpression) and self.current_token[0] == TokenType.EQ:
                self.eat(TokenType.EQ)
                value = self.expression()
                self.eat(TokenType.SEMI)
                return AssignmentMember(expr.left, expr.name, value)
            else:
                self.eat(TokenType.SEMI)
                return expr

    def let_statement(self):
        # allow 'let' or 'auto' as variable declaration
        if self.current_token[0] == TokenType.LET:
            self.eat(TokenType.LET)
        else:
            self.eat(TokenType.AUTO)
        var_name = self.current_token[1]
        self.eat(TokenType.IDENTIFIER)
        self.eat(TokenType.EQ)
        value = self.expression()
        self.eat(TokenType.SEMI)
        return LetStatement(var_name, value)

    def print_statement(self):
        self.eat(TokenType.PRINT)
        expr = self.expression()
        self.eat(TokenType.SEMI)
        return PrintStatement(expr)

    def import_statement(self):
        self.eat(TokenType.IMPORT)
        if self.current_token[0] == TokenType.STRING:
            path = self.current_token[1]
            self.eat(TokenType.STRING)
        elif self.current_token[0] == TokenType.IDENTIFIER:
            name = self.current_token[1]
            self.eat(TokenType.IDENTIFIER)
            path = Identifier(name)
        else:
            raise SyntaxError('import requires a string path or identifier')
        self.eat(TokenType.SEMI)
        return ImportStatement(path)

    def function_declaration(self, is_coro=False):
        self.eat(TokenType.FN)
        func_name = self.current_token[1]
        self.eat(TokenType.IDENTIFIER)
        self.eat(TokenType.LPAREN)
        params = []
        if self.current_token[0] != TokenType.RPAREN:
            params.append(self.current_token[1])
            self.eat(TokenType.IDENTIFIER)
            while self.current_token[0] == TokenType.COMMA:
                self.eat(TokenType.COMMA)
                params.append(self.current_token[1])
                self.eat(TokenType.IDENTIFIER)
        self.eat(TokenType.RPAREN)
        body = self.block()
        fn = Function(func_name, params, body)
        if is_coro:
            fn.is_coro = True
        return fn

    def module_declaration(self):
        self.eat(TokenType.MODULE)
        name = self.current_token[1]
        self.eat(TokenType.IDENTIFIER)
        body = self.block()
        return ModuleDeclaration(name, body)

    def concept_declaration(self):
        self.eat(TokenType.CONCEPT)
        name = self.current_token[1]
        self.eat(TokenType.IDENTIFIER)
        body = None
        if self.current_token[0] == TokenType.LBRACE:
            body = self.block()
        return ConceptDeclaration(name, body)

    def asm_statement(self):
        self.eat(TokenType.ASM)
        if self.current_token[0] == TokenType.STRING:
            code = self.current_token[1]
            self.eat(TokenType.STRING)
        else:
            # allow block for inline asm
            body = self.block()
            code = body
        self.eat(TokenType.SEMI)
        return AsmBlock(code)

    def class_declaration(self):
        self.eat(TokenType.CLASS)
        class_name = self.current_token[1]
        self.eat(TokenType.IDENTIFIER)
        base = None
        implements = []
        if self.current_token[0] == TokenType.EXTENDS:
            self.eat(TokenType.EXTENDS)
            base = self.current_token[1]
            self.eat(TokenType.IDENTIFIER)
        if self.current_token[0] == TokenType.IMPLEMENTS:
            self.eat(TokenType.IMPLEMENTS)
            implements.append(self.current_token[1])
            self.eat(TokenType.IDENTIFIER)
            while self.current_token[0] == TokenType.COMMA:
                self.eat(TokenType.COMMA)
                implements.append(self.current_token[1])
                self.eat(TokenType.IDENTIFIER)
        self.eat(TokenType.LBRACE)
        members = []
        while self.current_token[0] != TokenType.RBRACE:
            if self.current_token[0] == TokenType.PRIVATE:
                self.eat(TokenType.PRIVATE)
                self.eat(TokenType.LET)
                var_name = self.current_token[1]
                self.eat(TokenType.IDENTIFIER)
                self.eat(TokenType.EQ)
                value = self.expression()
                self.eat(TokenType.SEMI)
                members.append(FieldDeclaration(var_name, value, is_private=True))
            elif self.current_token[0] == TokenType.LET:
                self.eat(TokenType.LET)
                var_name = self.current_token[1]
                self.eat(TokenType.IDENTIFIER)
                self.eat(TokenType.EQ)
                value = self.expression()
                self.eat(TokenType.SEMI)
                members.append(FieldDeclaration(var_name, value, is_private=False))
            elif self.current_token[0] == TokenType.FN:
                members.append(self.function_declaration())
            elif self.current_token[0] == TokenType.STATIC:
                # static method
                self.eat(TokenType.STATIC)
                if self.current_token[0] != TokenType.FN:
                    raise SyntaxError('static must be followed by fn')
                fn = self.function_declaration()
                # mark function as static
                fn.is_static = True
                members.append(fn)
            else:
                members.append(self.statement())
        self.eat(TokenType.RBRACE)
        return ClassDeclaration(class_name, BlockStatement(members), base, implements)

    def interface_declaration(self):
        self.eat(TokenType.INTERFACE)
        name = self.current_token[1]
        self.eat(TokenType.IDENTIFIER)
        bases = []
        if self.current_token[0] == TokenType.EXTENDS:
            self.eat(TokenType.EXTENDS)
            bases.append(self.current_token[1])
            self.eat(TokenType.IDENTIFIER)
            while self.current_token[0] == TokenType.COMMA:
                self.eat(TokenType.COMMA)
                bases.append(self.current_token[1])
                self.eat(TokenType.IDENTIFIER)
        self.eat(TokenType.LBRACE)
        methods = []
        while self.current_token[0] != TokenType.RBRACE:
            if self.current_token[0] == TokenType.FN:
                self.eat(TokenType.FN)
                mname = self.current_token[1]
                self.eat(TokenType.IDENTIFIER)
                self.eat(TokenType.LPAREN)
                params = []
                if self.current_token[0] != TokenType.RPAREN:
                    params.append(self.current_token[1])
                    self.eat(TokenType.IDENTIFIER)
                    while self.current_token[0] == TokenType.COMMA:
                        self.eat(TokenType.COMMA)
                        params.append(self.current_token[1])
                        self.eat(TokenType.IDENTIFIER)
                self.eat(TokenType.RPAREN)
                if self.current_token[0] == TokenType.SEMI:
                    self.eat(TokenType.SEMI)
                    methods.append(Function(mname, params, None))
                else:
                    body = self.block()
                    methods.append(Function(mname, params, body))
            else:
                raise SyntaxError('Only method declarations allowed in interface')
        self.eat(TokenType.RBRACE)
        return InterfaceDeclaration(name, BlockStatement(methods), bases)

    def block(self):
        self.eat(TokenType.LBRACE)
        statements = []
        while self.current_token[0] != TokenType.RBRACE:
            statements.append(self.statement())
        self.eat(TokenType.RBRACE)
        return BlockStatement(statements)

    def while_statement(self):
        self.eat(TokenType.WHILE)
        self.eat(TokenType.LPAREN)
        condition = self.expression()
        self.eat(TokenType.RPAREN)
        body = self.block()
        return WhileStatement(condition, body)

    def if_statement(self):
        self.eat(TokenType.IF)
        self.eat(TokenType.LPAREN)
        condition = self.expression()
        self.eat(TokenType.RPAREN)
        consequence = self.block()
        alternative = None
        if self.current_token[0] == TokenType.ELSE:
            self.eat(TokenType.ELSE)
            if self.current_token[0] == TokenType.IF:
                alternative = self.if_statement()
            else:
                alternative = self.block()
        return IfStatement(condition, consequence, alternative)

    def for_statement(self):
        self.eat(TokenType.FOR)
        var1 = self.current_token[1]
        self.eat(TokenType.IDENTIFIER)
        var2 = None
        if self.current_token[0] == TokenType.COMMA:
            self.eat(TokenType.COMMA)
            var2 = self.current_token[1]
            self.eat(TokenType.IDENTIFIER)
        self.eat(TokenType.IN)
        iterable = self.expression()
        body = self.block()
        return ForStatement(var1, var2, iterable, body)

    def return_statement(self):
        self.eat(TokenType.RETURN)
        expr = self.expression()
        self.eat(TokenType.SEMI)
        return ReturnStatement(expr)

    def expression(self):
        return self.logical_or()

    def logical_or(self):
        node = self.logical_and()
        while self.current_token[0] == TokenType.OR:
            token = self.current_token
            self.eat(TokenType.OR)
            node = BinaryOp(left=node, op=token[0], right=self.logical_and())
        return node

    def logical_and(self):
        node = self.equality()
        while self.current_token[0] == TokenType.AND:
            token = self.current_token
            self.eat(TokenType.AND)
            node = BinaryOp(left=node, op=token[0], right=self.equality())
        return node

    def equality(self):
        node = self.bitwise_or()
        while self.current_token[0] in (TokenType.EQEQ, TokenType.BANGEQ):
            token = self.current_token
            self.eat(token[0])
            node = BinaryOp(left=node, op=token[0], right=self.comparison())
        return node

    def bitwise_or(self):
        node = self.comparison()
        while self.current_token[0] in (TokenType.BITOR, TokenType.BITXOR, TokenType.BITAND, TokenType.LSHIFT, TokenType.RSHIFT):
            token = self.current_token
            self.eat(token[0])
            node = BinaryOp(left=node, op=token[0], right=self.comparison())
        return node

    def comparison(self):
        node = self.term()
        while self.current_token[0] in (TokenType.GT, TokenType.LT, TokenType.GTE, TokenType.LTE):
            token = self.current_token
            self.eat(token[0])
            node = BinaryOp(left=node, op=token[0], right=self.term())
        return node

    def term(self):
        node = self.factor()
        while self.current_token[0] in (TokenType.PLUS, TokenType.MINUS):
            token = self.current_token
            self.eat(token[0])
            node = BinaryOp(left=node, op=token[0], right=self.factor())
        return node

    def factor(self):
        node = self.unary()
        while self.current_token[0] in (TokenType.STAR, TokenType.SLASH):
            token = self.current_token
            self.eat(token[0])
            node = BinaryOp(left=node, op=token[0], right=self.unary())
        return node

    def unary(self):
        if self.current_token[0] == TokenType.MINUS:
            token = self.current_token
            self.eat(TokenType.MINUS)
            return BinaryOp(NumberLiteral(0), TokenType.MINUS, self.unary())
        if self.current_token[0] == TokenType.NOT:
            self.eat(TokenType.NOT)
            return UnaryOp(TokenType.NOT, self.unary())
        if self.current_token[0] == TokenType.STAR:
            # pointer dereference (syntactic support)
            self.eat(TokenType.STAR)
            return PointerDereference(self.unary())
        if self.current_token[0] == TokenType.TILDE:
            self.eat(TokenType.TILDE)
            return UnaryOp(TokenType.TILDE, self.unary())
        return self.primary()

    def primary(self):
        token = self.current_token
        if token[0] == TokenType.FN:
            # lambda expression: fn(params) { body }
            self.eat(TokenType.FN)
            self.eat(TokenType.LPAREN)
            params = []
            if self.current_token[0] != TokenType.RPAREN:
                params.append(self.current_token[1])
                self.eat(TokenType.IDENTIFIER)
                while self.current_token[0] == TokenType.COMMA:
                    self.eat(TokenType.COMMA)
                    params.append(self.current_token[1])
                    self.eat(TokenType.IDENTIFIER)
            self.eat(TokenType.RPAREN)
            body = self.block()
            return Lambda(params, body)
        if token[0] == TokenType.NULL:
            self.eat(TokenType.NULL)
            return NullLiteral()
        if token[0] == TokenType.NEW:
            self.eat(TokenType.NEW)
            cls_name = self.current_token[1]
            self.eat(TokenType.IDENTIFIER)
            self.eat(TokenType.LPAREN)
            args = []
            if self.current_token[0] != TokenType.RPAREN:
                args.append(self.expression())
                while self.current_token[0] == TokenType.COMMA:
                    self.eat(TokenType.COMMA)
                    args.append(self.expression())
            self.eat(TokenType.RPAREN)
            return NewExpression(Identifier(cls_name), args)
        if token[0] == TokenType.SUPER:
            self.eat(TokenType.SUPER)
            self.eat(TokenType.DOT)
            method_name = self.current_token[1]
            self.eat(TokenType.IDENTIFIER)
            self.eat(TokenType.LPAREN)
            args = []
            if self.current_token[0] != TokenType.RPAREN:
                args.append(self.expression())
                while self.current_token[0] == TokenType.COMMA:
                    self.eat(TokenType.COMMA)
                    args.append(self.expression())
            self.eat(TokenType.RPAREN)
            return SuperExpression(method_name, args)
        if token[0] == TokenType.NUMBER:
            self.eat(TokenType.NUMBER)
            return NumberLiteral(token[1])
        elif token[0] == TokenType.STRING:
            self.eat(TokenType.STRING)
            return StringLiteral(token[1])
        elif token[0] == TokenType.BOOL:
            self.eat(TokenType.BOOL)
            return BooleanLiteral(token[1])
        elif token[0] == TokenType.LBRACKET:
            return self.array_literal()
        elif token[0] == TokenType.LBRACE:
            return self.dict_literal()
        elif token[0] == TokenType.IDENTIFIER:
            name = token[1]
            self.eat(TokenType.IDENTIFIER)
            node = Identifier(name)
            while True:
                if self.current_token[0] == TokenType.LPAREN:
                    self.eat(TokenType.LPAREN)
                    args = []
                    if self.current_token[0] != TokenType.RPAREN:
                        args.append(self.expression())
                        while self.current_token[0] == TokenType.COMMA:
                            self.eat(TokenType.COMMA)
                            args.append(self.expression())
                    self.eat(TokenType.RPAREN)
                    node = CallExpression(node, args)
                    continue
                if self.current_token[0] == TokenType.LBRACKET:
                    self.eat(TokenType.LBRACKET)
                    index = self.expression()
                    self.eat(TokenType.RBRACKET)
                    node = IndexExpression(node, index)
                    continue
                if self.current_token[0] == TokenType.DOT:
                    self.eat(TokenType.DOT)
                    attr = self.current_token[1]
                    self.eat(TokenType.IDENTIFIER)
                    node = MemberExpression(node, attr)
                    continue
                break
            return node
        elif token[0] == TokenType.LPAREN:
            self.eat(TokenType.LPAREN)
            node = self.expression()
            self.eat(TokenType.RPAREN)
            # allow call chaining on parenthesized expressions: (fn(...))(args)
            while self.current_token[0] == TokenType.LPAREN:
                self.eat(TokenType.LPAREN)
                args = []
                if self.current_token[0] != TokenType.RPAREN:
                    args.append(self.expression())
                    while self.current_token[0] == TokenType.COMMA:
                        self.eat(TokenType.COMMA)
                        args.append(self.expression())
                self.eat(TokenType.RPAREN)
                node = CallExpression(node, args)
            return node
        else:
            raise SyntaxError(f"Unexpected token: {token}")

    def array_literal(self):
        self.eat(TokenType.LBRACKET)
        elements = []
        if self.current_token[0] != TokenType.RBRACKET:
            elements.append(self.expression())
            while self.current_token[0] == TokenType.COMMA:
                self.eat(TokenType.COMMA)
                elements.append(self.expression())
        self.eat(TokenType.RBRACKET)
        return ArrayLiteral(elements)

    def dict_literal(self):
        self.eat(TokenType.LBRACE)
        pairs = []
        if self.current_token[0] != TokenType.RBRACE:
            key = self.expression()
            self.eat(TokenType.COLON)
            value = self.expression()
            pairs.append((key, value))
            while self.current_token[0] == TokenType.COMMA:
                self.eat(TokenType.COMMA)
                key = self.expression()
                self.eat(TokenType.COLON)
                value = self.expression()
                pairs.append((key, value))
        self.eat(TokenType.RBRACE)
        return DictLiteral(pairs)