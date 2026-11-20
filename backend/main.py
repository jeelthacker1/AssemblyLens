import base64
import csv
import hashlib
import hmac
import io
import json
import os
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Depends, Header, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from .db import Session, Record, Inspection, Event, Outbox, init, now
from .domain import Workflow, Detection, initial_state, observe, finish, demo_workflow
from .vision import decode, detect, calibrate_plane, measure, reference_match, OnnxDetector

DATA=Path(os.getenv('DATA_DIR','data')); DATA.mkdir(parents=True,exist_ok=True)
# SQLite development serializes locally. PostgreSQL additionally locks each inspection row.
LOCK=threading.RLock()
KINDS={'factory','station','camera','workflow','dataset','model'}
def uid(): return str(uuid.uuid4())

class Identity(BaseModel):
    tenant: str
    user: str
    role: Literal['admin','engineer','operator','reviewer','edge','viewer']

def identity(authorization: str=Header(default='')):
    configured=json.loads(os.getenv('API_KEYS_JSON','{}'))
    if os.getenv('DEMO_MODE')=='1':
        configured.update({f'demo-{r}':{'tenant':'demo','user':f'demo-{r}','role':r} for r in ['admin','operator','reviewer','edge','viewer']})
    token=authorization.removeprefix('Bearer ')
    for key,value in configured.items():
        if authorization.startswith('Bearer ') and hmac.compare_digest(key,token): return Identity(**value)
    raise HTTPException(401,'A valid bearer API key is required')

def allow(who,*roles):
    if who.role not in roles and who.role!='admin': raise HTTPException(403,'Role not permitted')

def audit(db,who,action,body,inspection=''):
    event=Event(id=uid(),tenant=who.tenant,inspection=inspection,actor=who.user,action=action,body=body)
    db.add(event)
    if os.getenv('ENABLE_OUTBOX')=='1':
        db.add(Outbox(id=event.id,body={'id':event.id,'tenant':who.tenant,'inspection':inspection,'actor':who.user,'action':action,'body':body,'created':now().isoformat()}))
    return event

def record(db,id,who,kind=None):
    row=db.scalar(select(Record).where(Record.id==id,Record.tenant==who.tenant))
    if not row or (kind and row.kind!=kind): raise HTTPException(404,'Record not found')
    return row

def inspection(db,id,who):
    row=db.scalar(select(Inspection).where(Inspection.id==id,Inspection.tenant==who.tenant).with_for_update())
    if not row: raise HTTPException(404,'Inspection not found')
    return row

def serialize(row):
    if isinstance(row,Inspection): return {k:getattr(row,k) for k in ('id','serial','station','workflow','state','version','last_sequence','created')}
    if isinstance(row,Event): return {k:getattr(row,k) for k in ('id','inspection','actor','action','body','created')}
    return {'id':row.id,'kind':row.kind,'body':row.body,'created':row.created}

@asynccontextmanager
async def lifespan(app):
    init(); yield
    await shutdown_webrtc()

app=FastAPI(title='AssemblyLens',version='0.1.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CORS_ORIGINS','http://localhost:3010').split(','),allow_methods=['GET','POST','PUT'],allow_headers=['Authorization','Content-Type'])

@app.get('/health')
def health(): return {'status':'ok','version':'0.1.0'}
@app.get('/me')
def me(who=Depends(identity)): return who

@app.post('/bootstrap')
def bootstrap(who=Depends(identity)):
    allow(who,'engineer')
    with Session.begin() as db:
        if db.scalar(select(Record).where(Record.tenant==who.tenant,Record.kind=='workflow')): return {'message':'Already initialized'}
        factory=Record(id=uid(),tenant=who.tenant,kind='factory',body={'name':'Pilot facility'})
        station=Record(id=uid(),tenant=who.tenant,kind='station',body={'name':'Assembly station 01','factory_id':factory.id})
        workflow=Record(id=uid(),tenant=who.tenant,kind='workflow',body=demo_workflow().model_dump())
        db.add_all([factory,station,workflow]); audit(db,who,'bootstrap',{})
    return {'message':'Training kit configured'}

@app.get('/records/{kind}')
def records(kind:str,limit:int=Query(100,ge=1,le=500),who=Depends(identity)):
    if kind not in KINDS: raise HTTPException(404)
    with Session() as db:
        rows=db.scalars(select(Record).where(Record.tenant==who.tenant,Record.kind==kind).order_by(Record.created.desc()).limit(limit)).all()
        return [serialize(r) for r in rows]

