"""One process per camera. Real capture, latest-frame buffer, reconnect, local inference."""
import argparse
import base64
from collections import deque
import json
import os
from pathlib import Path
import queue
import threading
import time
import cv2
import httpx
from backend.domain import Workflow, Detection, observe
from backend.vision import detect, Tracker, OnnxDetector

class Capture:
    def __init__(self,source,driver='opencv'):
        self.source=source; self.driver=driver; self.frames=queue.Queue(maxsize=1)
        self.stop=threading.Event(); self.connected=False; self.dropped=0
        self.thread=threading.Thread(target=self.run,daemon=True); self.thread.start()
    def run(self):
        delay=1
        while not self.stop.is_set():
            cap=None
            try:
                if self.driver=='pylon':
                    from pypylon import pylon
                    devices=pylon.TlFactory.GetInstance().EnumerateDevices()
                    device=next(d for d in devices if d.GetSerialNumber()==str(self.source))
                    cap=pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(device)); cap.Open(); cap.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
                    converter=pylon.ImageFormatConverter(); converter.OutputPixelFormat=pylon.PixelType_BGR8packed
                else:
                    source=int(self.source) if str(self.source).isdigit() else self.source
                    cap=cv2.VideoCapture(source,cv2.CAP_FFMPEG,[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,5000,cv2.CAP_PROP_READ_TIMEOUT_MSEC,5000]) if isinstance(source,str) and source.startswith(('rtsp://','rtsps://','http://','https://')) else cv2.VideoCapture(source,cv2.CAP_ANY)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE,1)
                    if not cap.isOpened(): raise RuntimeError('camera unavailable')
                while not self.stop.is_set():
                    if self.driver=='pylon':
                        result=cap.RetrieveResult(5000,pylon.TimeoutHandling_ThrowException)
                        try: image=converter.Convert(result).GetArray().copy() if result.GrabSucceeded() else None
                        finally: result.Release()
                        ok=image is not None
                    else: ok,image=cap.read()
                    if not ok: raise RuntimeError('capture disconnected')
                    self.connected=True; delay=1
                    scale=min(1,1280/image.shape[1],1080/image.shape[0])
                    if scale<1: image=cv2.resize(image,(round(image.shape[1]*scale),round(image.shape[0]*scale)))
                    if self.frames.full():
                        try: self.frames.get_nowait(); self.dropped+=1
                        except queue.Empty: pass
                    self.frames.put_nowait((time.monotonic(),image))
            except Exception as exc:
                self.connected=False
                # Never log source URLs: they may contain credentials.
                print(json.dumps({'event':'camera_reconnecting','error_type':type(exc).__name__,'delay':delay}),flush=True)
            finally:
                if cap is not None:
                    try: cap.Close() if self.driver=='pylon' else cap.release()
                    except Exception: pass
            self.stop.wait(delay); delay=min(30,delay*2)
    def close(self): self.stop.set(); self.thread.join(timeout=6)

