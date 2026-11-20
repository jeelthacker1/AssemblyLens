"""Quantize ONNX weights, then measure detection-set agreement and latency on real images."""
import argparse,json,time
from pathlib import Path
import cv2,numpy as np
from onnxruntime.quantization import quantize_dynamic,QuantType
from backend.vision import OnnxDetector

def main():
    p=argparse.ArgumentParser(); p.add_argument('model'); p.add_argument('output'); p.add_argument('images'); p.add_argument('--labels',required=True); args=p.parse_args()
    quantize_dynamic(args.model,args.output,weight_type=QuantType.QInt8)
    labels=json.loads(args.labels); original=OnnxDetector(args.model,labels); quantized=OnnxDetector(args.output,labels)
    rows=[]
    for path in Path(args.images).glob('*'):
        image=cv2.imread(str(path))
        if image is None: continue
        start=time.perf_counter(); a=original.infer(image); t1=(time.perf_counter()-start)*1000
        start=time.perf_counter(); b=quantized.infer(image); t2=(time.perf_counter()-start)*1000
        rows.append({'image':path.name,'part_set_agrees':{d['part'] for d in a}=={d['part'] for d in b},'original_ms':t1,'quantized_ms':t2})
    if not rows: raise ValueError('No validation images')
    report={'n':len(rows),'part_set_agreement':sum(r['part_set_agrees'] for r in rows)/len(rows),'original_p95_ms':float(np.percentile([r['original_ms'] for r in rows],95)),'quantized_p95_ms':float(np.percentile([r['quantized_ms'] for r in rows],95)),'limitation':'Agreement is not ground-truth accuracy. Run labeled validation before deployment.','rows':rows}
    Path(args.output+'.report.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
if __name__=='__main__': main()
