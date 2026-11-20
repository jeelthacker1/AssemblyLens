import cv2
import numpy as np
import pytest
from backend.domain import demo_workflow
from backend.vision import *

def kit_image(parts):
    image=np.full((480,800,3),220,np.uint8)
    for part in parts:
        x,color={'base':(80,(0,0,230)),'bracket':(320,(0,180,0)),'cap':(580,(230,0,0))}[part]
        cv2.rectangle(image,(x,150),(x+100,300),color,-1)
    return image
def jpeg(parts):return cv2.imencode('.jpg',kit_image(parts))[1].tobytes()
def test_real_segmentation_on_controlled_pixels():
    result=detect(kit_image(['base','bracket','cap']),demo_workflow())
    assert {d['part'] for d in result['detections']}=={'base','bracket','cap'}
    assert all(d['polygon'] for d in result['detections'])
def test_blank_frame_no_parts():assert not detect(kit_image([]),demo_workflow())['detections']
def test_decode_corrupt():
    with pytest.raises(ValueError):decode(b'not an image')
def test_decode_oversized():
    with pytest.raises(ValueError):decode(b'x'*4_000_001)
def test_plane_measurement():
    cal=calibrate_plane([[0,0],[200,0],[200,100],[0,100]],100,50)
    assert abs(measure([[0,0],[200,0]],cal)-100)<.001
def test_degenerate_calibration():
    with pytest.raises(ValueError):calibrate_plane([[0,0]]*4,100,50)
def test_reference_feature_match():
    image=np.random.default_rng(42).integers(0,255,(400,600,3),dtype=np.uint8)
    assert reference_match(image,image)['matched']
def test_reference_no_texture_is_uncertain():assert not reference_match(kit_image([]),kit_image([]))['matched']
def test_tracker_stable_and_expires():
    tracker=Tracker();d=detect(kit_image(['base']),demo_workflow())['detections']
    first=tracker.update(d)[0]['track_id'];second=tracker.update(d)[0]['track_id'];assert first==second
    tracker.update([]);assert tracker.update(d)[0]['track_id']!=first
