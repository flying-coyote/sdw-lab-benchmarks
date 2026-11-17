#!/usr/bin/env python3
"""Step R (prereg section 8.1): run the as-built gate unchanged.

Imports the byte-identical, hash-checked copy under repro/d3fend-wall/ and sets only
mod.ROBOT to the pinned jar in tools/ (owner ruling 2026-11-17: no /tmp jar, no source
byte change). Wraps mod.reason so ROBOT's exit code is checked (the gate ignores it,
so a JVM crash would otherwise read as zero unsatisfiable classes). Outputs land next
to the copy in repro/d3fend-wall/, never in the hub. Exit 0 = reproduced, 1 = drift.
"""
import hashlib, importlib.util, io, json, os, re, sys
from contextlib import redirect_stdout

G = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE = os.path.join(G, "repro", "d3fend-wall", "ocsf_d3fend_corpus_validation.py")
MATRIX = os.path.join(G, "repro", "external-engagements", "ocsf-crosswalk-field-matrix.md")
JAR = os.path.join(G, "tools", "robot.jar")
PIN = {
    GATE: "8de6557d6189f68f4b5b9a9a5b23dbf4e24604c2b3ae07a7bb9a21c6c08da443",
    MATRIX: "8317d3ad57f0e9357a98b300dee007b53057c89f6139120553469f4e8a5be7cc",
    JAR: "16a73c074f3df359a7338a84b4e0788785fe06117f931bb9796e9619ea776105",
}
HUB_FP = os.path.expanduser("~/project1/02-projects/d3fend-wall/corpus_validation_fp.json")
HUB_FP_SHA = "91469aed356a4d0035c81fc3cbccfd3f15a9085ab86e849bdd44158318f5ec9e"
EXPECT = dict(rows=925, testable=364, classes=231, fired=15, injected=231, caught=231)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    for p, h in list(PIN.items()) + [(HUB_FP, HUB_FP_SHA)]:
        if sha(p) != h:
            sys.exit(f"HASH MISMATCH {p}: {sha(p)} != {h}")
    spec = importlib.util.spec_from_file_location("gate", GATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROBOT = JAR
    rcs = []   # (returncode, n_unsat, stderr says unsatisfiable)
    orig_reason = mod.reason
    real_sub = mod.subprocess
    last = {}

    class SubShim:   # records ROBOT's stderr; the gate's call itself is unchanged
        @staticmethod
        def run(*a, **k):
            p = real_sub.run(*a, **k)
            last["stderr"] = (p.stdout or "") + (p.stderr or "")
            return p

    def checked_reason(ttl):
        mod.subprocess = SubShim
        try:
            rc, unsat = orig_reason(ttl)
        finally:
            mod.subprocess = real_sub
        rcs.append((rc, len(unsat), "unsatisfiable" in re.sub(r"(?m)^WARNING.*$", "", last.get("stderr", "")).lower(),
                    re.sub(r"(?m)^WARNING.*\n?", "", last.get("stderr", ""))[-400:]))
        return rc, unsat
    mod.reason = checked_reason

    buf = io.StringIO()
    with redirect_stdout(buf):
        ok = mod.selfcheck()
        classes = mod.corpus() if ok else {}
        if ok:
            mod.inject(classes)
    out = buf.getvalue()
    print(out)

    got = {}
    m = re.search(r"rows parsed: (\d+) .* testable \(both\): (\d+)", out)
    if m:
        got["rows"], got["testable"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"distinct testable mapping-classes: (\d+)", out)
    if m:
        got["classes"] = int(m.group(1))
    m = re.search(r"gate fired on \(would-fail-build\): (\d+)", out)
    if m:
        got["fired"] = int(m.group(1))
    m = re.search(r"injected type-crossing corruptions: (\d+)", out)
    if m:
        got["injected"] = int(m.group(1))
    m = re.search(r"caught by the gate \(unsatisfiable\): (\d+)", out)
    if m:
        got["caught"] = int(m.group(1))

    here_fp = json.load(open(os.path.join(os.path.dirname(GATE), "corpus_validation_fp.json")))
    hub_fp = json.load(open(HUB_FP))
    same_names = sorted(here_fp["fired"]) == sorted(hub_fp["fired"])
    checks = {
        "selfcheck_clean": bool(ok),
        # ROBOT 1.9.x exits 1 after writing --dump-unsatisfiable when unsat classes exist;
        # anything else (non-zero with no unsat, or no "unsatisfiable" in stderr) is a crash.
        "robot_exit_codes_explained": bool(rcs) and all(
            (rc == 0 and n == 0) or (rc == 1 and n > 0 and said) for rc, n, said, _ in rcs),
        "fired_names_match_hub_fp_json": same_names,
        **{k: got.get(k) == v for k, v in EXPECT.items()},
    }
    report = {"expected": EXPECT, "got": got, "robot_calls": [{"rc": rc, "n_unsat": n, "stderr_says_unsatisfiable": said, "stderr_tail": t} for rc, n, said, t in rcs],
              "checks": checks, "pass": all(checks.values()),
              "jar_sha256": PIN[JAR]}
    print(json.dumps(report, indent=1))
    json.dump(report, open(os.path.join(G, "results", "step-r-reproduction.json"), "w"), indent=1)
    sys.exit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
