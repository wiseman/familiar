from __future__ import generators
import re
from utils import *

import random
from string import Template

#______________________________________________________________________________

class KB:
    def __init__(self, sentence=None):
        abstract

    def tell(self, sentence): 
        "Add the sentence to the KB"
        abstract

    def ask(self, query):
        """Ask returns a substitution that makes the query true, or
        it returns False. It is implemented in terms of ask_generator."""
        try: 
            print "\nAsk: %s" % (query,)
            answer = self.ask_generator(query).next()
            print "answer: %s" % (answer,)
            return answer
        except StopIteration:
            print "answer: False"
            return False

    def ask_all(self, query):
        print "Ask all: %s" % (query,)
        answer = list(self.ask_generator(query))
        print "answer: %s" % (answer,)
        return answer
        
            

    def ask_generator(self, query): 
        "Yield all the substitutions that make query true."
        abstract

    def retract(self, sentence):
        "Remove the sentence from the KB"
        abstract


class PropKB(KB):
    "A KB for Propositional Logic.  Inefficient, with no indexing."

    def __init__(self, sentence=None):
        self.clauses = []
        if sentence:
            self.tell(sentence)
        self.functions = {}
        self.fluents = []
        self.heritable = []
        self.install_standard_functions()
        self.with_inheritance = True

    def tell(self, sentence): 
        "Add the sentence's clauses to the KB"
        if sentence.op == "ISA":
            self.assert_isa(sentence.args[0], sentence.args[1])
        else:
            if sentence.op in self.fluents:
                self.retract(expr("%s(%s,x)" % (sentence.op, sentence.args[0])))
            self.clauses.extend(conjuncts(to_cnf(sentence)))        

    def assert_isa(self, child, parent):
        self.tell(expr("$ISA(%s, %s)" % (child, parent)))
        
    def ask_generator(self, query, s = {}): 
        print "ASK_GENERATOR: query: %s  s: %s" % (str(query), str(s))
        "YIELD the empty substitution if KB implies query; else False"
        if query.op == '&':
            binding_generator = self.ask_and(query, s)
        elif query.op == '|':
            binding_generator = self.ask_or(query, s)
        elif query.op in self.functions:
            binding_generator = self.ask_function(query, s)
        else:
            binding_generator = self.ask_simple(query, s, with_inheritance=self.with_inheritance)
        return binding_generator

    def retract(self, query):
        "Remove the sentence's clauses from the KB"
        self.clauses = [x for x in self.clauses if unify(query, x, {}) == None]

    def ask_simple(self, query, active_bindings, with_inheritance=True):
        if with_inheritance and query.op in self.heritable:
            for bindings in self.ask_with_inheritance(query, active_bindings):
                yield bindings
        else:
            for clause in self.clauses:
                bindings = unify(query, clause, active_bindings)
                if bindings != None:
                    yield bindings

    def ask_with_inheritance(self, query, active_bindings):
        print "PERFORMING INHERITANCE %s" % (query.args,)
        slot = query.op
        thing = subst(active_bindings, query.args[0])
        slot_value = subst(active_bindings, query.args[1])
        if is_var_symbol(slot_value.op):
            # Find the value of a slot
            for parent in self.all_parents(thing.op):
                for binding in self.ask_simple(expr("%s(%s, v)" % (query.op, parent)), {}, with_inheritance=False):
                    print "INHERITING %s: %s" % (query.args[1], binding[expr("v")])
                    yield extend(active_bindings, query.args[1], binding[expr("v")])
        if is_var_symbol(thing.op):
            print "WE HAVE A VARIABLE THING"
            # Find all things that have a particular slot-value,
            # including through inheritance.
            query_template = Template("(${Slot}(${Parent}, ${Value}) & (ISA(${Thing}, ${Parent}) &" +
                                      "(~(ISA(${Thing}, ${Otherparent}) & (${Slot}(${Otherparent}, ${Othervalue}) & (~(${Thing} <=> ${Otherparent})))))))")
            newquery = query_template.substitute(Slot = slot,
                                                 Thing = "t",
                                                 Value = slot_value.op,
                                                 Parent = "p",
                                                 Otherparent = "o",
                                                 Othervalue = "w")
            print "CRAZY QUERY IS %s" % (newquery,)
            self.with_inheritance = False
            for binding in self.ask_generator(expr(newquery), {}):
                print "CRAZY BINDING: %s" % (binding,)
                yield extend(active_bindings, thing, binding[slot_value])
            self.with_inheritance = True
            
    def all_parents(self, x):
        parents = []
        for binding in self.ask_generator(expr("ISA(%s, x)" % (x,))):
            parents.append(binding[expr("x")].op)
        return parents

    def isa(self, a, b):
        return b in self.all_parents(a)

    def install_function(self, op, function):
        self.functions[op] = function

    def ask_function(self, query, s):
        function = self.functions[query.op]
        bindings = function.eval(self, query, s)
        for bindings in bindings:
            yield bindings
                
    def ask_and(self, query, s):
        arg1 = query.args[0]
        arg2 = query.args[1]
        for bindings in self.ask_generator(arg1, s):
            for more_bindings in self.ask_generator(arg2, bindings):
                if more_bindings != None:
                    yield more_bindings

    def ask_or(self, query, s):
        arg1 = query.args[0]
        arg2 = query.args[1]
        for bindings in self.ask_generator(arg1, s):
            yield bindings
        for bindings in self.ask_generator(arg2, s):
            yield bindings

    def ask_not(self, query, s):
        try:
            self.ask_generator(query.args[0], s).next()
            return
        except StopIteration:
            yield s

    def install_standard_functions(self):
        self.install_function("<=>", EqualFunction())
        self.install_function("~", NotFunction())
        self.install_function("Bind", BindFunction())
        self.install_function("ISA", ISAFunction())

    def install_standard_propositions(self):
        pass
    
    def defineFluent(self, relation, inherited=False):
        self.fluents.append(relation)
        if inherited:
            self.heritable.append(relation)
            

