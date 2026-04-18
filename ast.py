class AST:
    pass

class Program(AST):
    def __init__(self, statements):
        self.statements = statements

class LetStatement(AST):
    def __init__(self, name, value):
        self.name = name
        self.value = value

class PrintStatement(AST):
    def __init__(self, expr):
        self.expr = expr

class ImportStatement(AST):
    def __init__(self, path):
        self.path = path

class Function(AST):
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body

class CallExpression(AST):
    def __init__(self, func, args):
        # func: an expression (Identifier or MemberExpression)
        self.func = func
        self.args = args

class ReturnStatement(AST):
    def __init__(self, expr):
        self.expr = expr

class WhileStatement(AST):
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body

class IfStatement(AST):
    def __init__(self, condition, consequence, alternative=None):
        self.condition = condition
        self.consequence = consequence
        self.alternative = alternative

class ForStatement(AST):
    def __init__(self, var1, var2, iterable, body):
        # var2 可为 None（单变量 for）
        self.var1 = var1
        self.var2 = var2
        self.iterable = iterable
        self.body = body

class BlockStatement(AST):
    def __init__(self, statements):
        self.statements = statements

class Identifier(AST):
    def __init__(self, name):
        self.name = name

class NumberLiteral(AST):
    def __init__(self, value):
        self.value = value

class StringLiteral(AST):
    def __init__(self, value):
        self.value = value

class BooleanLiteral(AST):
    def __init__(self, value):
        self.value = value

class UnaryOp(AST):
    def __init__(self, op, operand):
        self.op = op
        self.operand = operand

class ArrayLiteral(AST):
    def __init__(self, elements):
        self.elements = elements

class DictLiteral(AST):
    def __init__(self, pairs):
        # pairs: list of (key_expr, value_expr)
        self.pairs = pairs

class IndexExpression(AST):
    def __init__(self, left, index):
        self.left = left
        self.index = index

class BinaryOp(AST):
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right

class AssignmentIndex(AST):
    def __init__(self, array, index, value):
        self.array = array
        self.index = index
        self.value = value

class MemberExpression(AST):
    def __init__(self, left, name):
        self.left = left
        self.name = name

class AssignmentMember(AST):
    def __init__(self, left, name, value):
        # left: expression for object, name: attribute name
        self.left = left
        self.name = name
        self.value = value

class ClassDeclaration(AST):
    def __init__(self, name, body, base=None, implements=None):
        self.name = name
        self.body = body
        self.base = base
        self.implements = implements or []

class InterfaceDeclaration(AST):
    def __init__(self, name, body, bases=None):
        self.name = name
        self.body = body
        self.bases = bases or []

class FieldDeclaration(AST):
    def __init__(self, name, value, is_private=False):
        self.name = name
        self.value = value
        self.is_private = is_private

class NewExpression(AST):
    def __init__(self, class_name, args):
        # class_name: Identifier
        self.class_name = class_name
        self.args = args