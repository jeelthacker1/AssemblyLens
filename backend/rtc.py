"""Optional authenticated WebRTC video ingestion. No audio, no prerecorded detections."""
import asyncio,json,time
from fastapi import Depends,HTTPException
from pydantic import BaseModel,Field

class Offer(BaseModel):
    inspection_id:str
    sdp:str=Field(max_length=100000)
    type:str='offer'

def install(app,identity):
    peers={}
    @app.post('/webrtc/offer')
    async def offer(request:Offer,who=Depends(identity)):
        from .main import allow,inspection,Session
        allow(who,'operator','engineer')
        if request.type!='offer': raise HTTPException(422,'Expected an SDP offer')
        if len(peers)>=16 or sum(v==who.tenant for v in peers.values())>=4: raise HTTPException(429,'WebRTC peer capacity reached; use an edge gateway')
        with Session() as db: inspection(db,request.inspection_id,who)
        try:
            from aiortc import RTCPeerConnection,RTCSessionDescription,RTCConfiguration
        except ImportError: raise HTTPException(503,'Install requirements-webrtc.txt and restart the API to enable WebRTC')
        pc=RTCPeerConnection(RTCConfiguration(iceServers=[]));peers[pc]=who.tenant
        channel=None
        async def close():
            peers.pop(pc,None);await pc.close()
        @pc.on('connectionstatechange')
        async def state_changed():
            if pc.connectionState in ('failed','closed','disconnected'): await close()
        @pc.on('datachannel')
        def datachannel(value):
            nonlocal channel
            channel=value
        def process(image):
            import cv2
            from .main import LOCK,Session,inspection,apply_observation,run_station_models
            from .domain import Workflow,Detection
            from .vision import detect
            if image.shape[1]>960: image=cv2.resize(image,(960,round(image.shape[0]*960/image.shape[1])))
            with LOCK,Session.begin() as db:
                row=inspection(db,request.inspection_id,who)
                result=run_station_models(db,row,who,image,detect(image,Workflow(**row.workflow)))
                _,jpg=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,80])
                response=apply_observation(db,row,who,[Detection(**d) for d in result.pop('detections')],row.last_sequence+1,result,jpg.tobytes())
                response['created']=response['created'].isoformat()
                return response
        @pc.on('track')
        async def track_received(track):
            if track.kind!='video':return
            last=0
            try:
                while pc in peers:
                    frame=await track.recv()
                    if time.monotonic()-last<.5:continue
                    last=time.monotonic()
                    result=await asyncio.to_thread(process,frame.to_ndarray(format='bgr24'))
                    if channel and channel.readyState=='open':channel.send(json.dumps(result))
            except Exception as exc:
                if channel and channel.readyState=='open':channel.send(json.dumps({'error':str(getattr(exc,'detail',type(exc).__name__))}))
                await close()
        try:
            await pc.setRemoteDescription(RTCSessionDescription(sdp=request.sdp,type=request.type))
            await pc.setLocalDescription(await pc.createAnswer())
        except Exception:
            await close();raise HTTPException(422,'Invalid WebRTC offer')
        async def expire():
            await asyncio.sleep(1800)
            if pc in peers:await close()
        asyncio.create_task(expire())
        return {'sdp':pc.localDescription.sdp,'type':pc.localDescription.type}

    async def shutdown():
        await asyncio.gather(*(pc.close() for pc in list(peers)),return_exceptions=True)
        peers.clear()
    return shutdown
