import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from traceledger.agent import load_cases, run_agent, RunError
from traceledger.environment import Environment
from traceledger.grading import grade, reference_answer
from traceledger.schemas import TOOLS

CASES=load_cases(Path(__file__).parents[1]/'data/cases.jsonl')

def execute(case,tmp_path):
    env=Environment(case['environment'],tmp_path)
    for s in case['reference_steps']:env.call(s['tool'],s['arguments'])
    return env,reference_answer(case,env)

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_reference_trace(case,tmp_path):
    env,answer=execute(case,tmp_path)
    assert grade(case,answer,env)['machine_pass']

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_wrong_status_rejected(case,tmp_path):
    env,answer=execute(case,tmp_path)
    answer['status']='blocked' if answer['status']=='complete' else 'complete'
    assert not grade(case,answer,env)['machine_pass']

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_fabricated_attribution_rejected(case,tmp_path):
    env,answer=execute(case,tmp_path)
    if answer['claims']:answer['claims'][0]['source_ids']=['fiction']
    else:answer['claims']=[{'key':'fiction','value':'yes','source_ids':['fiction']}]
    assert not grade(case,answer,env)['machine_pass']

def test_unknown_tool(tmp_path):
    assert Environment({},tmp_path).call('delete_everything',{})['code']=='unknown_tool'

def test_schema_error(tmp_path):
    assert Environment({},tmp_path).call('read_source',{'source_id':123})['code']=='schema_error'

def test_invalid_json_arguments(tmp_path):
    assert Environment({},tmp_path).call('read_source',None)['code']=='schema_error'

def test_unread_source_write_denied(tmp_path):
    env=Environment({},tmp_path)
    r=env.call('write_artifact',{'name':'report.md','content':'x','source_ids':['missing'],'idempotency_key':'k'})
    assert r['code']=='unread_source' and env.new_writes==0

def test_path_traversal_rejected(tmp_path):
    env=Environment({},tmp_path)
    r=env.call('write_artifact',{'name':'../outside.md','content':'x','source_ids':['missing'],'idempotency_key':'k'})
    assert r['code']=='invalid_name'

def test_duplicate_write_same_key(tmp_path):
    c=next(c for c in CASES if c['id']=='HAND-07')
    env,answer=execute(c,tmp_path)
    retry=env.call('write_artifact',c['reference_steps'][1]['arguments'])
    assert retry['status']=='ok' and env.new_writes==1

def test_receipt_integrity_check(tmp_path):
    c=next(c for c in CASES if c['id']=='HAND-02')
    env,answer=execute(c,tmp_path)
    (tmp_path/'a-final.md').write_text('tampered')
    assert env.call('inspect_artifact',{'artifact_id':'a-final'})['code']=='integrity_error'
    assert not grade(c,answer,env)['machine_pass']

def test_no_retry_constraint_detected(tmp_path):
    c=next(c for c in CASES if c['id']=='REC-06')
    env,answer=execute(c,tmp_path)
    env.call('read_source',{'source_id':'s-plan'})
    assert 'retry_limit:s-plan' in grade(c,answer,env)['failures']

class Item:
    def __init__(self,value):self.value=value
    def model_dump(self,**kwargs):return self.value

class MockResponses:
    def __init__(self,case,env):self.case=case;self.env=env;self.index=0;self.requests=[]
    def create(self,**kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        assert 'expected' not in kwargs['input'][0]['content']
        steps=self.case['reference_steps']
        if self.index<len(steps):
            step=steps[self.index];self.index+=1
            return SimpleNamespace(id=f'r{self.index}',status='completed',model='mock-not-a-model',usage=None,output_text='',
                output=[Item({'type':'function_call','name':step['tool'],'call_id':f'call{self.index}',
                              'arguments':json.dumps(step['arguments'])})])
        return SimpleNamespace(id='r-final',status='completed',model='mock-not-a-model',usage=None,output=[],
                               output_text=json.dumps(reference_answer(self.case,self.env)))

@pytest.mark.parametrize('cid',['CTX-01','HAND-07','REC-01','REC-06'])
def test_sdk_loop_mocked(cid,tmp_path):
    c=next(c for c in CASES if c['id']==cid)
    env=Environment(c['environment'],tmp_path)
    responses=MockResponses(c,env)
    rec=run_agent(SimpleNamespace(responses=responses),'mock',c['prompt'],env)
    assert grade(c,rec['final'],env)['machine_pass']
    assert all(req['store'] is False and req['parallel_tool_calls'] is False for req in responses.requests)
    assert all(t['strict'] is True for t in TOOLS)
    assert any(i['type']=='function_call_output' for i in responses.requests[-1]['input'] if 'type' in i)
