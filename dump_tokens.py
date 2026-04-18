from lexer import Lexer
from tokens import TokenType

code = '''
coro fn c() {
    print(1);
    coro_yield();
    print(2);
    return 42;
}

let x = c();
print(x);
coro_resume(x);
coro_resume(x);
'''

l = Lexer(code)
while True:
    tok = l.get_next_token()
    print(tok)
    if tok[0] == TokenType.EOF:
        break
