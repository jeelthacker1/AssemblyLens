import json
import os
from pathlib import Path
import tempfile
import pytest

_root=Path(tempfile.mkdtemp(prefix='assemblylens-tests-'))
os.environ['DATABASE_URL']='sqlite:///'+str(_root/'test.db').replace('\\','/')
os.environ['DATA_DIR']=str(_root/'data')
os.environ['DEMO_MODE']='1'
os.environ['API_KEYS_JSON']=json.dumps({'other-admin':{'tenant':'other','user':'other-admin','role':'admin'}})
from backend.main import app
from backend.db import Base,engine
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
    with TestClient(app) as client:
        client.headers['Authorization']='Bearer demo-admin'
        yield client

@pytest.fixture
def setup_inspection(client):
    client.post('/bootstrap').raise_for_status()
    station=client.get('/records/station').json()[0]['id']
    workflow=client.get('/records/workflow').json()[0]['id']
    response=client.post('/inspections',json={'serial':'KIT-1','station_id':station,'workflow_id':workflow})
    response.raise_for_status();return response.json()