class MemoryFunction:
    def eval(self, kb, expr, s):
       raise NotImplementedError

class NotFunction(MemoryFunction):
    def eval(self, kb, expr, s):
        try:
            kb.ask_generator(expr.args[0], s).next()
            return
        except StopIteration:
            yield s
        
class EqualFunction(MemoryFunction):
    def eval(self, kb, expr, s):
        arg1 = subst(s, expr.args[0])
        arg2 = subst(s, expr.args[1])
        if arg1 == arg2:
            yield s
        else:
            return

class BindFunction(MemoryFunction):
    def eval(self, kb, expr, s):
        if expr.args[0] in s:
            return
        else:
            yield extend(s, expr.args[0], expr.args[1])

def randomvar():
    return random.choice("abcdefghijklmnopqrstuvwxyz")

class ISAFunction(MemoryFunction):
    def eval(self, kb, query, s):
        print "ISA-QUERY: %s" % (query,)
        child = query.args[0]
        parent = query.args[1]
        v = newuniquevar(query)
        isastring = "($ISA(%s, %s) | ($ISA(%s, %s) & ISA(%s, %s)))" % (child, parent, child, v, v, parent)
        isaexpr = expr(isastring)
        generator = removevars(kb.ask_generator(isaexpr, s), (v,))
        subst_query = subst(s, query)
        subst_child = subst_query.args[0]
        subst_parent = subst_query.args[1]
        if is_var_symbol(subst_child.op):
            print "extending child %s with %s" % (subst_child, subst_parent)
            yield extend(s, subst_child, subst_parent)
        if is_var_symbol(subst_parent.op):
            print "extending parent %s with %s" % (subst_parent, subst_child)
            yield extend(s, subst_parent, subst_child)
        for bindings in generator:
            yield bindings


def newuniquevar(sentence, count=1):
    var = expr("x%s" % (count,))
    if occur_check(var, sentence):
        return newuniquevar(sentence, count + 1)
    else:
        return var

def removevars(bindings, vars):
    print "REMOVEVARS: %s  %s" % (bindings, vars)
    for s in bindings:
        print "checking %s" % (s,)
        for var in vars:
            if var in s:
                del s[var]
        yield s

