"""Interpreter for a bounded numerical Python subset; NEVER executes Python.

No imports, attributes, strings, function objects, file/network operations,
while loops or recursion. Bounded arrays, broadcasting, AST steps and for loops.
This is a purpose-built numerical DSL, not a general Python security sandbox.
"""
import ast
import numpy as np

class ProgramError(ValueError):pass
class BudgetEnd(Exception):pass

class NumericProgram:
 def __init__(self,source,seed=0):
    if not isinstance(source,str) or len(source)>15000:raise ProgramError('Program source exceeds15000 characters')
    try:tree=ast.parse(source)
    except SyntaxError as exc:raise ProgramError(str(exc))
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef):raise ProgramError('Exactly one search function required')
    self.fn=tree.body[0]
    if self.fn.name!='search' or [a.arg for a in self.fn.args.args]!=['initial','lower','upper','budget'] or self.fn.args.defaults or self.fn.args.kwonlyargs or self.fn.args.vararg or self.fn.args.kwarg or self.fn.decorator_list:raise ProgramError('Signature must be search(initial,lower,upper,budget) without defaults/decorators')
    allowed=(ast.Module,ast.FunctionDef,ast.arguments,ast.arg,ast.Assign,ast.AugAssign,ast.Return,ast.For,ast.If,ast.Break,ast.Continue,ast.Expr,ast.Name,ast.Load,ast.Store,ast.Constant,ast.List,ast.Tuple,ast.Subscript,ast.Slice,ast.BinOp,ast.UnaryOp,ast.BoolOp,ast.Compare,ast.Call,ast.IfExp,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow,ast.USub,ast.UAdd,ast.Not,ast.And,ast.Or,ast.BitAnd,ast.BitOr,ast.Lt,ast.LtE,ast.Gt,ast.GtE,ast.Eq,ast.NotEq)
    nodes=list(ast.walk(tree))
    if len(nodes)>1200:raise ProgramError('AST exceeds1200 nodes')
    for node in nodes:
        if not isinstance(node,allowed):raise ProgramError('Unsupported syntax: '+type(node).__name__)
        if isinstance(node,ast.FunctionDef) and node is not self.fn:raise ProgramError('No nested functions')
        if isinstance(node,ast.Name) and node.id.startswith('__'):raise ProgramError('No dunder names')
        if isinstance(node,ast.Constant) and (not isinstance(node.value,(int,float,bool)) or abs(node.value)>1e6):raise ProgramError('Only bounded numerical constants')
        if isinstance(node,ast.Call) and (not isinstance(node.func,ast.Name) or node.keywords):raise ProgramError('Only named numerical calls, positional arguments')
        if isinstance(node,ast.For) and node.orelse:raise ProgramError('For/else is not in this numerical language')
    self.rng=np.random.default_rng(seed);self.steps=0;self.maximum_steps=200000;self.env={};self.returned=None
 def tick(self):
    self.steps+=1
    if self.steps>self.maximum_steps:raise ProgramError('AST step limit')
 def array(self,value):
    a=np.asarray(value)
    if a.dtype.kind not in 'bifu' or a.ndim>2 or a.size>8192 or not np.isfinite(a).all():raise ProgramError('Finite numeric arrays <=8192 elements and2 dimensions only')
    return a
 def shape(self,value):
    a=np.atleast_1d(self.array(value));dims=tuple(self.integer(v) for v in a)
    if not 1<=len(dims)<=2 or min(dims)<1 or np.prod(dims)>8192:raise ProgramError('Allocation bounds')
    return dims
 def integer(self,value):
    if not np.isscalar(value) or not np.isfinite(value) or float(value)!=int(value) or abs(value)>1e6:raise ProgramError('Bounded scalar integer required')
    return int(value)
 def truth(self,value):
    if np.ndim(value)!=0:raise ProgramError('If/bool requires scalar; use all/any for an array')
    return bool(value)
 def binary(self,op,a,b):
    a=self.array(a);b=self.array(b)
    if np.prod(np.broadcast_shapes(a.shape,b.shape))>8192:raise ProgramError('Broadcast allocation limit')
    functions={ast.Add:np.add,ast.Sub:np.subtract,ast.Mult:np.multiply,ast.Div:np.divide,ast.Pow:np.power,ast.BitAnd:np.logical_and,ast.BitOr:np.logical_or}
    if isinstance(op,ast.Pow) and (b.ndim!=0 or abs(float(b))>4):raise ProgramError('Power exponent must be a scalar within±4')
    try:
        with np.errstate(all='raise'):result=functions[type(op)](a,b)
    except (FloatingPointError,KeyError,ValueError) as exc:raise ProgramError(str(exc))
    result=self.array(result);return result.item() if result.ndim==0 else result
 def call(self,name,args):
    if name=='evaluate':
        if len(args)!=1:raise ProgramError('evaluate takes one vector')
        return self.evaluate(self.array(args[0]))
    if name in ['zeros','ones','rand','normal']:
        if len(args)!=1:raise ProgramError(name+' takes one shape')
        shape=self.shape(args[0]);return {'zeros':np.zeros,'ones':np.ones,'rand':self.rng.random,'normal':self.rng.standard_normal}[name](shape)
    if name=='range':
        if not 1<=len(args)<=3:raise ProgramError('range arity')
        values=range(*[self.integer(a) for a in args])
        if len(values)>4096:raise ProgramError('Loop range exceeds4096')
        return np.array(values,dtype=int)
    if name=='randint':return int(self.rng.integers(self.integer(args[0]),self.integer(args[1])))
    if name=='permutation':
        n=self.integer(args[0])
        if not 0<n<=4096:raise ProgramError('Permutation limit')
        return self.rng.permutation(n)
    if name in ['length','len']:return len(self.array(args[0]))
    if name=='int':return self.integer(args[0])
    if name=='float':return float(self.array(args[0]))
    functions={'copy':lambda x:np.array(x,copy=True),'clip':np.clip,'where':np.where,'argmin':np.argmin,'argmax':np.argmax,'argsort':np.argsort,'abs':np.abs,'sqrt':np.sqrt,'exp':np.exp,'log':np.log,'sin':np.sin,'cos':np.cos,'sum':np.sum,'mean':np.mean,'std':np.std,'min':np.min,'max':np.max,'minimum':np.minimum,'maximum':np.maximum,'all':np.all,'any':np.any}
    if name not in functions:raise ProgramError('Unknown numerical function: '+name)
    values=[self.array(a) for a in args]
    if name in ['clip','where','minimum','maximum'] and np.prod(np.broadcast_shapes(*(a.shape for a in values)))>8192:raise ProgramError('Broadcast limit')
    try:
        with np.errstate(all='raise'):result=functions[name](*values)
    except (TypeError,ValueError,FloatingPointError) as exc:raise ProgramError(str(exc))
    result=self.array(result);return result.item() if result.ndim==0 else result
 def subindex(self,node):
    if isinstance(node,ast.Tuple):return tuple(self.subindex(v) for v in node.elts)
    if isinstance(node,ast.Slice):return slice(*(None if v is None else self.integer(self.value(v)) for v in [node.lower,node.upper,node.step]))
    value=self.value(node)
    if np.ndim(value)==0:return self.integer(value)
    a=self.array(value)
    if a.dtype.kind=='b':return a
    if not np.equal(a,np.floor(a)).all():raise ProgramError('Integer array index required')
    return a.astype(int)
 def value(self,node):
    self.tick()
    if isinstance(node,ast.Constant):return node.value
    if isinstance(node,ast.Name):
        if node.id not in self.env:raise ProgramError('Unknown numerical variable: '+node.id)
        return self.env[node.id]
    if isinstance(node,(ast.List,ast.Tuple)):return self.array([self.value(v) for v in node.elts])
    if isinstance(node,ast.BinOp):return self.binary(node.op,self.value(node.left),self.value(node.right))
    if isinstance(node,ast.UnaryOp):
        a=self.value(node.operand)
        return -self.array(a) if isinstance(node.op,ast.USub) else (+self.array(a) if isinstance(node.op,ast.UAdd) else not self.truth(a))
    if isinstance(node,ast.Call):return self.call(node.func.id,[self.value(v) for v in node.args])
    if isinstance(node,ast.Subscript):return self.array(self.value(node.value))[self.subindex(node.slice)]
    if isinstance(node,ast.IfExp):return self.value(node.body if self.truth(self.value(node.test)) else node.orelse)
    if isinstance(node,ast.BoolOp):
        values=[self.truth(self.value(v)) for v in node.values];return all(values) if isinstance(node.op,ast.And) else any(values)
    if isinstance(node,ast.Compare):
        operations={ast.Lt:np.less,ast.LtE:np.less_equal,ast.Gt:np.greater,ast.GtE:np.greater_equal,ast.Eq:np.equal,ast.NotEq:np.not_equal};a=self.value(node.left);result=True
        for op,right in zip(node.ops,node.comparators):
            b=self.value(right)
            if np.prod(np.broadcast_shapes(np.shape(a),np.shape(b),np.shape(result)))>8192:raise ProgramError('Comparison broadcast limit')
            result=np.logical_and(result,operations[type(op)](a,b));a=b
        return result
    raise ProgramError('Unsupported expression: '+type(node).__name__)
 def assign(self,node,value):
    value=self.array(value);value=value.item() if value.ndim==0 else value
    if isinstance(node,ast.Name):self.env[node.id]=value
    elif isinstance(node,ast.Subscript):
        target=self.value(node.value);index=self.subindex(node.slice)
        try:target[index]=value
        except (TypeError,ValueError,IndexError) as exc:raise ProgramError(str(exc))
    else:raise ProgramError('Only variable or numeric-array assignment')
 def block(self,nodes):
    for node in nodes:
        self.tick()
        if isinstance(node,ast.Assign):
            if len(node.targets)!=1:raise ProgramError('Single assignment target required')
            self.assign(node.targets[0],self.value(node.value))
        elif isinstance(node,ast.AugAssign):self.assign(node.target,self.binary(node.op,self.value(node.target),self.value(node.value)))
        elif isinstance(node,ast.Expr):self.value(node.value)
        elif isinstance(node,ast.Return):self.returned=self.value(node.value);return 'return'
        elif isinstance(node,ast.If):
            control=self.block(node.body if self.truth(self.value(node.test)) else node.orelse)
            if control:return control
        elif isinstance(node,ast.For):
            iterable=self.array(self.value(node.iter))
            if iterable.ndim!=1 or len(iterable)>4096:raise ProgramError('Bounded1D iteration only')
            for item in iterable:
                self.assign(node.target,item.item());control=self.block(node.body)
                if control=='return':return control
                if control=='break':break
        elif isinstance(node,ast.Break):return 'break'
        elif isinstance(node,ast.Continue):return 'continue'
        else:raise ProgramError('Unsupported statement')
    return None
 def run(self,evaluate,initial,lower,upper,budget):
    self.evaluate=evaluate;self.env={'initial':np.array(initial,float,copy=True),'lower':np.array(lower,float,copy=True),'upper':np.array(upper,float,copy=True),'budget':int(budget)}
    try:self.block(self.fn.body)
    except BudgetEnd:return {'status':'budget_exhausted','steps':self.steps}
    result=self.array(self.returned)
    if result.shape!=np.asarray(initial).shape:raise ProgramError('Return must be a candidate vector')
    return {'status':'returned','steps':self.steps,'returned_vector':result.tolist()}