class RecordInput(BaseModel): body: dict
def validate_record(db,kind,body,who):
    if kind=='workflow': return Workflow.model_validate(body).model_dump()
    if not isinstance(body.get('name'),str) or not 1<=len(body['name'])<=120: raise HTTPException(422,'name required, max 120 characters')
    if kind=='station':
        record(db,body.get('factory_id',''),who,'factory')
        if body.get('drift_baseline') is not None:
            from .drift import population_stability
            population_stability(body['drift_baseline'],body['drift_baseline'])
        for field,stage in [('active_model_id','active'),('shadow_model_id','shadow')]:
            if body.get(field):
                model=record(db,body[field],who,'model')
                if model.body.get('stage')!=stage: raise HTTPException(422,f'{field} requires a {stage} model')
    if kind=='camera':
        record(db,body.get('station_id',''),who,'station')
        if body.get('driver') not in ('browser','opencv','pylon'): raise HTTPException(422,'unsupported driver')
        if 'password' in body or '@' in str(body.get('source','')): raise HTTPException(422,'Store camera credentials on the edge gateway, not in camera URLs')
    if kind=='model': raise HTTPException(422,'Use model upload and deployment endpoints')
    return body

@app.post('/records/{kind}')
def create_record(kind:str,request:RecordInput,who=Depends(identity)):
    allow(who,'engineer')
    if kind not in KINDS: raise HTTPException(404)
    with Session.begin() as db:
        try: body=validate_record(db,kind,request.body,who)
        except ValueError as e: raise HTTPException(422,str(e))
        row=Record(id=uid(),tenant=who.tenant,kind=kind,body=body); db.add(row)
        audit(db,who,'create_'+kind,{'record_id':row.id,'body':body})
        db.flush(); return serialize(row)

@app.put('/records/{kind}/{id}')
def update_record(kind:str,id:str,request:RecordInput,who=Depends(identity)):
    allow(who,'engineer')
    with Session.begin() as db:
        row=record(db,id,who,kind)
        try: body=validate_record(db,kind,request.body,who)
        except ValueError as e: raise HTTPException(422,str(e))
        audit(db,who,'update_'+kind,{'record_id':id,'before':row.body,'after':body}); row.body=body
        return serialize(row)

class Start(BaseModel):
    serial: str=Field(min_length=1,max_length=120)
    station_id: str
    workflow_id: str
    @field_validator('serial',mode='before')
    @classmethod
    def clean_serial(cls,value): return value.strip() if isinstance(value,str) else value

@app.post('/inspections')
def start(request:Start,who=Depends(identity)):
    allow(who,'operator','engineer')
    try:
        with Session.begin() as db:
            record(db,request.station_id,who,'station'); wf=record(db,request.workflow_id,who,'workflow')
            row=Inspection(id=uid(),tenant=who.tenant,serial=request.serial,station=request.station_id,workflow=wf.body,state=initial_state())
            db.add(row); audit(db,who,'inspection_started',{'workflow_id':wf.id,'workflow_sha256':hashlib.sha256(json.dumps(wf.body,sort_keys=True).encode()).hexdigest()},row.id)
            db.flush(); return serialize(row)
    except IntegrityError: raise HTTPException(409,'Serial already exists; use rework for this serial')

@app.get('/inspections')
def list_inspections(limit:int=Query(50,ge=1,le=500),offset:int=Query(0,ge=0),who=Depends(identity)):
    with Session() as db:
        return [serialize(r) for r in db.scalars(select(Inspection).where(Inspection.tenant==who.tenant).order_by(Inspection.created.desc()).offset(offset).limit(limit))]

@app.get('/inspections/{id}')
def get_inspection(id:str,who=Depends(identity)):
    with Session() as db: return serialize(inspection(db,id,who))