#______________________________________________________________________________
    
class Expr:
    """A symbolic mathematical expression.  We use this class for logical
    expressions, and for terms within logical expressions. In general, an
    Expr has an op (operator) and a list of args.  The op can be:
      Null-ary (no args) op:
        A number, representing the number itself.  (e.g. Expr(42) => 42)
        A symbol, representing a variable or constant (e.g. Expr('F') => F)
      Unary (1 arg) op:
        '~', '-', representing NOT, negation (e.g. Expr('~', Expr('P')) => ~P)
      Binary (2 arg) op:
        '>>', '<<', representing forward and backward implication
        '+', '-', '*', '/', '**', representing arithmetic operators
        '<', '>', '>=', '<=', representing comparison operators
        '<=>', '^', representing logical equality and XOR
      N-ary (0 or more args) op:
        '&', '|', representing conjunction and disjunction
        A symbol, representing a function term or FOL proposition

    Exprs can be constructed with operator overloading: if x and y are Exprs,
    then so are x + y and x & y, etc.  Also, if F and x are Exprs, then so is 
    F(x); it works by overloading the __call__ method of the Expr F.  Note 
    that in the Expr that is created by F(x), the op is the str 'F', not the 
    Expr F.   See http://www.python.org/doc/current/ref/specialnames.html 
    to learn more about operator overloading in Python.

    WARNING: x == y and x != y are NOT Exprs.  The reason is that we want
    to write code that tests 'if x == y:' and if x == y were the same
    as Expr('==', x, y), then the result would always be true; not what a
    programmer would expect.  But we still need to form Exprs representing
    equalities and disequalities.  We concentrate on logical equality (or
    equivalence) and logical disequality (or XOR).  You have 3 choices:
        (1) Expr('<=>', x, y) and Expr('^', x, y)
            Note that ^ is bitwose XOR in Python (and Java and C++)
        (2) expr('x <=> y') and expr('x =/= y').  
            See the doc string for the function expr.
        (3) (x % y) and (x ^ y).
            It is very ugly to have (x % y) mean (x <=> y), but we need
            SOME operator to make (2) work, and this seems the best choice.

    WARNING: if x is an Expr, then so is x + 1, because the int 1 gets
    coerced to an Expr by the constructor.  But 1 + x is an error, because
    1 doesn't know how to add an Expr.  (Adding an __radd__ method to Expr
    wouldn't help, because int.__add__ is still called first.) Therefore,
    you should use Expr(1) + x instead, or ONE + x, or expr('1 + x').
    """

    def __init__(self, op, *args):
        "Op is a string or number; args are Exprs (or are coerced to Exprs)."
        assert isinstance(op, str) or (isnumber(op) and not args)
        self.op = num_or_str(op)
        self.args = map(expr, args) ## Coerce args to Exprs

    def __call__(self, *args):
        """Self must be a symbol with no args, such as Expr('F').  Create a new
        Expr with 'F' as op and the args as arguments."""
        assert is_symbol(self.op) and not self.args, "%s is not a symbol or there are args: %s" % (self.op, self.args)
        return Expr(self.op, *args)

    def __repr__(self):
        return '<%s: "%s">' % (x.__class__.__name__, str(self))
    
    def __str__(self):
        "Show something like 'P' or 'P(x, y)', or '~P' or '(P | Q | R)'"
        if len(self.args) == 0: # Constant or proposition with arity 0
            return str(self.op)
        elif is_symbol(self.op): # Functional or Propositional operator
            return '%s(%s)' % (self.op, ', '.join(map(repr, self.args)))
        elif len(self.args) == 1: # Prefix operator
            return self.op + repr(self.args[0])
        else: # Infix operator
            return '(%s)' % (' '+self.op+' ').join(map(repr, self.args))

    def __eq__(self, other):
        """x and y are equal iff their ops and args are equal."""
        return (other is self) or (isinstance(other, Expr) 
            and self.op == other.op and self.args == other.args)

    def __hash__(self):
        "Need a hash method so Exprs can live in dicts."
        return hash(self.op) ^ hash(tuple(self.args))

    # See http://www.python.org/doc/current/lib/module-operator.html
    # Not implemented: not, abs, pos, concat, contains, *item, *slice
    def __lt__(self, other):     return Expr('<',  self, other)
    def __le__(self, other):     return Expr('<=', self, other)
    def __ge__(self, other):     return Expr('>=', self, other)
    def __gt__(self, other):     return Expr('>',  self, other)
    def __add__(self, other):    return Expr('+',  self, other)
    def __sub__(self, other):    return Expr('-',  self, other)
    def __and__(self, other):    return Expr('&',  self, other)
    def __div__(self, other):    return Expr('/',  self, other)
    def __truediv__(self, other):return Expr('/',  self, other)
    def __invert__(self):        return Expr('~',  self)
    def __lshift__(self, other): return Expr('<<', self, other)
    def __rshift__(self, other): return Expr('>>', self, other)
    def __mul__(self, other):    return Expr('*',  self, other)
    def __neg__(self):           return Expr('-',  self)
    def __or__(self, other):     return Expr('|',  self, other)
    def __pow__(self, other):    return Expr('**', self, other)
    def __xor__(self, other):    return Expr('^',  self, other)
    def __mod__(self, other):    return Expr('<=>',  self, other) ## (x % y)
    


