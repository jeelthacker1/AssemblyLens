"""Evaluate independently labeled inspection outcomes; never invent ground truth."""
import argparse,json
from pathlib import Path
from backend.training import quality_metrics

def main():
    p=argparse.ArgumentParser();p.add_argument('jsonl',help='One reviewed inspection per line: truth_good, predicted_good, latency_ms');p.add_argument('--output',default='data/evaluation.json');args=p.parse_args()
    rows=[json.loads(line) for line in Path(args.jsonl).read_text().splitlines() if line.strip()]
    for row in rows:
        if type(row.get('truth_good')) is not bool or row.get('predicted_good') not in (True,False,None) or not isinstance(row.get('latency_ms'),(int,float)) or row['latency_ms']<0:raise ValueError('Invalid labeled inspection record')
    report=quality_metrics(rows);report['definition']='Positive = assembly judged visually conforming. Uncertain predictions are counted separately and reduce recall.'
    Path(args.output).parent.mkdir(parents=True,exist_ok=True);Path(args.output).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
