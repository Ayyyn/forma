import argparse
from pathlib import Path
from .experiment import freeze,run,finalize
p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','numerical','meta','finalize']);p.add_argument('--directory',type=Path,default=Path('benchmarks/nonlinear-discovery-v1'));a=p.parse_args();directory=a.directory.resolve()
if a.command=='freeze':freeze(directory)
elif a.command=='finalize':finalize(directory)
else:run(directory,a.command)