def expr(s):
    """Create an Expr representing a logic expression by parsing the input
    string. Symbols and numbers are automatically converted to Exprs.
    In addition you can use alternative spellings of these operators:
      'x ==> y'   parses as   (x >> y)    # Implication
      'x <== y'   parses as   (x << y)    # Reverse implication
      'x <=> y'   parses as   (x % y)     # Logical equivalence
      'x =/= y'   parses as   (x ^ y)     # Logical disequality (xor)
    But BE CAREFUL; precedence of implication is wrong. expr('P & Q ==> R & S')
    is ((P & (Q >> R)) & S); so you must use expr('(P & Q) ==> (R & S)').
    >>> expr('P <=> Q(1)')
    (P <=> Q(1))
    >>> expr('P & Q | ~R(x, F(x))')
    ((P & Q) | ~R(x, F(x)))
    """
    if isinstance(s, Expr): return s
    if isnumber(s): return Expr(s)
    ## Replace the alternative spellings of operators with canonical spellings
    s = s.replace('==>', '>>').replace('<==', '<<')
    s = s.replace('<=>', '%').replace('=/=', '^')
    ## Replace a symbol or number, such as 'P' with 'Expr("P")'
    s = re.sub(r'([a-zA-Z0-9_$.]+)', r'Expr("\1")', s)
    ## Now eval the string.  (A security hole; do not use with an adversary.)
    return eval(s, {'Expr':Expr})

def is_symbol(s):
    "A string s is a symbol if it starts with an alphabetic char."
    return isinstance(s, str) and (s[0].isalpha() or s[0] == '$')

def is_var_symbol(s):
    "A logic variable symbol is an initial-lowercase string."
    return is_symbol(s) and s[0].islower()

def is_prop_symbol(s):
    """A proposition logic symbol is an initial-uppercase string other than
    TRUE or FALSE."""
    return is_symbol(s) and (s[0].isupper() or s[0] == '$') and s != 'TRUE' and s != 'FALSE'


## Useful constant Exprs used in examples and code:
TRUE, FALSE, ZERO, ONE, TWO = map(Expr, ['TRUE', 'FALSE', 0, 1, 2]) 
A, B, C, F, G, P, Q, x, y, z  = map(Expr, 'ABCFGPQxyz') 

#______________________________________________________________________________

def tt_entails(kb, alpha):
    """Use truth tables to determine if KB entails sentence alpha. [Fig. 7.10]
    >>> tt_entails(expr('P & Q'), expr('Q'))
    True
    """
    return tt_check_all(kb, alpha, prop_symbols(kb & alpha), {})

