import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from traceledger.agent import load_cases, run_agent, RunError
from traceledger.environment import Environment
from traceledger.grading import reference_answer
from traceledger.experiment import build_plan, seal, verify_plan, execute_plan, ROOT
from traceledger.analyze import summarize
from traceledger.preferences import check_candidate

CASES=load_cases(ROOT/'data/cases.jsonl')
BY_ID={c['id']:c for c in CASES}
PAIRS=load_cases(ROOT/'data/preference_pairs.jsonl')

class Item:
    def __init__(self,x): self.x=x
    def model_dump(self,**kwargs): return self.x

class ScriptClient:
    def __init__(self,root,invalid_schema=False):
        self.responses=self;self.requests=[];self.invalid_schema=invalid_schema;self.answers={}
        for c in CASES:
            e=Environment(c['environment'],root/c['id'])
            for s in c['reference_steps']: e.call(s['tool'],s['arguments'])
            self.answers[c['id']]=reference_answer(c,e)
    def create(self,**kw):
        self.requests.append(copy.deepcopy(kw))
        c=next(c for c in CASES if c['prompt']==kw['input'][0]['content'])
        n=sum(i.get('type')=='function_call_output' for i in kw['input'])
        if n<len(c['reference_steps']):
            s=c['reference_steps'][n]
            output=[Item({'type':'function_call','name':s['tool'],'arguments':json.dumps(s['arguments']),'call_id':f'c{n}'})]
            text=''
        else:
            output=[];text=json.dumps({'invalid':True} if self.invalid_schema else self.answers[c['id']])
        return SimpleNamespace(id=f'r{len(self.requests)}',_request_id=f'req{len(self.requests)}',model='SCRIPTED-NOT-LIVE',
            status='completed',usage=Item({'input_tokens':10,'output_tokens':5}),output=output,output_text=text)

@pytest.mark.parametrize('pair',PAIRS,ids=lambda p:p['pair_id'])
def test_preference_contrast(pair,tmp_path):
    c=BY_ID[pair['case_id']]
    assert c['split']=='development'
    assert check_candidate(c,pair['input']['observed_tool_trace'],pair['chosen'],tmp_path/'good')
    assert not check_candidate(c,pair['input']['observed_tool_trace'],pair['rejected'],tmp_path/'bad')
    assert pair['human_review']=='pending' and pair['model_generated_trace'] is False


def test_preference_family_balance():
    assert len(PAIRS)==18
    assert {f:sum(p['family']==f for p in PAIRS) for f in ('CTX','HAND','REC')}=={'CTX':6,'HAND':6,'REC':6}

def test_validation_excluded_from_preferences():
    assert not {p['case_id'] for p in PAIRS}&{c['id'] for c in CASES if c['split']=='reserved_validation'}

def test_full_plan_counts():
    p=build_plan('explicit-snapshot')
    assert len(p['schedule'])==144
    assert sum(s['split']=='development' for s in p['schedule'])==108
    assert sum(s['split']=='reserved_validation' for s in p['schedule'])==36
    assert p['settings']['max_api_requests']==1728

def test_pilot_does_not_touch_validation():
    p=build_plan('explicit-snapshot','pilot')
    assert len(p['schedule'])==12
    assert all(s['split']=='development' for s in p['schedule'])

def test_seed_controls_order_only():
    a=build_plan('m');b=build_plan('m')
    assert a['schedule']==b['schedule']
    assert a['schedule']!=build_plan('m',seed=18)['schedule']

def test_validation_runs_after_development():
    splits=[s['split'] for s in build_plan('m')['schedule']]
    idx=splits.index('reserved_validation')
    assert all(s=='reserved_validation' for s in splits[idx:])

def test_frozen_plan_verifies():
    verify_plan(seal(build_plan('m')))

def test_modified_plan_rejected():
    p=seal(build_plan('m'));p['settings']['max_output_tokens']=999
    with pytest.raises(ValueError,match='Plan hash'):verify_plan(p)

def test_changed_source_hash_rejected():
    p=build_plan('m');p['source_hashes']['traceledger/agent.py']='wrong'
    with pytest.raises(ValueError,match='Source'):verify_plan(seal(p))

def test_empty_results_are_not_zero_percent_success():
    s=summarize(build_plan('m','pilot'),[])
    assert s['attempted_episodes']==0 and s['not_attempted_episodes']==12
    assert all(t['all_attempt_success_rate'] is None for t in s['tables'])

def test_mocked_pilot_reports_every_episode(tmp_path):
    p=seal(build_plan('mock','pilot'))
    client=ScriptClient(tmp_path/'reference')
    s=execute_plan(p,client,tmp_path/'experiment',run_kind='mocked_test')
    assert s['run_kind']=='mocked_test' and s['attempted_episodes']==12
    assert s['full_schedule_attempted'] is True
    total=next(t for t in s['tables'] if t['split']==t['family']==t['condition']=='ALL')
    assert total['schema_valid_completions']==12 and total['machine_passes']==12
    assert s['api_create_attempts_recorded']==len(client.requests)>12
    assert s['usage']['input_tokens_reported']==10*len(client.requests)
    assert all('reference_steps' not in json.dumps(r['input']) for r in client.requests)
    assert s['paired_comparisons'][-1]['fully_attempted_scenarios']==6

def test_invalid_schema_not_valid_completion(tmp_path):
    p=seal(build_plan('mock','pilot'))
    s=execute_plan(p,ScriptClient(tmp_path/'ref',True),tmp_path/'run',run_kind='mocked_test')
    total=next(t for t in s['tables'] if t['split']==t['family']==t['condition']=='ALL')
    assert total['schema_valid_completions']==0 and total['status_counts']['invalid_schema']==12
    assert total['all_attempt_success_rate']==0
    assert total['machine_pass_rate_valid'] is None

