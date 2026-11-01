import argparse
from pathlib import Path
from .experiment import freeze,run,report
p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','numerical','meta','report']);p.add_argument('--directory',type=Path,default=Path('benchmarks/frontier-materials-portfolio-v1'));a=p.parse_args();d=a.directory.resolve()
if a.command=='freeze':freeze(d)
elif a.command=='report':report(d)
else:run(d,a.command)