def tt_check_all(kb, alpha, symbols, model):
    "Auxiliary routine to implement tt_entails."
    if not symbols:
        if pl_true(kb, model): return pl_true(alpha, model)
        else: return True
        assert result != None
    else:
        P, rest = symbols[0], symbols[1:]
        return (tt_check_all(kb, alpha, rest, extend(model, P, True)) and
                tt_check_all(kb, alpha, rest, extend(model, P, False)))

def prop_symbols(x):
    "Return a list of all propositional symbols in x."
    if not isinstance(x, Expr):
        return []
    elif is_prop_symbol(x.op):
        return [x]
    else:
        s = set(())
        for arg in x.args:
            for symbol in prop_symbols(arg):
                s.add(symbol)
        return list(s)

def tt_true(alpha):
    """Is the sentence alpha a tautology? (alpha will be coerced to an expr.)
    >>> tt_true(expr("(P >> Q) <=> (~P | Q)"))
    True
    """
    return tt_entails(TRUE, expr(alpha))

def pl_true(exp, model={}):
    """Return True if the propositional logic expression is true in the model,
    and False if it is false. If the model does not specify the value for
    every proposition, this may return None to indicate 'not obvious';
    this may happen even when the expression is tautological."""
    op, args = exp.op, exp.args
    if exp == TRUE:
        return True
    elif exp == FALSE:
        return False
    elif is_prop_symbol(op):
        return model.get(exp)
    elif op == '~':
        p = pl_true(args[0], model)
        if p == None: return None
        else: return not p
    elif op == '|':
        result = False
        for arg in args:
            p = pl_true(arg, model)
            if p == True: return True
            if p == None: result = None
        return result
    elif op == '&':
        result = True
        for arg in args:
            p = pl_true(arg, model)
            if p == False: return False
            if p == None: result = None
        return result
    p, q = args
    if op == '>>':
        return pl_true(~p | q, model)
    elif op == '<<':
        return pl_true(p | ~q, model)
    pt = pl_true(p, model)
    if pt == None: return None
    qt = pl_true(q, model)
    if qt == None: return None
    if op == '<=>':
        return pt == qt
    elif op == '^':
        return pt != qt
    else:
        raise ValueError, "illegal operator in logic expression" + str(exp)

#______________________________________________________________________________

## Convert to Conjunctive Normal Form (CNF)
 
def to_cnf(s):
    """Convert a propositional logical sentence s to conjunctive normal form.
    That is, of the form ((A | ~B | ...) & (B | C | ...) & ...) [p. 215]
    >>> to_cnf("~(B|C)")
    (~B & ~C)
    >>> to_cnf("B <=> (P1|P2)")
    ((~P1 | B) & (~P2 | B) & (P1 | P2 | ~B))
    >>> to_cnf("a | (b & c) | d")
    ((b | a | d) & (c | a | d))
    >>> to_cnf("A & (B | (D & E))")
    (A & (D | B) & (E | B))
    """
    if isinstance(s, str): s = expr(s)
    s = eliminate_implications(s) # Steps 1, 2 from p. 215
    s = move_not_inwards(s) # Step 3
    return distribute_and_over_or(s) # Step 4
    
def eliminate_implications(s):
    """Change >>, <<, and <=> into &, |, and ~. That is, return an Expr
    that is equivalent to s, but has only &, |, and ~ as logical operators.
    >>> eliminate_implications(A >> (~B << C))
    ((~B | ~C) | ~A)
    """
    if not s.args or is_symbol(s.op): return s     ## (Atoms are unchanged.)
    args = map(eliminate_implications, s.args)
    a, b = args[0], args[-1]
    if s.op == '>>':
        return (b | ~a)
    elif s.op == '<<':
        return (a | ~b)
    elif s.op == '<=>':
        return (a | ~b) & (b | ~a)
    else:
        return Expr(s.op, *args)

