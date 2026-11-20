"""Real image processing; the color-kit algorithm is deliberately narrow in scope."""
import hashlib
import time
from pathlib import Path
import cv2
import numpy as np
from .domain import Detection, Workflow

MAX_PIXELS=1920*1080

def decode(data: bytes):
    if len(data)>4_000_000: raise ValueError('image exceeds 4 MB')
    import io
    from PIL import Image,UnidentifiedImageError
    try:
        with Image.open(io.BytesIO(data)) as header:
            if header.width*header.height>MAX_PIXELS: raise ValueError('maximum image resolution is 1920x1080')
    except (UnidentifiedImageError,Image.DecompressionBombError) as exc: raise ValueError('invalid or oversized image') from exc
    image=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR)
    if image is None: raise ValueError('invalid image')
    if image.shape[0]*image.shape[1]>MAX_PIXELS: raise ValueError('maximum image resolution is 1920x1080')
    return image

def detect(image, workflow: Workflow):
    start=time.perf_counter(); h,w=image.shape[:2]
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV); detections=[]
    for part in workflow.parts:
        mask=cv2.inRange(hsv,np.array(part.hsv_low),np.array(part.hsv_high))
        mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
        contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area=cv2.contourArea(contour)
            if area<h*w*part.min_area: continue
            x,y,bw,bh=cv2.boundingRect(contour)
            (_, _),(rw,rh),angle=cv2.minAreaRect(contour)
            if rw<rh: angle+=90
            polygon=cv2.approxPolyDP(contour,.01*cv2.arcLength(contour,True),True).reshape(-1,2)
            # Geometric mask purity is a heuristic, NOT a calibrated probability.
            confidence=min(.99,float(area/max(rw*rh,1)))
            directed_angle=angle%180 if max(rw,rh)/max(min(rw,rh),1)>=1.15 else None
            detections.append(Detection(part=part.id,confidence=confidence,bbox=(x/w,y/h,bw/w,bh/h),angle=directed_angle,polygon=[[float(px/w),float(py/h)] for px,py in polygon]))
    codes=[]
    try:
        ok,values,_,_=cv2.QRCodeDetector().detectAndDecodeMulti(image)
        if ok: codes=[v for v in values if v]
    except cv2.error: pass
    try:
        values,_,_=cv2.barcode_BarcodeDetector().detectAndDecode(image)
        codes.extend(v for v in values if v and v not in codes)
    except (cv2.error,AttributeError): pass
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    return {'detections':[d.model_dump() for d in detections], 'codes':codes,
            'brightness':float(gray.mean()),'sharpness':float(cv2.Laplacian(gray,cv2.CV_64F).var()),
            'latency_ms':(time.perf_counter()-start)*1000,'model':'hsv-kit-v1'}

class Tracker:
    """Nearest-centroid association with expiration; per camera, never globally shared."""
    def __init__(self): self.tracks={}; self.next_id=1
    def update(self,detections):
        updated={}; used=set()
        for d in detections:
            x,y,w,h=d['bbox']; center=np.array([x+w/2,y+h/2])
            options=[(float(np.linalg.norm(center-v[1])),k) for k,v in self.tracks.items() if v[0]==d['part'] and k not in used]
            distance,k=min(options,default=(1,''))
            if distance>.15: k=str(self.next_id); self.next_id+=1
            used.add(k); updated[k]=(d['part'],center); d['track_id']=k
        self.tracks=updated
        return detections

def reference_match(image, reference):
    orb=cv2.ORB_create(nfeatures=1500)
    k1,d1=orb.detectAndCompute(reference,None); k2,d2=orb.detectAndCompute(image,None)
    if d1 is None or d2 is None: return {'matched':False,'inliers':0,'reason':'insufficient_texture'}
    pairs=cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(d1,d2,k=2)
    good=[pair[0] for pair in pairs if len(pair)==2 and pair[0].distance<.75*pair[1].distance]
    if len(good)<8: return {'matched':False,'inliers':0,'reason':'insufficient_matches'}
    src=np.float32([k1[m.queryIdx].pt for m in good]); dst=np.float32([k2[m.trainIdx].pt for m in good])
    matrix,mask=cv2.findHomography(src,dst,cv2.RANSAC,3.0)
    count=int(mask.sum()) if mask is not None else 0
    return {'matched':count>=8 and count/len(good)>=.6,'inliers':count,'homography':matrix.tolist() if matrix is not None else None}

def calibrate_plane(points, width_mm, height_mm):
    points=np.array(points,dtype=np.float32)
    if points.shape!=(4,2) or abs(cv2.contourArea(points))<100: raise ValueError('four nondegenerate corners required, TL TR BR BL')
    if width_mm<=0 or height_mm<=0: raise ValueError('physical dimensions must be positive')
    matrix=cv2.getPerspectiveTransform(points,np.float32([[0,0],[width_mm,0],[width_mm,height_mm],[0,height_mm]]))
    return {'homography':matrix.tolist(),'width_mm':width_mm,'height_mm':height_mm,'restriction':'Only the calibrated plane; independent accuracy validation required.'}

def measure(points, calibration):
    mapped=cv2.perspectiveTransform(np.array([points],np.float32),np.array(calibration['homography'],np.float64))[0]
    return float(np.linalg.norm(mapped[1]-mapped[0]))

class OnnxDetector:
    """Contract: input RGB NCHW float32 0..1; output [1,N,6] xyxy pixels, score, class.
    Model MUST include NMS; arbitrary YOLO exports are not implicitly compatible.
    """
    def __init__(self,path,labels,profile='cpu'):
        import onnxruntime as ort
        providers=['CPUExecutionProvider']
        if profile=='gpu':
            if 'CUDAExecutionProvider' not in ort.get_available_providers(): raise ValueError('CUDA provider unavailable')
            providers=['CUDAExecutionProvider','CPUExecutionProvider']
        self.session=ort.InferenceSession(str(path),providers=providers)
        self.labels=labels; self.sha=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    def infer(self,image):
        inp=self.session.get_inputs()[0]; size=inp.shape[-1]
        if not isinstance(size,int): raise ValueError('fixed square input size required')
        tensor=cv2.cvtColor(cv2.resize(image,(size,size)),cv2.COLOR_BGR2RGB).transpose(2,0,1)[None].astype(np.float32)/255
        output=self.session.run(None,{inp.name:tensor})[0]
        if output.ndim!=3 or output.shape[-1]!=6: raise ValueError('expected [1,N,6] decoded output')
        results=[]
        for x1,y1,x2,y2,score,cls in output[0]:
            if score<.25: continue
            if not np.isfinite([x1,y1,x2,y2,score,cls]).all() or cls!=int(cls) or not 0<=int(cls)<len(self.labels) or not 0<=x1<x2<=size or not 0<=y1<y2<=size:
                raise ValueError('invalid decoded box/class from model')
            results.append(Detection(part=self.labels[int(cls)],confidence=float(score),bbox=(float(x1/size),float(y1/size),float((x2-x1)/size),float((y2-y1)/size))).model_dump())
        return results
