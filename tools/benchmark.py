"""Reproducible measurement. Synthetic fixture benchmarks are not factory validation."""
import argparse,concurrent.futures,json,os,platform,time,uuid
from pathlib import Path
import cv2,numpy as np,httpx
from backend.domain import demo_workflow
from backend.vision import detect

def fixture():
    image=np.full((480,800,3),220,np.uint8)
    for x,color in [(80,(0,0,230)),(320,(0,180,0)),(580,(230,0,0))]:cv2.rectangle(image,(x,150),(x+100,300),color,-1)
    return image

def main():
    p=argparse.ArgumentParser();p.add_argument('--images');p.add_argument('--synthetic',action='store_true');p.add_argument('--iterations',type=int,default=200);p.add_argument('--api');p.add_argument('--concurrency',type=int,default=10);p.add_argument('--output',default='docs/benchmark-results.json');args=p.parse_args()
    if not args.images and not args.synthetic:p.error('Specify --images with photographed examples or explicitly --synthetic')
    images=[fixture()] if args.synthetic else [im for path in Path(args.images).glob('*') if (im:=cv2.imread(str(path))) is not None]
    if not images:raise ValueError('No readable images')
    wf=demo_workflow();times=[];errors=[]
    for _ in range(10):detect(images[0],wf)
    started=time.perf_counter()
    if not args.api:
        for i in range(args.iterations):
            start=time.perf_counter();detect(images[i%len(images)],wf);times.append((time.perf_counter()-start)*1000)
    else:
        key=os.environ['ASSEMBLYLENS_API_KEY'];headers={'Authorization':'Bearer '+key}
        with httpx.Client(base_url=args.api,headers=headers,timeout=60) as c:
            c.post('/bootstrap').raise_for_status();station=c.get('/records/station').json()[0]['id'];workflow=c.get('/records/workflow').json()[0]['id']
        def worker(index):
            durations=[]
            with httpx.Client(base_url=args.api,headers=headers,timeout=120) as c:
                r=c.post('/inspections',json={'serial':f'BENCH-{uuid.uuid4()}','station_id':station,'workflow_id':workflow});r.raise_for_status();id=r.json()['id']
                for sequence in range(args.iterations):
                    data=cv2.imencode('.jpg',images[sequence%len(images)])[1].tobytes();start=time.perf_counter()
                    response=c.post(f'/inspections/{id}/frame?sequence={sequence}',files={'file':('benchmark.jpg',data,'image/jpeg')})
                    response.raise_for_status();durations.append((time.perf_counter()-start)*1000)
            return durations
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures=[pool.submit(worker,i) for i in range(args.concurrency)]
            for future in concurrent.futures.as_completed(futures):
                try:times.extend(future.result())
                except Exception as exc:errors.append(type(exc).__name__)
    elapsed=time.perf_counter()-started
    report={'date_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'python':platform.python_version(),'platform':platform.platform(),'processor':platform.processor(),'opencv':cv2.__version__,'input':'synthetic colored rectangles; NOT photographed validation' if args.synthetic else str(args.images),'mode':'HTTP camera frame ingestion' if args.api else 'in-process OpenCV segmentation + QR/barcode','frames':len(times),'concurrency':args.concurrency if args.api else 1,'elapsed_seconds':elapsed,'throughput_fps':len(times)/elapsed,'p50_ms':float(np.percentile(times,50)) if times else None,'p95_ms':float(np.percentile(times,95)) if times else None,'p99_ms':float(np.percentile(times,99)) if times else None,'errors':errors,'jpeg_bytes_example':len(cv2.imencode('.jpg',images[0],[cv2.IMWRITE_JPEG_QUALITY,85])[1]),'production_accuracy':'not measured','notes':'No claim of 100-camera real-time capacity. Includes synthetic pixels only if explicitly selected.'}
    Path(args.output).parent.mkdir(parents=True,exist_ok=True);Path(args.output).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
