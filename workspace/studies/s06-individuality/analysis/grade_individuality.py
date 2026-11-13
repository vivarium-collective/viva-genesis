# Grade s06 individuality out-of-sample from runs.db. Run from the repo root:
#   .venv/bin/python workspace/studies/s06-individuality/analysis/grade_individuality.py
# response = mean_adhesion[last step] - mean_adhesion[first emitted step (1)]
# (step 0 is the pre-run zero state and is not a baseline.) Seeds 1-3 = train, 4-6 = held-out test.
import json, sqlite3, statistics as st
from pathlib import Path

SD = Path(__file__).resolve().parents[1]
TRAIN, TEST = (1, 2, 3), (4, 5, 6)
ARMS = [('clonal', True), ('clonal', False), ('mixed', True), ('mixed', False)]
KEYS = ('response', 'heritability', 'among_group', 'within_group', 'mean_toughness')


def _state(db, rid, step):
    return json.loads(db.execute('select state from history where simulation_id=? and step=?', (rid, step)).fetchone()[0])


def collect(db_path=None):
    """Return {(clonality, selection, seed): metrics dict} for completed runs."""
    db = sqlite3.connect(str(db_path or SD / 'runs.db'))
    out = {}
    for rid, pj, n in db.execute("select run_id, params_json, n_steps from runs_meta where status='completed'"):
        p = json.loads(pj)
        first = db.execute('select min(step) from history where simulation_id=? and step>=1', (rid,)).fetchone()[0]
        a, b = _state(db, rid, first), _state(db, rid, n)
        out[(p['clonality'], bool(p['selection']), int(p['seed']))] = {
            'response': b['mean_adhesion'] - a['mean_adhesion'], 'heritability': b['heritability'],
            'among_group': b['among_group'], 'within_group': b['within_group'], 'mean_toughness': b['mean_toughness']}
    return out


def grade(db_path=None):
    runs = collect(db_path)
    arms = {}
    for split, seeds in (('train', TRAIN), ('test', TEST)):
        for arm in ARMS:
            rows = [runs[arm + (s,)] for s in seeds if arm + (s,) in runs]
            arms[(split,) + arm] = {'n': len(rows), **{k: (st.mean(r[k] for r in rows) if rows else None) for k in KEYS}}
    t = lambda c, s: arms[('test', c, s)]
    primary = (t('clonal', True)['response'] > t('clonal', False)['response']) and t('clonal', True)['response'] > 0
    secondary = (t('clonal', True)['heritability'] > t('mixed', True)['heritability']) and \
                (t('mixed', True)['response'] < t('clonal', True)['response'])
    lines = []
    for split in ('train', 'test'):
        for c, s in ARMS:
            m = arms[(split, c, s)]
            lines.append(f"{split} {c}-{'sel' if s else 'drift'} (n={m['n']}): response {m['response']:.4f}, heritability {m['heritability']:.3f}, "
                         f"among {m['among_group']:.4f}, within {m['within_group']:.4f}, toughness {m['mean_toughness']:.3f}")
    detail = (f"Out-of-sample (test seeds 4-6) primary criterion (clonal-sel response > clonal-drift and > 0): {primary}; "
              f"secondary (clonal heritability > mixed and mixed-sel response < clonal-sel): {secondary}. " + ' | '.join(lines))
    return {'verdict': primary, 'secondary': secondary, 'arms': arms, 'detail': detail}


def write_outcomes(r, study_yaml=None):
    """Author the primary behavior-test outcome into study.yaml runs (mirrors the S05
    grader). The out-of-sample primary criterion result becomes the test PASS/FAIL so the
    verdict is backed by a recorded outcome, not a SKIP."""
    from ruamel.yaml import YAML
    TESTNAME = 'selection-drives-individuality'
    res = 'PASS' if r['verdict'] else 'FAIL'
    margin = round(r['arms'][('test', 'clonal', True)]['response']
                   - r['arms'][('test', 'clonal', False)]['response'], 6)
    y = YAML(); y.preserve_quotes = True; y.width = 4096
    sy = Path(study_yaml or SD / 'study.yaml')
    d = y.load(open(sy))
    for run in d.get('runs', []) or []:
        run.pop('computed_outcomes', None)
        run['outcomes'] = {TESTNAME: {'result': res, 'measured_value': margin,
                                      'operator': 'cross_run', 'evaluated_by': 'code',
                                      'detail': r['detail']}}
    y.dump(d, open(sy, 'w'))
    return res, margin


if __name__ == '__main__':
    r = grade()
    print(r['verdict'], r['secondary'])
    print(r['detail'])
    for k, v in r['arms'].items():
        print(k, {a: (round(b, 4) if isinstance(b, float) else b) for a, b in v.items()})
    print('wrote outcomes:', *write_outcomes(r))
