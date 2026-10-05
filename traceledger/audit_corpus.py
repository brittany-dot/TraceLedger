"""Audit an export locally. Outputs aggregates only; never uploads conversations.

Input must be a conversations JSON array or an object containing 'conversations'.
Counts include branches in mapping, not just the selected visible conversation path.
This implementation loads one JSON file into memory. Audit split exports separately
unless a cross-file deduplication pass is added; do not sum overlapping snapshots.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def audit(path: str | Path) -> dict:
    p=Path(path)
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''): h.update(block)
    with p.open(encoding='utf-8') as f: data=json.load(f)
    if isinstance(data,dict): data=data.get('conversations')
    if not isinstance(data,list): raise ValueError('Expected a conversation array.')
    conversations=set(); messages={}; roles=Counter(); active_days=set(); dates=[]
    nodes=0; missing_ids=0; missing_timestamps=0; text_bytes=0; null_nodes=0; duplicates=0; conflicting=0
    for c in data:
        cid=c.get('conversation_id') or c.get('id')
        if cid: conversations.add(cid)
        mapping=c.get('mapping',{})
        if not isinstance(mapping,dict): raise ValueError('Unsupported conversation mapping structure.')
        for node_id,node in mapping.items():
            m=node.get('message')
            if not m: null_nodes+=1;continue
            nodes+=1
            mid=m.get('id') or node_id
            if not mid: missing_ids+=1;continue
            signature=hashlib.sha256(json.dumps(m,sort_keys=True).encode()).hexdigest()
            if mid in messages:
                duplicates+=1
                if messages[mid]!=signature: conflicting+=1
                continue
            messages[mid]=signature
            role=m.get('author',{}).get('role','unknown');roles[role]+=1
            t=m.get('create_time')
            if isinstance(t,(int,float)):
                dt=datetime.fromtimestamp(t,timezone.utc);dates.append(dt.isoformat())
                if role=='user':active_days.add(dt.date().isoformat())
            else:missing_timestamps+=1
            for part in m.get('content',{}).get('parts',[]):
                if isinstance(part,str):text_bytes+=len(part.encode('utf-8'))
    return {'audit_date_utc':datetime.now(timezone.utc).isoformat(), 'input_alias':'archival-snapshot-A',
            'input_sha256':h.hexdigest(),'input_bytes':p.stat().st_size,'input_decimal_mb':round(p.stat().st_size/1e6,6),
            'conversation_records':len(data),'unique_conversation_ids':len(conversations),
            'non_null_message_nodes':nodes,'unique_message_ids':len(messages),'duplicate_message_id_occurrences':duplicates,
            'duplicate_id_payload_differences':conflicting,'null_message_nodes':null_nodes,'missing_message_ids':missing_ids,
            'unique_message_role_counts':dict(roles),'user_active_utc_days':len(active_days),
            'earliest_message_utc':min(dates) if dates else None,'latest_message_utc':max(dates) if dates else None,
            'missing_message_timestamps':missing_timestamps,'string_content_utf8_bytes':text_bytes,
            'count_scope':'All exported mapping branches; unique message IDs; roles include user/assistant/tool/system.',
            'limitations':['Archive coverage, not lifetime/current usage or number of formal evaluations.',
                          'JSON bytes include metadata; referenced media bytes are not included.',
                          'No inference about the reported 1.89 GB seven-day export-size increase.',
                          'One snapshot only; other files are not assumed to be nonoverlapping.']}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input');p.add_argument('--out',required=True);a=p.parse_args()
    result=audit(a.input);Path(a.out).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