def save_evidence(db,who,id,data,metadata):
    # Re-encode uploaded pixels: strip metadata; never retain arbitrary uploaded file bytes.
    import cv2
    image=decode(data); ok,encoded=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,85])
    if not ok: raise HTTPException(422,'JPEG encoding failed')
    blob=encoded.tobytes(); digest=hashlib.sha256(blob).hexdigest(); evidence_id=uid(); key=f'{who.tenant}/{id}/{evidence_id}.jpg'
    if os.getenv('S3_BUCKET'):
        import boto3
        boto3.client('s3',endpoint_url=os.getenv('S3_ENDPOINT')).put_object(Bucket=os.environ['S3_BUCKET'],Key=key,Body=blob,ContentType='image/jpeg')
    else:
        # Only generated IDs form local paths; tenant labels never become filesystem paths.
        path=DATA/'evidence'/f'{evidence_id}.jpg'; path.parent.mkdir(exist_ok=True); path.write_bytes(blob)
    db.add(Record(id=evidence_id,tenant=who.tenant,kind='evidence',body={'inspection':id,'key':key,'sha256':digest,'bytes':len(blob),**metadata}))
    return evidence_id

def apply_observation(db,row,who,detections,sequence,meta,jpeg):
    if row.state['status'] in ('approved','rejected'): raise HTTPException(409,'Inspection is closed')
    if sequence<=row.last_sequence: raise HTTPException(409,'Stale or duplicate frame sequence')
    source=meta.get('camera_id','browser')
    if row.state.get('source') not in (None,source): raise HTTPException(409,'This inspection is bound to another camera; use a separate inspection or rework')
    previous=row.state; state=observe(previous,Workflow(**row.workflow),detections)
    state['source']=source
    state['last_observation_at']=now().isoformat()
    baseline=previous.get('brightness_baseline',meta.get('brightness',0))
    state['brightness_baseline']=baseline
    state['lighting_drift']=abs(meta.get('brightness',baseline)-baseline)>35
    if state['lighting_drift']:
        state['status']='needs_review'
        f={'kind':'lighting_drift','part':'camera'}
        if f not in state['faults']: state['faults'].append(f)
    if meta.get('model_drift'):
        state['status']='needs_review'
        f={'kind':'model_distribution_drift','part':'model'}
        if f not in state['faults']: state['faults'].append(f)
    changed=state['cursor']!=previous['cursor'] or state['status']!=previous['status'] or state['faults']!=previous['faults']
    event_body={'sequence':sequence,'detections':[d.model_dump() for d in detections],**meta,'state':state}
    if changed:
        if jpeg: event_body['evidence_id']=save_evidence(db,who,row.id,jpeg,{'sequence':sequence,'model':meta.get('model')})
        audit(db,who,'observation',event_body,row.id)
        if state['status']=='needs_review':
            db.add(Record(id=uid(),tenant=who.tenant,kind='sample',body={'inspection':row.id,'priority':1-min((d.confidence for d in detections),default=0),'evidence_id':event_body.get('evidence_id'),'reason':state['last_event']}))
    row.state=state; row.last_sequence=sequence; row.version+=1
    return {**serialize(row),'observation':{**meta,'detections':event_body['detections']},'event':changed,'evidence_id':event_body.get('evidence_id')}

MODEL_CACHE={}
DRIFT_MONITORS={}
def run_station_models(db,row,who,image,result):
    import time
    started=time.perf_counter()
    station=record(db,row.station,who,'station')
    for field,stage in [('active_model_id','active'),('shadow_model_id','shadow')]:
        if not station.body.get(field): continue
        model=record(db,station.body[field],who,'model')
        if model.body['stage']!=stage: raise HTTPException(409,'Station model stage changed; update station configuration')
        cache_key=(model.id,model.body['sha256'])
        if cache_key not in MODEL_CACHE:
            if len(MODEL_CACHE)>=8: MODEL_CACHE.pop(next(iter(MODEL_CACHE)))
            MODEL_CACHE[cache_key]=OnnxDetector(DATA/'models'/f'{model.id}.onnx',model.body['labels'],os.getenv('INFERENCE_PROFILE','cpu'))
        predictions=MODEL_CACHE[cache_key].infer(image)
        if stage=='active': result['detections']=predictions; result['model']=model.body['sha256']
        else: result['shadow']={'model_sha256':model.body['sha256'],'detections':predictions,'disagrees':{d['part'] for d in predictions}!={d['part'] for d in result['detections']}}
    if station.body.get('drift_baseline') is not None:
        from .drift import DriftMonitor
        baseline=station.body['drift_baseline'];key=(who.tenant,station.id,result['model'],tuple(baseline))
        if key not in DRIFT_MONITORS:
            if len(DRIFT_MONITORS)>=128:DRIFT_MONITORS.pop(next(iter(DRIFT_MONITORS)))
            DRIFT_MONITORS[key]=DriftMonitor(baseline)
        result.update(DRIFT_MONITORS[key].update(max((d['confidence'] for d in result['detections']),default=0)))
    result['latency_ms']+=(time.perf_counter()-started)*1000
    return result