def discover(count=5):
    found=[]
    for index in range(count):
        cap=cv2.VideoCapture(index)
        if cap.isOpened(): found.append({'driver':'opencv','source':str(index),'width':cap.get(3),'height':cap.get(4)})
        cap.release()
    try:
        from pypylon import pylon
        found.extend({'driver':'pylon','source':d.GetSerialNumber(),'name':d.GetFriendlyName()} for d in pylon.TlFactory.GetInstance().EnumerateDevices())
    except ImportError: pass
    return found

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--discover',action='store_true'); parser.add_argument('--source',default=os.getenv('CAMERA_SOURCE','0'))
    parser.add_argument('--driver',choices=['opencv','pylon'],default='opencv')
    parser.add_argument('--api',default='http://localhost:8010'); parser.add_argument('--camera'); parser.add_argument('--inspection')
    parser.add_argument('--fps',type=float,default=4); parser.add_argument('--model'); parser.add_argument('--shadow-model'); parser.add_argument('--labels',default='[]')
    parser.add_argument('--profile',choices=['cpu','gpu'],default='cpu'); parser.add_argument('--clips',action='store_true')
    parser.add_argument('--drift-baseline',help='JSON from tools.drift_baseline; optional representative station baseline')
    args=parser.parse_args()
    if args.discover: print(json.dumps(discover(),indent=2)); return
    if not args.camera or not args.inspection or not os.getenv('ASSEMBLYLENS_API_KEY'): parser.error('--camera, --inspection and ASSEMBLYLENS_API_KEY are required')
    client=httpx.Client(base_url=args.api,headers={'Authorization':'Bearer '+os.environ['ASSEMBLYLENS_API_KEY']},timeout=15)
    response=client.get('/inspections/'+args.inspection); response.raise_for_status(); inspection=response.json()
    wf=Workflow(**inspection['workflow']); tracker=Tracker(); cap=Capture(args.source,args.driver)
    model=OnnxDetector(args.model,json.loads(args.labels),args.profile) if args.model else None
    shadow=OnnxDetector(args.shadow_model,json.loads(args.labels),args.profile) if args.shadow_model else None
    from backend.drift import DriftMonitor
    monitor=DriftMonitor(json.loads(Path(args.drift_baseline).read_text())['drift_baseline']) if args.drift_baseline else None
    clips=deque(maxlen=round(max(1,min(args.fps,30))*5)); last_heartbeat=0
    try:
        while True:
            start=time.monotonic()
            if start-last_heartbeat>5:
                try:
                    client.post(f'/cameras/{args.camera}/heartbeat',json={'connected':cap.connected,'fps':min(30,args.fps),'dropped':cap.dropped,'profile':args.profile}).raise_for_status()
                except httpx.HTTPError: print('{"event":"heartbeat_failed"}',flush=True)
                last_heartbeat=start
            try: captured,image=cap.frames.get(timeout=1)
            except queue.Empty: continue
            if time.monotonic()-captured>2: continue
            result=detect(image,wf)
            if model: result['detections']=model.infer(image); result['model']=model.sha
            tracker.update(result['detections'])
            drift=monitor.update(max((d['confidence'] for d in result['detections']),default=0)) if monitor else {'model_drift':False,'drift_score':None}
            if shadow:
                alternate=shadow.infer(image)
                print(json.dumps({'event':'shadow_comparison','model_sha256':shadow.sha,'disagrees':{d['part'] for d in alternate}!={d['part'] for d in result['detections']}}),flush=True)
            _,jpg=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,75]); jpeg=jpg.tobytes()
            if args.clips: clips.append(jpeg)
            predicted=observe(inspection['state'],wf,[Detection(**d) for d in result['detections']])
            changed=any(predicted[k]!=inspection['state'][k] for k in ('cursor','status','faults'))
            changed=changed or (drift['model_drift'] and not any(f['kind']=='model_distribution_drift' for f in inspection['state']['faults'])) or (abs(result['brightness']-inspection['state'].get('brightness_baseline',result['brightness']))>35 and not inspection['state'].get('lighting_drift'))
            payload={'sequence':inspection['last_sequence']+1,'camera_id':args.camera,'detections':result['detections'],'brightness':result['brightness'],'latency_ms':(time.monotonic()-start)*1000,'model':result['model'],'jpeg_base64':base64.b64encode(jpeg).decode() if changed else None}
            payload.update({k:drift[k] for k in ('model_drift','drift_score')})
            try:
                response=client.post(f'/inspections/{args.inspection}/observations',json=payload)
                if response.status_code==409:
                    latest=client.get('/inspections/'+args.inspection); latest.raise_for_status(); inspection=latest.json()
                    if inspection['state']['status'] in ('approved','rejected'): break
                    continue
                response.raise_for_status(); inspection=response.json()
                if changed:
                    print(json.dumps({'event':'inspection_change','state':inspection['state'],'latency_ms':payload['latency_ms']}),flush=True)
                    if args.clips and clips:
                        folder=Path('data/clips'); folder.mkdir(parents=True,exist_ok=True)
                        path=folder/f'{args.inspection}-{inspection["last_sequence"]}.mp4'
                        writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),max(1,min(args.fps,30)),(image.shape[1],image.shape[0]))
                        for frame in clips:
                            import numpy as np
                            writer.write(cv2.imdecode(np.frombuffer(frame,np.uint8),cv2.IMREAD_COLOR))
                        writer.release()
                        # Enforce a local bounded retention count; central evidence holds event JPEGs.
                        for old in sorted(folder.glob('*.mp4'),key=lambda p:p.stat().st_mtime)[:-100]: old.unlink()
            except httpx.HTTPError:
                print('{"event":"api_unavailable_no_auto_accept"}',flush=True); time.sleep(1)
            elapsed=time.monotonic()-start
            # Adaptive sampling: one request in flight, no unbounded inference backlog.
            time.sleep(max(0,1/max(.2,min(args.fps,30))-elapsed))
    except KeyboardInterrupt: pass
    finally: cap.close(); client.close()

if __name__=='__main__': main()
