#!/usr/bin/env python3
"""Full-chain Security Context map — Sankey builder.

Renders the controls-layer essay's whole chain as ONE picture, aggregated to a readable
grain and colored by `proxy_quality` so a viewer can SEE which joints are cheap:

    OCSF class ─②③─► D3FEND defense ─④─► ATT&CK tactic ─⑤'─► SCF domain

Every flow is built from real Security Context Graph edges (results-scf-local/, the
--with-scf build), aggregated; the link color is the hop's proxy_quality and the tooltip
carries its honesty note. The defense→ATT&CK joint (artifact_cooccurrence, intent-blind) is
colored to stand out — it is the cheapest joint in the chain, and the point of the map is
that you can see that.

SCF licensing: the terminal stage is SCF DOMAIN-level aggregate counts (derived statistics),
never raw mapping cells — publishable under CC-BY-ND. Run after `scg.py --with-scf`.

Output: securitydataworks/public/research/security-context-map.html (self-contained, light brand).
Usage: python3 build_chain_sankey.py
"""
import csv
import json
import os
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
GRAPH = HERE / "results-scf-local"          # the --with-scf build (local; SCF present)
P1 = Path(os.environ.get("SCG_PROJECT1", str(Path.home() / "project1" / "02-projects")))
WALL_COLUMNS = P1 / "d3fend-wall" / "data" / "wall_columns.csv"
OUT = (HERE / ".." / ".." / "securitydataworks" / "public" / "research"
       / "security-context-chain.html").resolve()

# proxy_quality -> (brand color, short label, honesty note). The artifact_cooccurrence
# joint is amber on purpose: it is the cheapest, intent-blind link in the chain.
PROXY = {
    "doc_link":              ("#5c8dc5", "documentation link", "OCSF↔D3FEND reciprocal hyperlinks (seeAlso/references) — not axioms, not per-record fields; a design-time map."),
    "ontology_axiom":        ("#6f9a4f", "ontology axiom",      "D3FEND event-class restriction tying the event to its digital-artifact participant."),
    "ontology_curated":      ("#7d9bb5", "ontology (curated)",  "D3FEND technique hand-tagged to the artifact it observes."),
    "artifact_cooccurrence": ("#c87d3f", "shared-artifact inference", "INTENT-BLIND (D3FEND #520): a defense and an attack touch the same artifact, so the defense COULD observe it — a possibility of coverage, not a guarantee."),
    "ctid_reroute":          ("#36608f", "CTID re-route",       "SCF→ATT&CK is CTID's NIST 800-53→ATT&CK mapping re-routed through SCF's own 800-53 crosswalk (uniform Intersects-With/strength-3); no independent SCF signal."),
}
STAGE_COLOR = {"ocsf": "#2c4f74", "defense": "#3f6f4f", "attack": "#8a5a2b", "scf": "#5a6b7d"}


def load_graph():
    nodes = {n["id"]: n for n in json.load(open(GRAPH / "nodes.json"))}
    edges = json.load(open(GRAPH / "edges.json"))
    out = defaultdict(list)
    for e in edges:
        out[e["src"]].append(e)
    return nodes, edges, out


def base_rollup():
    """leaf D3-id -> base technique name, and leaf def_tech name -> base, from the wall."""
    d3id2base, name2base, bases = {}, {}, set()
    for r in csv.DictReader(open(WALL_COLUMNS)):
        base = r["base_tech"].strip()
        bases.add(base)
        d3id2base[r["d3fend_id"].strip()] = base
        if r.get("def_tech"):
            name2base[r["def_tech"].strip()] = base
    return d3id2base, name2base, bases