@app.post('/inspections/{id}/frame')
def frame(id:str,sequence:int=Query(ge=0),file:UploadFile=File(...),who=Depends(identity)):
    allow(who,'operator','engineer','edge')
    data=file.file.read(4_000_001)
    try: image=decode(data)
    except ValueError as e: raise HTTPException(422,str(e))
    with LOCK,Session.begin() as db:
        row=inspection(db,id,who); result=run_station_models(db,row,who,image,detect(image,Workflow(**row.workflow)))
        return apply_observation(db,row,who,[Detection(**d) for d in result.pop('detections')],sequence,result,data)

class EdgeObservation(BaseModel):
    sequence:int=Field(ge=0)
    camera_id:str
    detections:list[Detection]=Field(max_length=200)
    brightness:float=Field(ge=0,le=255)
    latency_ms:float=Field(ge=0)
    model:str=Field(max_length=100)
    model_drift:bool=False
    drift_score:float|None=Field(default=None,ge=0)
    jpeg_base64:str|None=Field(default=None,max_length=5_400_000)

@app.post('/inspections/{id}/observations')
def edge_observation(id:str,request:EdgeObservation,who=Depends(identity)):
    allow(who,'edge')
    with LOCK,Session.begin() as db:
        row=inspection(db,id,who); camera=record(db,request.camera_id,who,'camera')
        if camera.body.get('station_id')!=row.station: raise HTTPException(409,'Camera belongs to another station')
        try: jpeg=base64.b64decode(request.jpeg_base64,validate=True) if request.jpeg_base64 else None
        except ValueError: raise HTTPException(422,'Invalid base64')
        return apply_observation(db,row,who,request.detections,request.sequence,request.model_dump(exclude={'detections','jpeg_base64','sequence'}),jpeg)

@app.post('/inspections/{id}/finish')
def finish_inspection(id:str,who=Depends(identity)):
    allow(who,'operator','engineer')
    with LOCK,Session.begin() as db:
        row=inspection(db,id,who)
        if row.state['status'] in ('approved','rejected'): raise HTTPException(409,'Inspection closed')
        row.state=finish(row.state,Workflow(**row.workflow)); row.version+=1
        audit(db,who,'finish',{'state':row.state},id); return serialize(row)

class Decision(BaseModel):
    action:Literal['approve','reject','rework','override']
    reason:str=Field(min_length=5,max_length=2000)
    expected_version:int=Field(ge=0)
    @field_validator('reason',mode='before')
    @classmethod
    def clean_reason(cls,value): return value.strip() if isinstance(value,str) else value

@app.post('/inspections/{id}/decision')
def decision(id:str,request:Decision,who=Depends(identity)):
    allow(who,'reviewer')
    with LOCK,Session.begin() as db:
        row=inspection(db,id,who)
        if row.version!=request.expected_version: raise HTTPException(409,'Inspection changed; reload before reviewing')
        if request.action=='override': allow(who) # only admin
        if row.state['status'] in ('approved','rejected') and request.action!='rework': raise HTTPException(409,'Closed inspection; start rework first')
        wf=Workflow(**row.workflow)
        if request.action=='approve' and (row.state['status']!='awaiting_approval' or row.state['faults'] or any(row.state['counts'].get(s.part,0)<wf.stable_frames for s in wf.steps)):
            raise HTTPException(409,'Approval requires all steps currently verified and no faults; administrator override requires a reason')
        before=row.state
        if request.action=='rework': row.state=initial_state()
        else: row.state={**row.state,'status':'approved' if request.action in ('approve','override') else 'rejected','human_verified':True,'overridden':request.action=='override'}
        row.version+=1; audit(db,who,request.action,{'reason':request.reason,'before':before,'after':row.state},id)
        return serialize(row)

