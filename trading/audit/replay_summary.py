import json,sys,datetime as dt
from zoneinfo import ZoneInfo
UK=ZoneInfo('Europe/London'); u=lambda t: dt.datetime.fromtimestamp(float(t),UK).strftime('%H:%M') if t else '-'
R=json.load(open(sys.argv[1]+'/replay.json'))
SC=[('03:25',1794367517),('05:03',1794373382),('14:37',1794407824),('15:19',1794410390),('16:27',1794414429),('17:27',1794418072)]
def cat(b):
    if b=='ENTRY': return 'PASSED'
    if b.startswith('missing setup'): return 'missing setup'
    if 'before setup completed' in b: return 'broke before completion'
    if b.startswith('R:R'): return 'R:R<2'
    if b.startswith('expired: zone never'): return 'no retest'
    if b.startswith('expired: no conf'): return 'no confirmation'
    if b.startswith('invalidated'): return 'invalidated before entry'
    if b.startswith('conflict'): return 'opposite break'
    if b.startswith('zone filled'): return 'zone filled'
    if b.startswith('late: TP1'): return 'late: TP1 first'
    if b.startswith('late: conf'): return 'late: beyond worst fill'
    if b.startswith('open'): return 'still waiting'
    return b
var=sys.argv[2] if len(sys.argv)>2 else 'live'
L=[x for x in R if x.get('variant')==var and not x.get('data')]
for scope in ('shortlisted','other'):
    S=[x for x in L if (x['scope']=='shortlisted')==(scope=='shortlisted')]
    print(f'== {var} | scope {scope}')
    for plan in 'AB':
        for d in ('bull','bear'):
            rows=[x for x in S if x['plan']==plan and x['dir']==d]
            inc=sum(1 for x in rows if x.get('group')=='n/a')
            for g in ('main','countertrend'):
                c={}
                for x in rows:
                    if x.get('group')==g: c[cat(x['block'])]=c.get(cat(x['block']),0)+1
                print(f"  {plan} {'L' if d=='bull' else 'S'} [{g[:4]}] {sum(c.values())}: {dict(sorted(c.items(),key=lambda kv:-kv[1]))}")
            print(f"  {plan} {'L' if d=='bull' else 'S'} incomplete sweeps: {inc}")
E=[x for x in L if x['block']=='ENTRY']
print('ENTRIES',len(E))
for x in sorted(E,key=lambda x:x['entry_t']):
    prev=[n for n,t in SC if t<=x['entry_t']]; nxt=[n for n,t in SC if t>x['entry_t']]
    print(f"  {x['sym']} {x['plan']} {'long' if x['dir']=='bull' else 'short'} [{x['group']}] {x['scope']} | ready {u(x['Tc'])} zone {x['zone'][0]:.6g}-{x['zone'][1]:.6g} | conf {u(x['conf']['t'])} close {x['conf']['close']:.6g} vs lvl {x['conf']['level']:.6g} | entry {u(x['entry_t'])} @{x['entry']:.6g} ({x['entry_how']}) W {x['worst_fill']:.6g} SL {x['stop']:.6g} TP {x['tp1']:.6g}/{x['tp2']:.6g} | {x['result']} {x['netR']}R | between scans {prev[-1] if prev else 'start'} and {nxt[0] if nxt else 'now'}")
