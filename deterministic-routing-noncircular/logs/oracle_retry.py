import json, sys, time, duckdb
sys.path.insert(0, '.')
from oracle import render_duckdb
from ejs_queries import normalize
q = [x for x in json.load(open('queries/corpus.json'))['queries'] if x['id'] == 'join_3to4_09'][0]
c = duckdb.connect(); c.execute("SET memory_limit='24GB'; SET threads=8; SET temp_directory='/tmp/claude-1000/drn-duck-spill'")
t = time.time(); a = normalize(c.execute(render_duckdb(q['sql'])).fetchall())
p = 'results/oracle.json'; d = json.load(open(p)); d['answers'][q['id']] = a
d['retries'] = {q['id']: {"memory_limit": "24GB", "threads": 8, "reason": "OOM at 8GB in first oracle pass"}}
d['errors'].pop(q['id'], None); json.dump(d, open(p, 'w'), indent=1, sort_keys=True)
print('ok', len(a), a[:2], round(time.time() - t), 's (not a timing result)')
