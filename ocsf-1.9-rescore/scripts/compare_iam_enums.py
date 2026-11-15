"""Post-hoc (not pre-registered): compare activity_id enums of account_change and user_management in the
pinned 1.9.0 export (and account_change in 1.8.0), matching captions after a stated normalisation:
lowercase, singularise each word ('ies'->'y', trailing 's' dropped), and reorder 'MFA Factor Enable'/'Enable MFA Factors' style captions by
sorting words. Writes results/iam-enum-compare.json."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocsf_full as F  # noqa: E402

def _sing(w):
    return w[:-3] + "y" if w.endswith("ies") else (w[:-1] if w.endswith("s") and not w.endswith("ss") else w)

def norm(c):
    return " ".join(sorted(_sing(w) for w in c.lower().split()))

def enum(schema, cls):
    return {int(k): v["caption"] for k, v in schema["classes"][cls]["attributes"]["activity_id"]["enum"].items()}

s19, _ = F.load_export("1.9.0"); s18, _ = F.load_export("1.8.0")
ac19, um19, ac18 = enum(s19, "account_change"), enum(s19, "user_management"), enum(s18, "account_change")
um_by = {norm(c): i for i, c in um19.items()}
rows = []
for i, c in sorted(ac19.items()):
    if i in (0, 99):
        continue
    j = um_by.get(norm(c))
    rows.append({"account_change_id": i, "account_change_caption": c, "user_management_id": j,
                 "user_management_caption": um19.get(j), "same_integer": i == j,
                 "user_management_caption_at_same_integer": um19.get(i)})
out = {"account_change_1.9.0_equals_1.8.0": ac19 == ac18, "account_change_1.9.0": ac19, "user_management_1.9.0": um19,
       "rows": rows, "matched": sum(r["user_management_id"] is not None for r in rows),
       "same_integer": [r["account_change_caption"] for r in rows if r["same_integer"]]}
json.dump(out, open(os.path.join(F.ROOT, "results", "iam-enum-compare.json"), "w"), indent=1, sort_keys=True)
for r in rows: print(r)
print("ac 1.9.0 == ac 1.8.0:", out["account_change_1.9.0_equals_1.8.0"], "matched", out["matched"], "of", len(rows), "same integer:", out["same_integer"])