def test_request_cap_stops_before_excess_call(tmp_path):
    p=seal(build_plan('mock','pilot',max_requests=2))
    client=ScriptClient(tmp_path/'ref')
    s=execute_plan(p,client,tmp_path/'run',run_kind='mocked_test')
    assert len(client.requests)==2 and s['api_create_attempts_recorded']==2
    assert s['not_attempted_episodes']>0

class RateLimitMock(Exception):
    status_code=429;request_id='req-rate-limit'
    body={'error':{'code':'rate_limit_exceeded','message':'DO-NOT-LOG-THIS'}}
    response=SimpleNamespace(headers={'retry-after':'2'})

class FailedClient:
    def __init__(self):self.responses=self;self.calls=0
    def create(self,**kw):self.calls+=1;raise RateLimitMock('DO-NOT-LOG-THIS')

def test_rate_limit_preserved_without_retries(tmp_path):
    p=seal(build_plan('mock','pilot'));client=FailedClient()
    s=execute_plan(p,client,tmp_path/'run',run_kind='mocked_test')
    assert client.calls==1 and s['attempted_episodes']==1 and s['not_attempted_episodes']==11
    assert s['http_status_counts']=={'429':1}
    text=(tmp_path/'run'/'results.jsonl').read_text()
    assert 'req-rate-limit' in text and 'retry-after' in text and 'DO-NOT-LOG-THIS' not in text

def test_existing_run_directory_is_not_overwritten(tmp_path):
    with pytest.raises(ValueError,match='exists'):
        execute_plan(seal(build_plan('m','pilot')),None,tmp_path,run_kind='mocked_test')

def test_invalid_json_keeps_raw_output_and_usage(tmp_path):
    e=Environment({},tmp_path)
    response=SimpleNamespace(id='r',model='mock',status='completed',usage=Item({'input_tokens':3,'output_tokens':4}),output=[],output_text='not-json')
    client=SimpleNamespace(responses=SimpleNamespace(create=lambda **kw:response))
    with pytest.raises(RunError) as exc:run_agent(client,'mock','task',e)
    assert exc.value.code=='invalid_final_json'
    cp=json.loads((tmp_path/'checkpoint.json').read_text())
    assert cp['responses'][0]['usage']['output_tokens']==4
    assert (tmp_path/'final_text.txt').read_text()=='not-json'

def test_incomplete_response_keeps_usage(tmp_path):
    e=Environment({},tmp_path)
    response=SimpleNamespace(id='r',model='mock',status='incomplete',usage=Item({'input_tokens':2,'output_tokens':2500}),output=[],output_text='',incomplete_details=Item({'reason':'max_output_tokens'}))
    with pytest.raises(RunError) as exc:
        run_agent(SimpleNamespace(responses=SimpleNamespace(create=lambda **kw:response)),'mock','task',e)
    assert exc.value.code=='incomplete_response'
    cp=json.loads((tmp_path/'checkpoint.json').read_text())
    assert cp['responses'][0]['incomplete_details']['reason']=='max_output_tokens'

def test_reasoning_items_preserved(tmp_path):
    e=Environment({},tmp_path);requests=[]
    seq=[SimpleNamespace(id='a',model='mock',status='completed',usage=None,output_text='',output=[
        Item({'type':'reasoning','id':'rs1','summary':[],'encrypted_content':'opaque-state'}),
        Item({'type':'function_call','name':'list_sources','call_id':'c1','arguments':'{}'})]),
        SimpleNamespace(id='b',model='mock',status='completed',usage=None,output=[],output_text='{}')]
    def create(**kw): requests.append(copy.deepcopy(kw));return seq.pop(0)
    run_agent(SimpleNamespace(responses=SimpleNamespace(create=create)),'mock','task',e)
    assert any(i.get('encrypted_content')=='opaque-state' for i in requests[1]['input'])
    assert any(i.get('call_id')=='c1' and i['type']=='function_call_output' for i in requests[1]['input'])
    assert requests[0]['instructions']==requests[1]['instructions']

def test_errors_remain_in_primary_denominator():
    p=build_plan('m','pilot');s1,s2=p['schedule'][:2]
    rows=[{**s1,'run_status':'completed','run_kind':'mocked_test','grading':{'machine_pass':True}},
          {**s2,'run_status':'api_error','run_kind':'mocked_test'}]
    s=summarize(p,rows)
    allrow=next(t for t in s['tables'] if t['split']==t['family']==t['condition']=='ALL')
    assert allrow['all_attempt_success_rate']==.5 and allrow['machine_pass_rate_valid']==1

def test_duplicate_attempts_rejected():
    p=build_plan('m','pilot');r={**p['schedule'][0],'run_status':'api_error'}
    with pytest.raises(ValueError,match='Duplicate'):summarize(p,[r,r])

def test_mixed_mock_live_data_rejected():
    p=build_plan('m','pilot');a,b=p['schedule'][:2]
    with pytest.raises(ValueError,match='live and mocked'):
        summarize(p,[{**a,'run_kind':'mocked_test'},{**b,'run_kind':'live_api'}])

def test_result_metadata_mismatch_rejected():
    p=build_plan('m','pilot');r={**p['schedule'][0],'family':'REC' if p['schedule'][0]['family']!='REC' else 'CTX'}
    with pytest.raises(ValueError,match='metadata'):summarize(p,[r])