@app.get('/events')
def events(inspection_id:str|None=None,limit:int=Query(100,ge=1,le=1000),who=Depends(identity)):
    with Session() as db:
        query=select(Event).where(Event.tenant==who.tenant)
        if inspection_id: query=query.where(Event.inspection==inspection_id)
        return [serialize(e) for e in db.scalars(query.order_by(Event.created.desc()).limit(limit))]

@app.get('/evidence/{id}')
def evidence(id:str,who=Depends(identity)):
    with Session() as db:
        row=record(db,id,who,'evidence')
        if os.getenv('S3_BUCKET'):
            import boto3
            from botocore.exceptions import ClientError
            try: blob=boto3.client('s3',endpoint_url=os.getenv('S3_ENDPOINT')).get_object(Bucket=os.environ['S3_BUCKET'],Key=row.body['key'])['Body'].read()
            except ClientError as exc:
                if exc.response['Error']['Code'] in ('NoSuchKey','404'): raise HTTPException(410,'Evidence expired')
                raise
        else:
            path=DATA/'evidence'/f'{row.id}.jpg'
            if not path.exists(): raise HTTPException(410,'Evidence expired')
            blob=path.read_bytes()
        return Response(blob,media_type='image/jpeg',headers={'Cache-Control':'private, no-store'})

@app.get('/analytics')
def analytics(who=Depends(identity)):
    with Session() as db:
        total=db.scalar(select(func.count()).select_from(Inspection).where(Inspection.tenant==who.tenant))
        rows=db.scalars(select(Inspection).where(Inspection.tenant==who.tenant).order_by(Inspection.created.desc()).limit(1000)).all()
        counts={}; faults={}
        for r in rows:
            status=r.state['status']; counts[status]=counts.get(status,0)+1
            for f in r.state['faults']: faults[f['kind']]=faults.get(f['kind'],0)+1
        return {'total':total,'window':len(rows),'statuses':counts,'failures':faults,'scope':'Latest 1000 inspections; operational summary, not measured model accuracy'}