def main():
    nodes, edges, out = load_graph()
    d3id2base, name2base, bases = base_rollup()

    def defense_base(nid):
        a = nodes.get(nid, {})
        d3 = a.get("d3fend_id")
        if d3 and d3 in d3id2base:
            return d3id2base[d3]
        lab = a.get("label", "")
        if lab in bases:
            return lab
        return name2base.get(lab, lab)  # observed-defense base names == wall base_tech

    # ---- stage maps ----
    # OCSF class -> events -> artifacts ; defense -observes-> artifacts (reverse)
    cls_events = defaultdict(set)
    event_arts = defaultdict(set)
    art_defenses = defaultdict(set)          # artifact -> {base defense}
    def_attacks = defaultdict(set)           # base defense -> {attack id}
    attack_tactic = {}                       # attack id -> tactic name
    attack_scf = defaultdict(set)            # attack id -> {scf_control id}
    scf_domain = {}                          # scf_control id -> domain name

    for nid, a in nodes.items():
        if a["ntype"] == "scf_control" and a.get("domain"):
            scf_domain[nid] = a["domain"]

    for e in edges:
        s, d, rel, pq = e["src"], e["dst"], e["rel"], e["proxy_quality"]
        sn, dn = nodes.get(s, {}), nodes.get(d, {})
        if sn.get("ntype") == "ocsf_class" and rel == "references":
            cls_events[s].add(d)
        elif sn.get("ntype") == "d3fend_event" and rel.startswith("event_"):
            event_arts[s].add(d)
        elif sn.get("ntype") == "defense" and rel.startswith("observes"):
            art_defenses[d].add(defense_base(s))
        elif sn.get("ntype") == "defense" and rel == "may_counter":
            def_attacks[defense_base(s)].add(d)
        elif rel == "in_tactic":
            attack_tactic[s] = dn.get("label", d.split("/")[-1])
        elif rel == "mitigated_by" and dn.get("ntype") == "scf_control":
            attack_scf[s].add(d)

    # ---- aggregate links (with proxy_quality) ----
    L1 = defaultdict(int)  # (ocsf_class, base_def) -> shared-artifact count   [doc_link]
    for cls, evs in cls_events.items():
        arts = set().union(*(event_arts[ev] for ev in evs)) if evs else set()
        def_hits = defaultdict(int)
        for art in arts:
            for bd in art_defenses.get(art, ()):
                def_hits[bd] += 1
        for bd, k in def_hits.items():
            L1[(nodes[cls]["label"], bd)] += k

    L2 = defaultdict(int)  # (base_def, tactic) -> attack count   [artifact_cooccurrence]
    for bd, atks in def_attacks.items():
        for atk in atks:
            tac = attack_tactic.get(atk)
            if tac:
                L2[(bd, tac)] += 1

    L3 = defaultdict(int)  # (tactic, scf_domain) -> count   [ctid_reroute]
    for atk, ctrls in attack_scf.items():
        tac = attack_tactic.get(atk)
        if not tac:
            continue
        for c in ctrls:
            dom = scf_domain.get(c)
            if dom:
                L3[(tac, dom)] += 1

    # ---- ECharts nodes + links ----
    def nid(stage, name):
        return {"ocsf": "OCSF · ", "defense": "D3FEND · ", "attack": "ATT&CK · ",
                "scf": "SCF · "}[stage] + name

    depth = {"ocsf": 0, "defense": 1, "attack": 2, "scf": 3}
    enodes, seen = [], set()

    def add(stage, name):
        n = nid(stage, name)
        if n not in seen:
            seen.add(n)
            enodes.append({"name": n, "depth": depth[stage],
                           "itemStyle": {"color": STAGE_COLOR[stage]}})
        return n

    elinks = []

    def link(a, b, val, pq):
        color, lab, note = PROXY[pq]
        elinks.append({"source": a, "target": b, "value": val,
                       "lineStyle": {"color": color, "opacity": 0.45},
                       "pq": lab, "note": note})

    for (cls, bd), v in sorted(L1.items()):
        link(add("ocsf", cls), add("defense", bd), v, "doc_link")
    for (bd, tac), v in sorted(L2.items()):
        link(add("defense", bd), add("attack", tac), v, "artifact_cooccurrence")
    for (tac, dom), v in sorted(L3.items()):
        link(add("attack", tac), add("scf", dom), v, "ctid_reroute")

    stats = {
        "ocsf_classes": sum(1 for n in enodes if n["depth"] == 0),
        "defenses": sum(1 for n in enodes if n["depth"] == 1),
        "tactics": sum(1 for n in enodes if n["depth"] == 2),
        "scf_domains": sum(1 for n in enodes if n["depth"] == 3),
        "links": len(elinks),
    }
    print("Sankey stages:", stats)

    legend = [{"pq": lab, "color": c, "note": note} for c, lab, note in PROXY.values()]
    html = render_html(enodes, elinks, legend, stats)
    echarts_js = (HERE / "vendor" / "echarts.min.js").read_text(encoding="utf-8")
    html = html.replace("/*__ECHARTS__*/", echarts_js)  # inline (no CDN/SRI dependency)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")


