from lexer import Lexer
from tokens import TokenType

code = '''
# two coroutines, one waits for event 'go', the other signals it later
coro fn waiter() {
    print(1);
    coro_wait("go");
    print(3);
}

coro fn signaller() {
    print(2);
    coro_sleep(0.01);
    coro_signal("go");
    print(4);
}

let W = waiter();
let S = signaller();

scheduler_run([W, S]);
'''

l = Lexer(code)
count=0
while True:
    print('DEBUG POS', l.pos, repr(l.current_char))
    tok = l.get_next_token()
    print('DEBUG TOK', tok)
    count+=1
    if tok[0] == TokenType.EOF or count>500:
        break
