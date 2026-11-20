"""Pure assembly state machine. Persistent presence is not a repeated action."""
import copy
from pydantic import BaseModel, Field, model_validator

class Part(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    hsv_low: tuple[int,int,int] = (0,100,70)
    hsv_high: tuple[int,int,int] = (10,255,255)
    min_area: float = Field(default=.003, gt=0, lt=1)

class Step(BaseModel):
    id: str
    part: str
    instruction: str
    zone: tuple[float,float,float,float] = (0,0,1,1)
    angle: float | None = None
    tolerance: float = Field(default=20, ge=0, le=90)
    min_confidence: float = Field(default=.75, ge=0, le=1)
    @model_validator(mode='after')
    def valid_zone(self):
        x,y,w,h=self.zone
        if min(x,y)<0 or min(w,h)<=0 or x+w>1.00001 or y+h>1.00001:
            raise ValueError('zone must fit normalized image coordinates')
        return self

class Workflow(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    variant: str = 'Standard'
    parts: list[Part] = Field(min_length=1,max_length=100)
    steps: list[Step] = Field(min_length=1,max_length=100)
    stable_frames: int = Field(default=3,ge=1,le=30)
    @model_validator(mode='after')
    def unique(self):
        parts=[p.id for p in self.parts]
        if len(set(parts))!=len(parts) or len({s.id for s in self.steps})!=len(self.steps):
            raise ValueError('part and step IDs must be unique')
        if any(s.part not in parts for s in self.steps):
            raise ValueError('each step must reference a BOM part')
        if len({s.part for s in self.steps})!=len(self.steps):
            raise ValueError('v1 requires one distinct part per step')
        for p in self.parts:
            if any(a<0 or b>limit or a>b for a,b,limit in zip(p.hsv_low,p.hsv_high,(179,255,255))):
                raise ValueError('invalid OpenCV HSV range')
        return self

class Detection(BaseModel):
    part: str
    confidence: float = Field(ge=0,le=1)
    bbox: tuple[float,float,float,float]
    angle: float | None = None
    track_id: str = ''
    polygon: list[list[float]] = Field(default_factory=list)

def initial_state():
    return dict(cursor=0,status='in_progress',counts={},completed=[],absent={},faults=[],last_event='waiting',frames=0)

def observe(state: dict, workflow: Workflow, detections: list[Detection]):
    s=copy.deepcopy(state)
    if s['status'] in ('approved','rejected'): return s
    s['frames']+=1
    by={}
    for d in detections:
        if d.part not in by or d.confidence>by[d.part].confidence: by[d.part]=d
    events=[]
    cursor_at_start=s['cursor']
    def fault(kind, part):
        item={'kind':kind,'part':part}
        if item not in s['faults']: s['faults'].append(item)
        events.append(kind)
    for i,step in enumerate(workflow.steps):
        d=by.get(step.part); valid=False
        if d:
            x,y,w,h=step.zone; bx,byy,bw,bh=d.bbox
            delta=abs((d.angle-(step.angle or 0)+90)%180-90) if d.angle is not None else 180
            valid=d.confidence>=step.min_confidence and bx>=x and byy>=y and bx+bw<=x+w+.001 and byy+bh<=y+h+.001 and (step.angle is None or delta<=step.tolerance)
            if not valid: events.append('uncertain' if d.confidence<step.min_confidence or (step.angle is not None and d.angle is None) else 'placement_or_orientation')
        s['counts'][step.part]=s['counts'].get(step.part,0)+1 if valid else 0
        if step.part in s['completed']:
            if not valid: s['absent'][step.part]=s['absent'].get(step.part,0)+1
            elif s['absent'].get(step.part,0)>=workflow.stable_frames:
                fault('repeated_step',step.part); s['absent'][step.part]=0
            else: s['absent'][step.part]=0
            if s['absent'].get(step.part,0)>=workflow.stable_frames: fault('missing_component',step.part)
        elif s['counts'][step.part]>=workflow.stable_frames:
            if i>cursor_at_start: fault('incorrect_order',step.part)
            elif i==cursor_at_start:
                s['completed'].append(step.part); s['cursor']+=1; events.append('step_completed')
    for d in detections:
        if d.part not in {p.id for p in workflow.parts}: fault('incorrect_part',d.part)
    s['last_event']=events[-1] if events else 'waiting'
    if s['faults'] or any(e in ('uncertain','placement_or_orientation') for e in events): s['status']='needs_review'
    elif s['cursor']==len(workflow.steps): s['status']='awaiting_approval'
    else: s['status']='in_progress'
    return s

def finish(state, workflow):
    s=copy.deepcopy(state)
    for step in workflow.steps[s['cursor']:]:
        f={'kind':'omitted_step','part':step.part}
        if f not in s['faults']: s['faults'].append(f)
    s['status']='needs_review' if s['faults'] else 'awaiting_approval'
    return s

def demo_workflow():
    return Workflow(name='Three-part training fixture',variant='Color kit A',parts=[
        Part(id='base',name='Red base',hsv_low=(0,110,70),hsv_high=(12,255,255)),
        Part(id='bracket',name='Green bracket',hsv_low=(35,80,50),hsv_high=(90,255,255)),
        Part(id='cap',name='Blue cap',hsv_low=(95,100,50),hsv_high=(135,255,255))],steps=[
        Step(id='s1',part='base',instruction='Place the red base inside the left zone.',zone=(.05,.2,.27,.6)),
        Step(id='s2',part='bracket',instruction='Fit the green bracket in the center zone.',zone=(.36,.2,.27,.6)),
        Step(id='s3',part='cap',instruction='Install the blue cap in the right zone.',zone=(.68,.2,.27,.6))])
