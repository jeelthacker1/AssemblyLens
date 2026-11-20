"""Actual ONNX execution and WebRTC transport tests on explicitly synthetic pixels."""
import asyncio
import io
import numpy as np
import pytest
from backend.vision import OnnxDetector

def tiny_model():
    onnx=pytest.importorskip('onnx')
    from onnx import helper,TensorProto,numpy_helper
    graph=helper.make_graph([
        helper.make_node('ReduceMean',['image'],['mean'],axes=[1,2,3],keepdims=0),
        helper.make_node('Reshape',['mean','shape'],['score']),
        helper.make_node('Concat',['boxes','score','label'],['detections'],axis=2)
    ],'pixel-dependent-test-model',[helper.make_tensor_value_info('image',TensorProto.FLOAT,[1,3,320,320])],[helper.make_tensor_value_info('detections',TensorProto.FLOAT,[1,1,6])],[numpy_helper.from_array(np.array([1,1,1],np.int64),'shape'),numpy_helper.from_array(np.array([[[32,96,80,192]]],np.float32),'boxes'),numpy_helper.from_array(np.zeros((1,1,1),np.float32),'label')])
    model=helper.make_model(graph,opset_imports=[helper.make_opsetid('',17)]);model.ir_version=10
    return model.SerializeToString()

def test_onnx_prediction_depends_on_actual_pixels(tmp_path):
    path=tmp_path/'test.onnx';path.write_bytes(tiny_model());model=OnnxDetector(path,['base'])
    assert model.infer(np.zeros((320,320,3),np.uint8))==[]
    result=model.infer(np.full((320,320,3),255,np.uint8))
    assert result[0]['part']=='base' and result[0]['confidence']>.99 and result[0]['angle'] is None

def test_model_registry_activation_and_live_selection(client,setup_inspection):
    import cv2
    upload=client.post('/models/upload?name=test&labels=["base"]',files={'file':('test.onnx',tiny_model())});assert upload.status_code==200,upload.text
    model=upload.json();id=model['id']
    assert client.post(f'/models/{id}/deployment',json={'stage':'active','reason':'Test validation contract','validation':{}}).status_code==422
    report={'precision':1,'recall':1,'false_acceptance_rate':0,'false_rejection_rate':0,'dataset_sha256':'synthetic-test-only'}
    assert client.post(f'/models/{id}/deployment',json={'stage':'active','reason':'Synthetic contract test only','validation':report}).status_code==200
    station=client.get('/records/station').json()[0];station['body']['active_model_id']=id
    assert client.put('/records/station/'+station['id'],json={'body':station['body']}).status_code==200
    blob=cv2.imencode('.jpg',np.full((320,320,3),255,np.uint8))[1].tobytes()
    response=client.post(f'/inspections/{setup_inspection["id"]}/frame?sequence=0',files={'file':('frame.jpg',blob)})
    assert response.status_code==200,response.text
    assert response.json()['observation']['model']==model['body']['sha256']

def test_webrtc_transports_actual_frames(client,setup_inspection):
    aiortc=pytest.importorskip('aiortc')
    from aiortc import RTCPeerConnection,RTCSessionDescription,RTCConfiguration,VideoStreamTrack
    from av import VideoFrame
    from tests.test_vision import kit_image
    class Track(VideoStreamTrack):
        async def recv(self):
            pts,time_base=await self.next_timestamp()
            frame=VideoFrame.from_ndarray(kit_image(['base']),format='bgr24');frame.pts=pts;frame.time_base=time_base;return frame
    async def exercise():
        pc=RTCPeerConnection(RTCConfiguration(iceServers=[]));pc.addTrack(Track());channel=pc.createDataChannel('inspection');received=asyncio.get_running_loop().create_future()
        @channel.on('message')
        def message(data):
            import json
            value=json.loads(data)
            if not received.done():received.set_result(value)
        try:
            await pc.setLocalDescription(await pc.createOffer())
            response=await asyncio.to_thread(client.post,'/webrtc/offer',json={'inspection_id':setup_inspection['id'],'sdp':pc.localDescription.sdp,'type':'offer'})
            assert response.status_code==200,response.text
            await pc.setRemoteDescription(RTCSessionDescription(**response.json()))
            value=await asyncio.wait_for(received,20)
            assert 'error' not in value,value
            assert value['observation']['detections'][0]['part']=='base'
        finally:await pc.close()
    asyncio.run(exercise())
