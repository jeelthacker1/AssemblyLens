from tests.test_vision import jpeg

def post_frame(client,id,sequence,parts):return client.post(f'/inspections/{id}/frame?sequence={sequence}',files={'file':('frame.jpg',jpeg(parts),'image/jpeg')})
def test_auth_required(client):
    client.headers.clear();assert client.get('/inspections').status_code==401
def test_viewer_cannot_write(client):
    client.headers['Authorization']='Bearer demo-viewer';assert client.post('/bootstrap').status_code==403
def test_tenant_isolation(client,setup_inspection):
    client.headers['Authorization']='Bearer other-admin'
    assert client.get('/inspections').json()==[]
    assert client.get('/inspections/'+setup_inspection['id']).status_code==404
def test_serial_unique(client,setup_inspection):
    wf=client.get('/records/workflow').json()[0]['id']
    assert client.post('/inspections',json={'serial':'KIT-1','station_id':setup_inspection['station'],'workflow_id':wf}).status_code==409
def test_stale_sequence_rejected(client,setup_inspection):
    id=setup_inspection['id'];assert post_frame(client,id,0,[]).status_code==200
    assert post_frame(client,id,0,[]).status_code==409
def test_camera_to_evidence_to_approval(client,setup_inspection):
    id=setup_inspection['id'];sequence=0;evidence=[]
    for parts in [['base'],['base','bracket'],['base','bracket','cap']]:
        for _ in range(3):
            response=post_frame(client,id,sequence,parts);assert response.status_code==200,response.text
            row=response.json();sequence+=1
            if row['evidence_id']:evidence.append(row['evidence_id'])
    assert row['state']['status']=='awaiting_approval'
    assert len(evidence)==3
    assert client.get('/evidence/'+evidence[0]).headers['content-type']=='image/jpeg'
    client.headers['Authorization']='Bearer demo-reviewer'
    decision=client.post(f'/inspections/{id}/decision',json={'action':'approve','reason':'Physically reviewed all components','expected_version':row['version']})
    assert decision.status_code==200,decision.text
    assert decision.json()['state']['human_verified']
    client.headers['Authorization']='Bearer other-admin'
    assert client.get('/evidence/'+evidence[0]).status_code==404
def test_fault_blocks_approval_and_override_is_audited(client,setup_inspection):
    id=setup_inspection['id']
    for n in range(3):row=post_frame(client,id,n,['cap']).json()
    payload={'action':'approve','reason':'Reviewed assembly','expected_version':row['version']}
    assert client.post(f'/inspections/{id}/decision',json=payload).status_code==409
    client.headers['Authorization']='Bearer demo-reviewer';payload['action']='override'
    assert client.post(f'/inspections/{id}/decision',json=payload).status_code==403
    client.headers['Authorization']='Bearer demo-admin'
    response=client.post(f'/inspections/{id}/decision',json=payload);assert response.status_code==200
    events=client.get('/events',params={'inspection_id':id}).json()
    assert any(e['action']=='override' and e['body']['reason']==payload['reason'] for e in events)
def test_optimistic_review_version(client,setup_inspection):
    id=setup_inspection['id'];post_frame(client,id,0,[])
    assert client.post(f'/inspections/{id}/decision',json={'action':'reject','reason':'Part missing','expected_version':0}).status_code==409
def test_rework_resets_state_preserves_sequence(client,setup_inspection):
    id=setup_inspection['id'];row=post_frame(client,id,10,['cap']).json()
    result=client.post(f'/inspections/{id}/decision',json={'action':'rework','reason':'Remove parts and repeat','expected_version':row['version']}).json()
    assert result['state']['cursor']==0 and result['last_sequence']==10
def test_corrupt_upload_does_not_change_inspection(client,setup_inspection):
    id=setup_inspection['id'];response=client.post(f'/inspections/{id}/frame?sequence=0',files={'file':('a.jpg',b'invalid')})
    assert response.status_code==422
    assert client.get('/inspections/'+id).json()['version']==0
def test_finish_detects_omitted_steps(client,setup_inspection):
    row=client.post('/inspections/'+setup_inspection['id']+'/finish').json()
    assert len(row['state']['faults'])==3
def test_analytics_real_totals(client,setup_inspection):assert client.get('/analytics').json()['total']==1
def test_workflow_snapshot_immutable(client,setup_inspection):
    wf=client.get('/records/workflow').json()[0];wf['body']['name']='Changed'
    assert client.put('/records/workflow/'+wf['id'],json={'body':wf['body']}).status_code==200
    assert client.get('/inspections/'+setup_inspection['id']).json()['workflow']['name']!='Changed'
def test_cvat_import(client):
    data=b'<annotations><image name="a.jpg" width="100" height="100"><box label="base" xtl="10" ytl="10" xbr="30" ybr="40"/></image></annotations>'
    result=client.post('/datasets/import-cvat?name=kit',files={'file':('annotations.xml',data)});assert result.status_code==200,result.text
    assert len(result.json()['body']['images'])==1
def test_bad_model_rejected(client):assert client.post('/models/upload?name=bad&labels=["x"]',files={'file':('bad.onnx',b'invalid')}).status_code==422
