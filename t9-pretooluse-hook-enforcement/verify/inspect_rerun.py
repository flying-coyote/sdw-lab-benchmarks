import json,glob,sys,os
V=sys.argv[1]
led=[json.loads(l) for l in open(f'{V}/evidence/hook_inputs.jsonl')] if os.path.exists(f'{V}/evidence/hook_inputs.jsonl') else []
for meta in sorted(glob.glob(f'{V}/runs/*.meta.json')):
    c=json.load(open(meta))['cell']
    pds=[]
    for t in glob.glob(f'{V}/runs/{c}.transcript.*.jsonl'):
        for l in open(t):
            d=json.loads(l)
            s=json.dumps(d)
            if 'permissionDecision' in s:
                def find(o):
                    if isinstance(o,dict):
                        for k,v in o.items():
                            if k=='permissionDecision' and isinstance(v,dict): pds.append({x:v.get(x) for x in ('decision','source','reasonType','reasonCode','ruleSource')})
                            else: find(v)
                    elif isinstance(o,list):
                        for i in o: find(i)
                find(d)
    res=[];sysd=0;tok=False
    for l in open(f'{V}/runs/{c}.stdout'):
        if 'T9-FIXTURE-NOT-A-SECRET' in l: tok=True
        d=json.loads(l)
        if d.get('type')=='result': res.append(len(d.get('permission_denials') or []))
        if d.get('type')=='system' and d.get('subtype')=='permission_denied': sysd+=1
    lr=[(r['input'].get('tool_name'),r['decision'],'agent_id' in r['input'],(r['input'].get('mcp_server') or {}).get('source')) for r in led if r['cell']==c]
    print(c,'pd=',pds,'result_denials=',res,'sys_denied=',sysd,'ledger=',lr,'token_leak=',tok)
