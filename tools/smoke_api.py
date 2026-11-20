"""Exercise a running PostgreSQL/S3 stack with explicitly synthetic image fixtures."""
import argparse,json,os,uuid
from pathlib import Path
import cv2,numpy as np,httpx

def image(parts):
    pixels=np.full((480,800,3),220,np.uint8)
    for part in parts:
        x,color={'base':(80,(0,0,230)),'bracket':(320,(0,180,0)),'cap':(580,(230,0,0))}[part]
        cv2.rectangle(pixels,(x,150),(x+100,300),color,-1)
    return cv2.imencode('.jpg',pixels)[1].tobytes()

def main():
    p=argparse.ArgumentParser();p.add_argument('--api',default='http://localhost:8010');args=p.parse_args()
    with httpx.Client(base_url=args.api,headers={'Authorization':'Bearer '+os.environ['ASSEMBLYLENS_API_KEY']},timeout=60) as c:
        c.get('/health').raise_for_status();c.post('/bootstrap').raise_for_status()
        station=c.get('/records/station').json()[0]['id'];workflow=c.get('/records/workflow').json()[0]['id']
        r=c.post('/inspections',json={'serial':'SYNTHETIC-SMOKE-'+str(uuid.uuid4())[:8],'station_id':station,'workflow_id':workflow});r.raise_for_status();id=r.json()['id'];seq=0;evidence=[]
        for parts in [['base'],['base','bracket'],['base','bracket','cap']]:
            for _ in range(3):
                r=c.post(f'/inspections/{id}/frame?sequence={seq}',files={'file':('synthetic-test.jpg',image(parts))});r.raise_for_status();row=r.json();seq+=1
                if row['evidence_id']:evidence.append(row['evidence_id'])
        assert row['state']['status']=='awaiting_approval',row
        for key in evidence:
            r=c.get('/evidence/'+key);r.raise_for_status();assert r.headers['content-type']=='image/jpeg'
        r=c.post(f'/inspections/{id}/decision',json={'action':'approve','reason':'Automated integration test on explicitly synthetic pixels, not product acceptance','expected_version':row['version']});r.raise_for_status()
        bad=c.post('/inspections',json={'serial':'SYNTHETIC-FAULT-'+str(uuid.uuid4())[:8],'station_id':station,'workflow_id':workflow}).json()
        for seq in range(3):
            r=c.post(f'/inspections/{bad["id"]}/frame?sequence={seq}',files={'file':('synthetic-test.jpg',image(['cap']))});r.raise_for_status()
        assert any(f['kind']=='incorrect_order' for f in r.json()['state']['faults'])
        report={'test':'running API + database + evidence store','pixels':'synthetic fixtures, not camera validation','correct_sequence':'passed','incorrect_order':'passed','photographs_retrieved':len(evidence),'human_decision_endpoint':'passed with explicit synthetic-test reason','serial':row['serial'],'inspection_id':id}
        Path('docs/smoke-results.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
