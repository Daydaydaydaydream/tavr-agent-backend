from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.guidance_v2 import generate_guidance
from app.models.schemas_v2 import GuideRequest

client = TestClient(app)
URL = '/api/v2/agent/guide'

def payload(**state):
    base = dict(current_page='vessel_extract', ct_loaded=True, picked_point_count=0,
                segmentation_status='not_started', segmentation_result_available=False,
                prosthesis_status='absent', move_enabled=False, returned=False)
    base.update(state)
    return dict(protocol_version='2.1', request_id='c62ef01e-8c51-44b9-a88a-e70c743bb80f', state_revision=1, state=base)

@pytest.mark.parametrize('state,reason,target', [
    ({'ct_loaded':False},'CT_REQUIRED',None),
    ({},'SEGMENT_START','segment.auto_segment'),
    ({'segmentation_status':'running'},'SEGMENT_RUNNING',None),
    ({'segmentation_status':'failed'},'SEGMENT_FAILED','segment.auto_segment'),
    ({'segmentation_status':'failed','segmentation_result_available':True},'SEGMENT_FAILED','segment.auto_segment'),
    ({'segmentation_status':'succeeded','segmentation_result_available':True},'SEGMENT_AVAILABLE','nav.next'),
    ({'current_page':'annulus_pick','picked_point_count':1},'PICK_POINTS','annulus.pick'),
    ({'current_page':'annulus_pick','picked_point_count':3},'POINTS_COMPLETE','nav.next'),
    ({'current_page':'navigation'},'RETURN_TO_POINTS','nav.back'),
    ({'current_page':'navigation','picked_point_count':3},'SET_PROSTHESIS','navigation.sent_setting'),
    ({'current_page':'navigation','picked_point_count':3,'prosthesis_status':'unknown'},'CHECK_PROSTHESIS',None),
    ({'current_page':'navigation','picked_point_count':3,'prosthesis_status':'available'},'MOVE_PROSTHESIS','navigation.sent_move'),
    ({'current_page':'navigation','picked_point_count':3,'prosthesis_status':'available','move_enabled':True},'MOVING_PROSTHESIS','navigation.sent_return'),
    ({'current_page':'navigation','picked_point_count':3,'prosthesis_status':'available','returned':True},'PROSTHESIS_RETURNED',None),
    ({'current_page':'render'},'ENTER_SEGMENTATION','nav.next'),
    ({'current_page':'reserved_4'},'NO_GUIDANCE',None),
])
def test_rules(state,reason,target):
    data=payload(**state); before=deepcopy(data)
    response=client.post(URL,json=data)
    assert response.status_code==200,response.text
    out=response.json()
    assert (out['reason_code'],out['target_id'])==(reason,target)
    assert out['request_id']==data['request_id'] and out['state_revision']==1
    assert data==before

@pytest.mark.parametrize('n',[0,1,2,3])
@pytest.mark.parametrize('seg',['not_started','running','failed'])
def test_segmentation_does_not_override_points(n,seg):
    out=client.post(URL,json=payload(current_page='annulus_pick',picked_point_count=n,segmentation_status=seg)).json()
    assert out['reason_code']==('POINTS_COMPLETE' if n==3 else 'PICK_POINTS')

@pytest.mark.parametrize('field,value',[('ct_loaded','true'),('picked_point_count',True),('picked_point_count',4),('picked_point_count',1.5),('current_page','bad'),('prosthesis_status','ready')])
def test_invalid_state(field,value):
    res=client.post(URL,json=payload(**{field:value}))
    assert res.status_code==422
    assert res.json()['error']['code']=='INVALID_REQUEST'

@pytest.mark.parametrize('state',[dict(ct_loaded=False,picked_point_count=1),dict(segmentation_status='succeeded'),dict(move_enabled=True),dict(returned=True)])
def test_invariants(state):
    assert client.post(URL,json=payload(**state)).json()['error']['code']=='INCONSISTENT_STATE'

@pytest.mark.parametrize('body',[b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}',b'\xff',b'{'])
def test_bad_json(body):
    out=client.post(URL,content=body,headers={'content-type':'application/json'})
    assert out.status_code==422 and out.json()['error']['code']=='INVALID_JSON'

@pytest.mark.parametrize('body',[[],None,True,3])
def test_invalid_root(body):
    import json
    assert client.post(URL,content=json.dumps(body),headers={'content-type':'application/json'}).status_code==422

def test_limits_and_media():
    assert client.post(URL,content=b' '*16385,headers={'content-type':'application/json'}).status_code==413
    assert client.post(URL,content=b'{}').status_code==415
    assert client.post(URL,json=payload(),headers={'content-encoding':'gzip'}).status_code==415
    assert client.post(URL,json=payload(),headers={'content-type':'Application/JSON; charset=UTF-8'}).status_code==200

def test_numeric_integer_and_unknown_fields():
    data=payload(picked_point_count=1.0); data['state_revision']=1.0
    assert client.post(URL,json=data).status_code==200
    data['patient-secret']='sensitive'
    out=client.post(URL,json=data)
    assert out.status_code==422 and 'patient-secret' not in out.text and 'sensitive' not in out.text

def test_v1_and_errors_are_isolated():
    assert client.post('/agent/guide',json={'state':{}}).status_code==200
    assert 'detail' in client.post('/agent/guide',json={}).json()
    data=payload(); data['protocol_version']='2'
    assert client.post(URL,json=data).status_code==422

def test_internal_error(monkeypatch):
    import app.routers.guide_v2 as router
    def fail(_): raise RuntimeError('do not expose')
    monkeypatch.setattr(router,'generate_guidance',fail)
    out=TestClient(app,raise_server_exceptions=False).post(URL,json=payload())
    assert out.status_code==500 and 'do not expose' not in out.text

def test_observed_sequence():
    for n in [0,1,2,3,2,3]:
        out=client.post(URL,json=payload(current_page='annulus_pick',picked_point_count=n)).json()
        if n<3: assert f'剩余 {3-n}' in out['message']
    for changes,expected in [({'prosthesis_status':'unknown'},'CHECK_PROSTHESIS'),({'prosthesis_status':'available'},'MOVE_PROSTHESIS'),({'prosthesis_status':'available','move_enabled':True},'MOVING_PROSTHESIS'),({'prosthesis_status':'available','move_enabled':True,'returned':True},'PROSTHESIS_RETURNED')]:
        out=client.post(URL,json=payload(current_page='navigation',picked_point_count=3,**changes)).json()
        assert out['reason_code']==expected

def test_openapi_matches_published_contract():
    import json
    from pathlib import Path
    assert app.openapi()==json.loads(Path('docs/contracts/planning-prompts-v2.1.openapi.json').read_text())

def test_streamed_body_limit_without_content_length():
    import asyncio
    from starlette.requests import Request
    from app.routers.guide_v2 import guide_v2
    chunks=iter([b' '*10000,b' '*10000])
    async def receive():
        return {'type':'http.request','body':next(chunks),'more_body':True}
    request=Request({'type':'http','method':'POST','path':URL,'headers':[(b'content-type',b'application/json')]},receive)
    response=asyncio.run(guide_v2(request))
    assert response.status_code==413
