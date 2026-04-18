from lexer import Lexer
from parser import Parser
from interpreter import Interpreter

code = '''
fn f(a,b) {
    print(a);
    print(b);
    return 99;
}

coro fn c() {
    let x = f(coro_yield(), 2);
    print(x);
}

let C = c();
print(C);
scheduler_run([C]);
'''

lexer = Lexer(code)
parser = Parser(lexer)
program = parser.parse()
interp = Interpreter()
interp.interpret(program)
print('expr-yield done')
