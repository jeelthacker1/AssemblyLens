import pytest
from backend.domain import *

def detection(part,confidence=.95,angle=0):
    x={'base':.1,'bracket':.4,'cap':.72}.get(part,.1)
    return Detection(part=part,confidence=confidence,bbox=(x,.3,.15,.3),angle=angle)
def frames(state,wf,parts,n=3):
    for _ in range(n):state=observe(state,wf,[detection(p) for p in parts])
    return state

def test_correct_sequence_requires_human_approval():
    wf=demo_workflow();s=initial_state()
    for parts in [['base'],['base','bracket'],['base','bracket','cap']]:s=frames(s,wf,parts)
    assert s['cursor']==3 and s['status']=='awaiting_approval' and not s['faults']
def test_stable_presence_is_not_repeated_step():
    s=frames(initial_state(),demo_workflow(),['base'],20)
    assert s['cursor']==1 and not s['faults']
def test_out_of_order_latches():
    wf=demo_workflow();s=frames(initial_state(),wf,['cap'])
    assert {'kind':'incorrect_order','part':'cap'} in s['faults']
    s=frames(s,wf,['base'])
    assert s['status']=='needs_review'
def test_simultaneous_install_cannot_prove_sequence():
    s=frames(initial_state(),demo_workflow(),['base','bracket','cap'])
    assert s['cursor']==1 and len(s['faults'])==2
def test_short_detection_does_not_advance():
    assert frames(initial_state(),demo_workflow(),['base'],2)['cursor']==0
def test_absence_resets_debounce():
    wf=demo_workflow();s=frames(initial_state(),wf,['base'],2);s=frames(s,wf,[],1);s=frames(s,wf,['base'],2)
    assert s['cursor']==0
def test_removed_and_reinstalled_is_repeated():
    wf=demo_workflow();s=frames(initial_state(),wf,['base']);s=frames(s,wf,[]);s=frames(s,wf,['base'])
    assert {'kind':'missing_component','part':'base'} in s['faults']
    assert {'kind':'repeated_step','part':'base'} in s['faults']
def test_uncertain_never_advances():
    s=initial_state()
    for _ in range(8):s=observe(s,demo_workflow(),[detection('base',.4)])
    assert s['cursor']==0 and s['status']=='needs_review'
def test_wrong_zone():
    d=detection('base');d.bbox=(.8,.3,.1,.3)
    s=observe(initial_state(),demo_workflow(),[d]);assert s['status']=='needs_review'
def test_orientation_modulo_180():
    wf=demo_workflow();wf.steps[0].angle=0
    s=initial_state()
    for _ in range(3):s=observe(s,wf,[detection('base',angle=179)])
    assert s['cursor']==1
def test_orientation_rejects_90():
    wf=demo_workflow();wf.steps[0].angle=0
    s=observe(initial_state(),wf,[detection('base',angle=90)])
    assert s['cursor']==0 and s['last_event']=='placement_or_orientation'
def test_model_without_pose_cannot_verify_orientation():
    wf=demo_workflow();wf.steps[0].angle=0
    d=detection('base');d.angle=None
    s=observe(initial_state(),wf,[d])
    assert s['cursor']==0 and s['last_event']=='uncertain'
def test_incomplete_finish_omitted_steps():
    s=finish(initial_state(),demo_workflow());assert len(s['faults'])==3
def test_unknown_component():
    s=observe(initial_state(),demo_workflow(),[detection('alien')]);assert s['faults'][0]['kind']=='incorrect_part'
def test_closed_is_immutable():
    s=initial_state();s['status']='approved';assert observe(s,demo_workflow(),[])==s
def test_input_state_is_not_mutated():
    s=initial_state();observe(s,demo_workflow(),[detection('base')]);assert s==initial_state()
@pytest.mark.parametrize('zone',[(0,0,2,1),(-.1,0,1,1),(0,0,0,1)])
def test_invalid_zone(zone):
    with pytest.raises(ValueError):Step(id='x',part='x',instruction='x',zone=zone)
def test_duplicate_bom():
    wf=demo_workflow().model_dump();wf['parts'].append(wf['parts'][0])
    with pytest.raises(ValueError):Workflow(**wf)
