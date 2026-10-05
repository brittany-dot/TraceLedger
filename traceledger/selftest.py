"""Exercise authored reference traces and mutations. NEVER a live-model benchmark."""
import copy
import hashlib
import json
import platform
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from .agent import load_cases
from .environment import Environment
from .grading import grade, reference_answer


def run(out: Path):
    rows=[];pairs=[]
    cases=load_cases('data/cases.jsonl')
    with tempfile.TemporaryDirectory() as tmp:
        for c in cases:
            env=Environment(c['environment'],Path(tmp)/c['id'])
            for step in c['reference_steps']:env.call(step['tool'],step['arguments'])
            answer=reference_answer(c,env)
            good=grade(c,answer,env)
            bad_status=copy.deepcopy(answer)
            bad_status['status']='blocked' if answer['status']=='complete' else 'complete'
            bad_source=copy.deepcopy(answer)
            if bad_source['claims']:bad_source['claims'][0]['source_ids']=['invented:source']
            else:bad_source['claims']=[{'key':'invented','value':'unsupported','source_ids':['invented:source']}]
            rows.append({'case_id':c['id'],'family':c['family'],'run_kind':'authored_reference_trace',
                         'reference':good,'wrong_status_rejected':not grade(c,bad_status,env)['machine_pass'],
                         'unsupported_source_rejected':not grade(c,bad_source,env)['machine_pass'],
                         'trace':env.trace,'authored_final':answer})
            if c['id'] in {'CTX-01','CTX-05','HAND-01','HAND-07','REC-05','REC-06'}:
                pairs.append({'case_id':c['id'],'label_provenance':'synthetic, rule-authored; not human preference collection',
                              'input':{'prompt':c['prompt'],'observed_tool_trace':env.trace},
                              'preferred':answer,'dispreferred':bad_status,
                              'rationale':'Preferred terminal state matches the observed execution/evidence state; the alternate falsely changes completion status.',
                              'training_status':'not used for training'})
    summary={'run_kind':'offline_harness_validation_NOT_model_evaluation','generated_utc':datetime.now(timezone.utc).isoformat(),
             'python_version':platform.python_version(),'case_file_sha256':hashlib.sha256(Path('data/cases.jsonl').read_bytes()).hexdigest(),
             'reference_traces':len(rows),'reference_traces_accepted':sum(r['reference']['machine_pass'] for r in rows),
             'mutated_outputs':2*len(rows),'mutated_outputs_rejected':sum(r['wrong_status_rejected']+r['unsupported_source_rejected'] for r in rows),
             'live_api_runs':0,'observed_model_failure_rate':None,
             'by_family':{f:{'reference_traces':8,'accepted':sum(r['reference']['machine_pass'] for r in rows if r['family']==f)} for f in ['CTX','HAND','REC']},
             'note':'Authored control traces and mechanical mutations share the design assumptions of the grader. This is not independent semantic calibration or evidence of model reliability.'}
    out.mkdir(exist_ok=True,parents=True)
    (out/'offline_validation.json').write_text(json.dumps(summary,indent=2))
    (out/'reference_trace_records.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
    Path('data/preference_examples.jsonl').write_text('\n'.join(json.dumps(p) for p in pairs)+'\n')
    print(json.dumps(summary,indent=2))
    assert summary['reference_traces_accepted']==24
    assert summary['mutated_outputs_rejected']==48

if __name__=='__main__': run(Path('reports'))
