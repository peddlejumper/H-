from tokens import TokenType

class Lexer:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.current_char = self.text[self.pos] if self.text else None

    def advance(self):
        self.pos += 1
        if self.pos >= len(self.text):
            self.current_char = None
        else:
            self.current_char = self.text[self.pos]

    def skip_whitespace(self):
        while self.current_char and (self.current_char.isspace() or self.current_char == '#'):
            if self.current_char == '#':
                # skip comment until end of line
                while self.current_char and self.current_char != '\n':
                    self.advance()
                continue
            self.advance()

    def number(self):
        result = ''
        while self.current_char and self.current_char.isdigit():
            result += self.current_char
            self.advance()
        # handle fractional part
        if self.current_char == '.':
            result += '.'
            self.advance()
            frac = ''
            while self.current_char and self.current_char.isdigit():
                frac += self.current_char
                self.advance()
            if frac == '':
                raise SyntaxError('Invalid number literal')
            return float(result + frac)
        return int(result)

    def identifier(self):
        result = ''
        while self.current_char and (self.current_char.isalnum() or self.current_char == '_'):
            result += self.current_char
            self.advance()
        keywords = {
            'let': TokenType.LET,
            'fn': TokenType.FN,
            'return': TokenType.RETURN,
            'while': TokenType.WHILE,
            'if': TokenType.IF,
            'else': TokenType.ELSE,
            'for': TokenType.FOR,
            'in': TokenType.IN,
            'print': TokenType.PRINT,
            'import': TokenType.IMPORT,
            'class': TokenType.CLASS,
            'new': TokenType.NEW,
            'extends': TokenType.EXTENDS,
            'private': TokenType.PRIVATE,
            'static': TokenType.STATIC,
            'interface': TokenType.INTERFACE,
            'implements': TokenType.IMPLEMENTS,
            'super': TokenType.SUPER,
            'is': TokenType.IS,
            'as': TokenType.AS,
            'module': TokenType.MODULE,
            'concept': TokenType.CONCEPT,
            'coro': TokenType.CORO,
            'asm': TokenType.ASM,
            'ptr': TokenType.PTR,
            'true': ('BOOL', True),
            'false': ('BOOL', False),
            'and': TokenType.AND,
            'or': TokenType.OR,
            'not': TokenType.NOT,
            'continue': TokenType.CONTINUE,
            'break': TokenType.BREAK,
            'nullptr': (TokenType.NULL, None),
            'auto': TokenType.AUTO,
        }
        if result in keywords:
            val = keywords[result]
            if isinstance(val, tuple):
                # e.g. ('BOOL', True)
                if val[0] == 'BOOL':
                    return (TokenType.BOOL, val[1])
                return val
            else:
                return (val, None)
        return (TokenType.IDENTIFIER, result)

    def string(self):
        self.advance()
        result = ''
        while self.current_char is not None and self.current_char != '"':
            if self.current_char is None:
                raise SyntaxError("Unterminated string")
            if self.current_char == '\\':
                self.advance()
                if self.current_char == 'n':
                    result += '\n'
                    self.advance()
                elif self.current_char == '"':
                    result += '"'
                    self.advance()
                else:
                    result += '\\' + (self.current_char or '')
                    self.advance()
            else:
                result += self.current_char
                self.advance()
        self.advance()
        return (TokenType.STRING, result)
    def get_next_token(self):
        while self.current_char is not None:
            if self.current_char.isspace() or self.current_char == '#':
                self.skip_whitespace()
                continue

            if self.current_char.isdigit():
                return (TokenType.NUMBER, self.number())

            if self.current_char.isalpha() or self.current_char == '_':
                return self.identifier()

            if self.current_char == '"':
                return self.string()

            # 多字符 operators
            if self.current_char == '=':
                self.advance()
                if self.current_char == '=':
                    self.advance()
                    return (TokenType.EQEQ, '==')
                return (TokenType.EQ, '=')
            if self.current_char == '!':
                self.advance()
                if self.current_char == '=':
                    self.advance()
                    return (TokenType.BANGEQ, '!=')
                raise SyntaxError("Unexpected '!'")
            if self.current_char == '>':
                self.advance()
                if self.current_char == '=':
                    self.advance()
                    return (TokenType.GTE, '>=')
                if self.current_char == '>':
                    self.advance()
                    return (TokenType.RSHIFT, '>>')
                return (TokenType.GT, '>')
            if self.current_char == '<':
                self.advance()
                if self.current_char == '=':
                    self.advance()
                    return (TokenType.LTE, '<=')
                if self.current_char == '<':
                    self.advance()
                    return (TokenType.LSHIFT, '<<')
                return (TokenType.LT, '<')

            # 单字符
            if self.current_char == '+':
                self.advance()
                return (TokenType.PLUS, '+')
            if self.current_char == '-':
                self.advance()
                return (TokenType.MINUS, '-')
            if self.current_char == '*':
                self.advance()
                return (TokenType.STAR, '*')
            if self.current_char == '/':
                self.advance()
                return (TokenType.SLASH, '/')
            if self.current_char == '&':
                self.advance()
                return (TokenType.BITAND, '&')
            if self.current_char == '|':
                self.advance()
                return (TokenType.BITOR, '|')
            if self.current_char == '^':
                self.advance()
                return (TokenType.BITXOR, '^')
            if self.current_char == '~':
                self.advance()
                return (TokenType.TILDE, '~')
            if self.current_char == ';':
                self.advance()
                return (TokenType.SEMI, ';')
            if self.current_char == '(':
                self.advance()
                return (TokenType.LPAREN, '(')
            if self.current_char == ')':
                self.advance()
                return (TokenType.RPAREN, ')')
            if self.current_char == '{':
                self.advance()
                return (TokenType.LBRACE, '{')
            if self.current_char == '}':
                self.advance()
                return (TokenType.RBRACE, '}')
            if self.current_char == '[':
                self.advance()
                return (TokenType.LBRACKET, '[')
            if self.current_char == ']':
                self.advance()
                return (TokenType.RBRACKET, ']')
            if self.current_char == ':':
                self.advance()
                return (TokenType.COLON, ':')
            if self.current_char == ',':
                self.advance()
                return (TokenType.COMMA, ',')
            if self.current_char == '.':
                self.advance()
                return (TokenType.DOT, '.')

            raise SyntaxError(f"Invalid character: '{self.current_char}'")

        return (TokenType.EOF, None)