def move_not_inwards(s):
    """Rewrite sentence s by moving negation sign inward.
    >>> move_not_inwards(~(A | B))
    (~A & ~B)
    >>> move_not_inwards(~(A & B))
    (~A | ~B)
    >>> move_not_inwards(~(~(A | ~B) | ~~C))
    ((A | ~B) & ~C)
    """
    if s.op == '~':
        NOT = lambda b: move_not_inwards(~b)
        a = s.args[0]
        if a.op == '~': return move_not_inwards(a.args[0]) # ~~A ==> A
        if a.op =='&': return NaryExpr('|', *map(NOT, a.args))
        if a.op =='|': return NaryExpr('&', *map(NOT, a.args))
        return s
    elif is_symbol(s.op) or not s.args:
        return s
    else:
        return Expr(s.op, *map(move_not_inwards, s.args))

def distribute_and_over_or(s):
    """Given a sentence s consisting of conjunctions and disjunctions
    of literals, return an equivalent sentence in CNF.
    >>> distribute_and_over_or((A & B) | C)
    ((A | C) & (B | C))
    """
    if s.op == '|':
        s = NaryExpr('|', *s.args)
        if len(s.args) == 0: 
            return FALSE
        if len(s.args) == 1: 
            return distribute_and_over_or(s.args[0])
        conj = find_if((lambda d: d.op == '&'), s.args)
        if not conj:
            return NaryExpr(s.op, *s.args)
        others = [a for a in s.args if a is not conj]
        if len(others) == 1:
            rest = others[0]
        else:
            rest = NaryExpr('|', *others)
        return NaryExpr('&', *map(distribute_and_over_or,
                                  [(c|rest) for c in conj.args]))
    elif s.op == '&':
        return NaryExpr('&', *map(distribute_and_over_or, s.args))
    else:
        return s

_NaryExprTable = {'&':TRUE, '|':FALSE, '+':ZERO, '*':ONE}

def NaryExpr(op, *args):
    """Create an Expr, but with an nary, associative op, so we can promote
    nested instances of the same op up to the top level.
    >>> NaryExpr('&', (A&B),(B|C),(B&C))
    (A & B & (B | C) & B & C)
    """
    arglist = []
    for arg in args:
        if arg.op == op: arglist.extend(arg.args)
        else: arglist.append(arg)
    if len(args) == 1:
        return args[0]
    elif len(args) == 0:
        return _NaryExprTable[op]
    else:
        return Expr(op, *arglist)

def conjuncts(s):
    """Return a list of the conjuncts in the sentence s.
    >>> conjuncts(A & B)
    [A, B]
    >>> conjuncts(A | B)
    [(A | B)]
    """
    if isinstance(s, Expr) and s.op == '&': 
        return s.args
    else:
        return [s]

def disjuncts(s):
    """Return a list of the disjuncts in the sentence s.
    >>> disjuncts(A | B)
    [A, B]
    >>> disjuncts(A & B)
    [(A & B)]
    """
    if isinstance(s, Expr) and s.op == '|': 
        return s.args
    else:
        return [s]

#______________________________________________________________________________

def pl_resolution(KB, alpha):
    "Propositional Logic Resolution: say if alpha follows from KB. [Fig. 7.12]"
    clauses = KB.clauses + conjuncts(to_cnf(~alpha))
    new = set()
    while True:
        n = len(clauses)
        pairs = [(clauses[i], clauses[j]) for i in range(n) for j in range(i+1, n)]
        for (ci, cj) in pairs:
            resolvents = pl_resolve(ci, cj)
            if FALSE in resolvents: return True
            new.union_update(set(resolvents))
        if new.issubset(set(clauses)): return False
        for c in new:
            if c not in clauses: clauses.append(c)

def pl_resolve(ci, cj):
    """Return all clauses that can be obtained by resolving clauses ci and cj.
    >>> pl_resolve(to_cnf(A|B|C), to_cnf(~B|~C|F))
    [(A | C | ~C | F), (A | B | ~B | F)]
    """
    clauses = []
    for di in disjuncts(ci):
        for dj in disjuncts(cj):
            if di == ~dj or ~di == dj:
                dnew = unique(removeall(di, disjuncts(ci)) + 
                              removeall(dj, disjuncts(cj)))
                clauses.append(NaryExpr('|', *dnew))
    return clauses

#______________________________________________________________________________