def render_html(enodes, elinks, legend, stats):
    data = json.dumps({"nodes": enodes, "links": elinks}, separators=(",", ":"))
    legend_html = "".join(
        f'<span class="lg"><i style="background:{l["color"]}"></i>{l["pq"]}'
        f'<span class="tip">{l["note"]}</span></span>' for l in legend)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Security Context map: schema → defense → offense → controls</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<script>/*__ECHARTS__*/</script>
<style>
:root{{--bg:#fff;--panel:#f4f6f8;--ink:#1f2933;--muted:#67768a;--teal:#2c4f74}}
html,body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 "DM Sans Variable","DM Sans",system-ui,sans-serif}}
.wrap{{max-width:1000px;margin:0 auto;padding:18px 20px 30px}}
h1{{font-size:19px;font-weight:600;margin:0 0 4px}}
p.sub{{color:var(--muted);margin:0 0 14px;font-size:13px}}
#chart{{width:100%;height:620px}}
.legend{{display:flex;flex-wrap:wrap;gap:14px;margin:6px 0 2px;font-size:12.5px;color:var(--muted)}}
.lg{{position:relative;cursor:default}}
.lg i{{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:5px;vertical-align:-1px}}
.lg .tip{{display:none;position:absolute;left:0;top:20px;z-index:5;width:300px;background:#fff;color:var(--ink);
  border:1px solid #e2e6ea;border-radius:8px;padding:9px 11px;box-shadow:0 8px 28px rgba(12,22,32,.14);font-size:12px;line-height:1.45}}
.lg:hover .tip{{display:block}}
.foot{{color:var(--muted);font-size:12px;margin-top:8px}}
.stat{{font-family:"JetBrains Mono",monospace;color:var(--teal)}}
</style></head>
<body><div class="wrap">
<h1>The Security Context map</h1>
<p class="sub">Schema → defense → offense → controls, one chain — and every joint colored by how cheap its proxy is.
Hover a flow for the hop's honesty note; hover a legend swatch for what that joint actually rests on.</p>
<div class="legend">{legend_html}</div>
<div id="chart"></div>
<p class="foot"><span class="stat">{stats['ocsf_classes']}</span> OCSF classes →
<span class="stat">{stats['defenses']}</span> D3FEND base techniques →
<span class="stat">{stats['tactics']}</span> ATT&amp;CK tactics →
<span class="stat">{stats['scf_domains']}</span> SCF domains.
The amber band (defense→offense) is the cheapest joint: a shared digital artifact says a defense
<em>could</em> observe an attack, not that it counters it. SCF shown at domain-grain (derived counts, CC-BY-ND).
Built from the Security Context Graph; numbers reconcile to the controls-layer essay.</p>
</div>
<script>
var D={data};
var color={{}};{("".join(f'color[{json.dumps(l["pq"])}]={json.dumps(l["color"])};' for l in legend))}
var chart=echarts.init(document.getElementById('chart'),null,{{renderer:'canvas'}});
chart.setOption({{
  backgroundColor:'transparent',
  textStyle:{{fontFamily:'"DM Sans Variable","DM Sans",system-ui,sans-serif'}},
  tooltip:{{trigger:'item',triggerOn:'mousemove',backgroundColor:'#fffffff2',borderColor:'#e2e6ea',
    textStyle:{{color:'#1f2933',fontSize:12}},extraCssText:'max-width:340px;white-space:normal;box-shadow:0 8px 28px rgba(12,22,32,.14);border-radius:8px',
    formatter:function(p){{
      if(p.dataType==='edge'){{return '<b>'+p.data.source+'</b> → <b>'+p.data.target+'</b><br>flow: '+p.data.value+
        '<br><span style="color:'+(color[p.data.pq]||'#666')+'">● '+p.data.pq+'</span><br><span style="color:#67768a">'+p.data.note+'</span>';}}
      return '<b>'+p.name+'</b>';}}}},
  series:[{{type:'sankey',data:D.nodes,links:D.links,draggable:false,
    nodeWidth:14,nodeGap:9,
    emphasis:{{focus:'adjacency'}},
    label:{{fontSize:11.5,color:'#1f2933',fontFamily:'"DM Sans Variable","DM Sans",system-ui,sans-serif'}},
    lineStyle:{{curveness:0.5}},
    levels:[{{depth:0,label:{{position:'right'}}}},{{depth:1}},{{depth:2}},{{depth:3,label:{{position:'left'}}}}]
  }}]
}});
window.addEventListener('resize',function(){{chart.resize();}});
</script>
</body></html>"""


if __name__ == "__main__":
    main()
