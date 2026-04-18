from lexer import Lexer
from parser import Parser
from interpreter import Interpreter

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

lexer = Lexer(code)
parser = Parser(lexer)
program = parser.parse()
interp = Interpreter()
interp.interpret(program)
print('events done')