def find_pure_symbol(symbols, unknown_clauses):
    """Find a symbol and its value if it appears only as a positive literal
    (or only as a negative) in clauses.
    >>> find_pure_symbol([A, B, C], [A|~B,~B|~C,C|A])
    (A, True)
    """
    for s in symbols:
        found_pos, found_neg = False, False
        for c in unknown_clauses:
            if not found_pos and s in disjuncts(c): found_pos = True
            if not found_neg and ~s in disjuncts(c): found_neg = True
        if found_pos != found_neg: return s, found_pos
    return None, None

def find_unit_clause(clauses, model):
    """A unit clause has only 1 variable that is not bound in the model.
    >>> find_unit_clause([A|B|C, B|~C, A|~B], {A:True})
    (B, False)
    """
    for clause in clauses:
        num_not_in_model = 0
        for literal in disjuncts(clause):
            sym = literal_symbol(literal)
            if sym not in model:
                num_not_in_model += 1
                P, value = sym, (literal.op != '~')
        if num_not_in_model == 1:
            return P, value
    return None, None
                

def literal_symbol(literal):
    """The symbol in this literal (without the negation).
    >>> literal_symbol(P)
    P
    >>> literal_symbol(~P)
    P
    """
    if literal.op == '~':
        return literal.args[0]
    else:
        return literal
        

#______________________________________________________________________________

def unify(x, y, s):
    """Unify expressions x,y with substitution s; return a substitution that
    would make x,y equal, or None if x,y can not unify. x and y can be
    variables (e.g. Expr('x')), constants, lists, or Exprs. [Fig. 9.1]
    >>> unify(x + y, y + C, {})
    {y: C, x: y}
    """
    if s == None:
        return None
    elif x == y:
        return s
    elif is_variable(x):
        return unify_var(x, y, s)
    elif is_variable(y):
        return unify_var(y, x, s)
    elif isinstance(x, Expr) and isinstance(y, Expr):
        return unify(x.args, y.args, unify(x.op, y.op, s))
    elif isinstance(x, str) or isinstance(y, str) or not x or not y:
        return if_(x == y, s, None)
    elif issequence(x) and issequence(y) and len(x) == len(y):
        return unify(x[1:], y[1:], unify(x[0], y[0], s))
    else:
        return None

def is_variable(x):
    "A variable is an Expr with no args and a lowercase symbol as the op."
    return isinstance(x, Expr) and not x.args and is_var_symbol(x.op)

def unify_var(var, x, s):
    if var in s:
        return unify(s[var], x, s)
    elif occur_check(var, x):
        return None
    else:
        return extend(s, var, x)

def occur_check(var, x):
    "Return true if var occurs anywhere in x."
    if var == x:
        return True
    elif isinstance(x, Expr):
        return var.op == x.op or occur_check(var, x.args)
    elif not isinstance(x, str) and issequence(x):
        for xi in x:
            if occur_check(var, xi): return True
    return False

def extend(s, var, val):
    """Copy the substitution s and extend it by setting var to val; return copy.
    >>> extend({x: 1}, y, 2)
    {y: 2, x: 1}
    """
    s2 = s.copy()
    s2[var] = val
    return s2
    
def subst(s, x):
    """Substitute the substitution s into the expression x.
    >>> subst({x: 42, y:0}, F(x) + y)
    (F(42) + 0)
    """
    if isinstance(x, list): 
        return [subst(s, xi) for xi in x]
    elif isinstance(x, tuple): 
        return tuple([subst(s, xi) for xi in x])
    elif not isinstance(x, Expr): 
        return x
    elif is_var_symbol(x.op): 
        return s.get(x, x)
    else: 
        return Expr(x.op, *[subst(s, arg) for arg in x.args])
        
def standardize_apart(sentence, dic):
    """Replace all the variables in sentence with new variables."""
    if not isinstance(sentence, Expr): 
        return sentence
    elif is_var_symbol(sentence.op): 
        if sentence in dic:
            return dic[sentence]
        else:
            standardize_apart.counter += 1
            dic[sentence] = Expr('V_%d' % standardize-apart.counter)
            return dic[sentence]
    else: 
        return Expr(sentence.op, *[standardize-apart(a, dic) for a in sentence.args])
