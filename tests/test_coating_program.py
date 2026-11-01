import unittest
import numpy as np
from coating_proof.program import NumericProgram,ProgramError,BudgetEnd

EXAMPLE='''def search(initial, lower, upper, budget):
    best = copy(initial)
    loss = evaluate(best)
    n = length(initial)
    for step in range(budget - 1):
        proposal = clip(best + 0.1 * (upper-lower) * normal(n),lower,upper)
        value = evaluate(proposal)
        if value < loss:
            best = copy(proposal)
            loss = value
    return best
'''
class CoatingProgramTests(unittest.TestCase):
 def test_comparison_broadcast_and_for_else_rejected(self):
    with self.assertRaises(ProgramError):NumericProgram('def search(initial,lower,upper,budget):\n x=ones([8192,1]) < ones([1,8192])\n return initial').run(lambda x:0,[1],[0],[2],3)
    with self.assertRaises(ProgramError):NumericProgram('def search(initial,lower,upper,budget):\n for i in range(3):\n  x=1\n else:\n  x=2\n return initial')
 def test_numeric_program_runs_reproducibly_without_exec(self):
    a=[];b=[]
    def first(x):a.append(x.copy());return float(x@x)
    def second(x):b.append(x.copy());return float(x@x)
    r=NumericProgram(EXAMPLE,17).run(first,[.8,.8],[-1,-1],[1,1],20);s=NumericProgram(EXAMPLE,17).run(second,[.8,.8],[-1,-1],[1,1],20)
    self.assertEqual(r,s);np.testing.assert_array_equal(a,b);self.assertEqual(len(a),20);self.assertLess(np.dot(r['returned_vector'],r['returned_vector']),1.28)
 def test_import_attributes_strings_and_dynamic_calls_rejected(self):
    cases=['def search(initial,lower,upper,budget):\n import os\n return initial','def search(initial,lower,upper,budget):\n x=initial.__class__\n return initial','def search(initial,lower,upper,budget):\n x="secret"\n return initial']
    for source in cases:
        with self.assertRaises(ProgramError):NumericProgram(source)
    with self.assertRaises(ProgramError):NumericProgram('def search(initial,lower,upper,budget):\n return open(initial)').run(lambda x:0,[1],[0],[2],2)
 def test_allocation_and_broadcast_guard(self):
    with self.assertRaises(ProgramError):NumericProgram('def search(initial,lower,upper,budget):\n x=zeros((8192,8192))\n return initial').run(lambda x:0,[1],[0],[2],2)
 def test_oracle_budget_stops_before_extra_evaluation(self):
    count=0
    def oracle(x):
        nonlocal count
        if count==3:raise BudgetEnd()
        count+=1;return float(x@x)
    result=NumericProgram(EXAMPLE,1).run(oracle,[1],[0],[2],100);self.assertEqual(count,3);self.assertEqual(result['status'],'budget_exhausted')
 def test_array_indices_and_bounded_for_loops(self):
    source='''def search(initial,lower,upper,budget):
    pop=zeros((3,length(initial)))
    for i in range(3):
        pop[i,:]=initial
    return pop[1,:]
'''
    result=NumericProgram(source).run(lambda x:0,[1,2],[0,0],[3,3],4);self.assertEqual(result['returned_vector'],[1.,2.])

if __name__=='__main__':unittest.main()
