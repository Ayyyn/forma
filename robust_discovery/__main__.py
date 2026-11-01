import argparse
from pathlib import Path
from .experiment import freeze,run,finalize
p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','numerical','meta','finalize']);p.add_argument('--directory',type=Path,default=Path('benchmarks/robust-discovery-v1'));a=p.parse_args();d=a.directory.resolve()
if a.command=='freeze':freeze(d)
elif a.command=='finalize':finalize(d)
else:run(d,a.command)