@app.get('/export.csv')
def export(who=Depends(identity)):
    allow(who,'reviewer','engineer')
    output=io.StringIO(); writer=csv.writer(output); writer.writerow(['id','serial','station','status','created'])
    with Session() as db:
        for r in db.scalars(select(Inspection).where(Inspection.tenant==who.tenant).order_by(Inspection.created.desc()).limit(10000)):
            serial="'"+r.serial if r.serial.startswith(('=','+','-','@','\t','\r','\n')) else r.serial
            writer.writerow([r.id,serial,r.station,r.state['status'],r.created.isoformat()])
    return Response(output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=assemblylens-inspections.csv'})

@app.get('/learning/queue')
def learning(who=Depends(identity)):
    allow(who,'engineer','reviewer')
    with Session() as db:
        rows=db.scalars(select(Record).where(Record.tenant==who.tenant,Record.kind=='sample').order_by(Record.created.desc()).limit(500)).all()
        return sorted([serialize(r) for r in rows],key=lambda r:r['body']['priority'],reverse=True)

class Heartbeat(BaseModel):
    connected:bool
    fps:float=Field(ge=0,le=1000)
    dropped:int=Field(ge=0)
    profile:Literal['cpu','gpu']='cpu'

@app.post('/cameras/{id}/heartbeat')
def heartbeat(id:str,request:Heartbeat,who=Depends(identity)):
    allow(who,'edge','engineer')
    with Session.begin() as db:
        row=record(db,id,who,'camera'); row.body={**row.body,'health':{**request.model_dump(),'at':now().isoformat()}}
    return {'ok':True}

class Calibration(BaseModel):
    points:list[tuple[float,float]]=Field(min_length=4,max_length=4)
    width_mm:float=Field(gt=0)
    height_mm:float=Field(gt=0)
@app.post('/cameras/{id}/calibration')
def calibration(id:str,request:Calibration,who=Depends(identity)):
    allow(who,'engineer')
    try: cal=calibrate_plane(request.points,request.width_mm,request.height_mm)
    except ValueError as e: raise HTTPException(422,str(e))
    with Session.begin() as db:
        row=record(db,id,who,'camera'); row.body={**row.body,'calibration':cal}; audit(db,who,'calibration',{'camera':id,'calibration':cal})
    return cal
class Measure(BaseModel): points:list[tuple[float,float]]=Field(min_length=2,max_length=2)
@app.post('/cameras/{id}/measure')
def measurement(id:str,request:Measure,who=Depends(identity)):
    with Session() as db:
        cal=record(db,id,who,'camera').body.get('calibration')
        if not cal: raise HTTPException(409,'Camera not calibrated')
        return {'distance_mm':measure(request.points,cal),'restriction':cal['restriction']}

@app.post('/vision/compare')
def compare(file:UploadFile=File(...),reference:UploadFile=File(...),who=Depends(identity)):
    allow(who,'engineer','operator')
    try: return reference_match(decode(file.file.read(4_000_001)),decode(reference.file.read(4_000_001)))
    except ValueError as e: raise HTTPException(422,str(e))

@app.post('/datasets/import-cvat')
def import_cvat(name:str,file:UploadFile=File(...),who=Depends(identity)):
    allow(who,'engineer')
    from .training import parse_cvat
    data=file.file.read(20_000_001)
    if len(data)>20_000_000: raise HTTPException(413)
    try: annotations=parse_cvat(data)
    except Exception as e: raise HTTPException(422,f'Invalid CVAT image XML: {type(e).__name__}')
    with Session.begin() as db:
        row=Record(id=uid(),tenant=who.tenant,kind='dataset',body={'name':name,'sha256':hashlib.sha256(data).hexdigest(),'images':annotations,'version':uid()})
        db.add(row); audit(db,who,'dataset_import',{'id':row.id,'images':len(annotations)}); db.flush(); return serialize(row)

@app.post('/models/upload')
def upload_model(name:str,labels:str,file:UploadFile=File(...),who=Depends(identity)):
    allow(who,'engineer'); data=file.file.read(100_000_001)
    if len(data)>100_000_000: raise HTTPException(413)
    try:
        label_list=json.loads(labels)
        if not isinstance(label_list,list) or not label_list or not all(isinstance(v,str) for v in label_list): raise ValueError()
    except ValueError: raise HTTPException(422,'labels must be a JSON string array')
    model_id=uid(); folder=DATA/'models'; folder.mkdir(exist_ok=True); path=folder/f'{model_id}.onnx'; path.write_bytes(data)
    try:
        detector=OnnxDetector(path,label_list)
        import numpy as np
        detector.infer(np.zeros((640,640,3),np.uint8))
    except Exception as e:
        path.unlink(missing_ok=True); raise HTTPException(422,f'Unsupported ONNX contract: {type(e).__name__}')
    with Session.begin() as db:
        row=Record(id=model_id,tenant=who.tenant,kind='model',body={'name':name,'labels':label_list,'sha256':detector.sha,'stage':'registered'})
        db.add(row); audit(db,who,'model_registered',{'id':model_id,'sha256':detector.sha}); db.flush(); return serialize(row)

class Deployment(BaseModel):
    stage:Literal['shadow','active','retired']
    reason:str=Field(min_length=5)
    validation:dict
    @field_validator('reason',mode='before')
    @classmethod
    def clean_reason(cls,value): return value.strip() if isinstance(value,str) else value
@app.post('/models/{id}/deployment')
def deployment(id:str,request:Deployment,who=Depends(identity)):
    allow(who,'engineer')
    if request.stage=='active' and not all(k in request.validation for k in ('precision','recall','false_acceptance_rate','false_rejection_rate','dataset_sha256')):
        raise HTTPException(422,'Active deployment requires a recorded validation report')
    if request.stage=='active':
        import math
        for key in ('precision','recall','false_acceptance_rate','false_rejection_rate'):
            value=request.validation[key]
            if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or not 0<=value<=1: raise HTTPException(422,'Validation rates must be finite values in [0,1]')
    with Session.begin() as db:
        row=record(db,id,who,'model'); row.body={**row.body,**request.model_dump()}; audit(db,who,'model_deployment',{'id':id,**request.model_dump()})
        return serialize(row)

@app.get('/models/{id}/artifact')
def model_artifact(id:str,who=Depends(identity)):
    allow(who,'engineer','edge')
    with Session() as db:
        row=record(db,id,who,'model'); path=DATA/'models'/f'{row.id}.onnx'
        if not path.exists(): raise HTTPException(404,'Artifact not available on this server')
        return Response(path.read_bytes(),media_type='application/octet-stream',headers={'X-SHA256':row.body['sha256']})

from .rtc import install
shutdown_webrtc=install(app,identity)
