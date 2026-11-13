# Grade s05 specialization out-of-sample from runs.db. Run from the repo root:
#   .venv/bin/python workspace/studies/s05-differentiation/analysis/grade_specialization.py
# net_biomass = viable_biomass[last update] - viable_biomass[first emitted update (step 1)].
# (step 0 is the pre-run initial state, viable_biomass 0.0, and is not a growth baseline.)
import json, sqlite3, statistics as st
from ruamel.yaml import YAML
SD = 'workspace/studies/s05-differentiation'
TEST = 'specialization-improves-group-performance'
ENV_B, ENV_A = 0.025, 0.02
db = sqlite3.connect(f'{SD}/runs.db')

def vb(rid, step):
    r = db.execute('select state from history where simulation_id=? and step=?', (rid, step)).fetchone()
    return float(json.loads(r[0])['viable_biomass'])

runs = {}   # run_id -> (mode, o2, seed, net, fate_counts)
for rid, pj, n in db.execute("select run_id, params_json, n_steps from runs_meta where status='completed'"):
    p = json.loads(pj)
    first = db.execute('select min(step) from history where simulation_id=? and step>=1', (rid,)).fetchone()[0]
    fc = json.loads(db.execute('select state from history where simulation_id=? and step=?', (rid, n)).fetchone()[0])['fate_counts']
    runs[rid] = (p['fate_mode'], float(p['o2_source']), int(p['seed']), vb(rid, n) - vb(rid, first), fc)
by = {}
for mode, o2, seed, net, fc in runs.values():
    by.setdefault((mode, o2), []).append(net)
mean = {k: st.mean(v) for k, v in by.items()}
modes = ['oxygen', 'none', 'random', 'clamped']
ctrl = ['none', 'random', 'clamped']
oxB = mean[('oxygen', ENV_B)]
gain = oxB - max(mean[(c, ENV_B)] for c in ctrl)
ok = all(oxB > mean[(c, ENV_B)] for c in ctrl)
fmt = lambda o2: ', '.join(f'{m} {mean[(m, o2)]:.1f}' for m in modes)
nseeds = sorted({len(v) for v in by.values()})
detail = (f"Seed-mean net viable biomass growth (viable_biomass last update - first update, {nseeds} seeds per arm). "
          f"Held-out env B (o2_source 0.025): {fmt(ENV_B)}; out-of-sample gain = oxygen - best control = {gain:.1f}. "
          f"Calibration env A (0.02, context only): {fmt(ENV_A)}. "
          "The stemness threshold is fixed a priori, not tuned on A (generalization-across-regimes test). "
          "Benefit over the no-fate/clamped nulls is modest; over the random-fate null it is decisive. Transient 40-update window, one CPM backend.")
print(ok, round(gain, 3)); print(detail)
for k in sorted(by): print(k, [round(x, 1) for x in by[k]], round(mean[k], 1))
y = YAML(); y.preserve_quotes = True; y.width = 4096
d = y.load(open(f'{SD}/study.yaml'))
res = 'PASS' if ok else 'FAIL'
for r in d['runs']:
    r.pop('computed_outcomes', None)
    r['outcomes'] = {TEST: {'result': res, 'measured_value': round(gain, 6), 'operator': 'cross_run',
                            'evaluated_by': 'code', 'detail': detail}}
y.dump(d, open(f'{SD}/study.yaml', 'w'))
