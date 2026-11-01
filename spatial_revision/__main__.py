import argparse
from pathlib import Path
from .study import freeze,run,report

parser=argparse.ArgumentParser();parser.add_argument('command',choices=['freeze','run','report']);parser.add_argument('--directory',type=Path,default=Path('benchmarks/spatial-revision-v1'));parser.add_argument('--workers',type=int,choices=[1,2,4],default=4);args=parser.parse_args();directory=args.directory.resolve()
if args.command=='freeze':freeze(directory)
elif args.command=='run':run(directory,args.workers)
else:report(directory)
