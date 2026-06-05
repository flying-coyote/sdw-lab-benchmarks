# BENCH-C OBDA arm (Ontop) — setup

The formal-rewrite arm: Ontop exposes the fidelity store as a virtual RDF graph and rewrites
SPARQL to SQL over DuckDB. Files here are the reproducible artifacts; the Ontop CLI is fetched
separately (it's large) and pointed at via `ONTOP_HOME`.

```bash
# one-time: fetch Ontop CLI 5.5.0 + the DuckDB JDBC driver
curl -sL -o ontop-cli.zip https://github.com/ontop/ontop/releases/download/ontop-5.5.0/ontop-cli-5.5.0.zip
python -c "import zipfile; zipfile.ZipFile('ontop-cli.zip').extractall('ontop-cli')"
curl -sL -o ontop-cli/jdbc/duckdb_jdbc.jar https://repo1.maven.org/maven2/org/duckdb/duckdb_jdbc/1.1.3/duckdb_jdbc-1.1.3.jar
# then, from the repo root (Store F must be built — see bench-a):
ONTOP_HOME=$PWD/ontop-cli python ocsf-semantic-query/run_obda.py
```

- `storef.obda` — OBDA mapping: process / api / session tables → RDF.
- `storef.ttl` — minimal OWL2QL ontology (classes + datatype properties).
- `a2.rq`, `a6.rq`, `a4.rq.template` — the SPARQL for the expressible adversary queries.

The five out-of-OWL2QL queries (A1/A3/A5/A7/A9 — aggregation, ordering, recursion) are recorded
by the runner as out-of-expressivity, which is the refusal-honesty boundary the arm measures.
