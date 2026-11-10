#!/usr/bin/env python3
"""T1-shadow-ai-discovery: one full lab run (containers up, capture, activity, osquery, teardown).

Usage: run_lab.py <run_id>    -> results/run<id>/{eth0.pcap, any.pcap, dnsmasq.log, activity.log, osquery/*.json, timing.json}
stdlib only. All timing with time.monotonic(). Containers pinned to --cpuset-cpus 0-3.
"""
import json, os, pathlib, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent
RUN = sys.argv[1]
OUT = HERE / "results" / f"run{RUN}"
(OUT / "osquery").mkdir(parents=True, exist_ok=True)
HOME = HERE / "fixtures" / "endpoint-home"
CPUS = "0-3"
NET = "t1lab"
timing = {}
cmdlog = open(HERE / "COMMANDS.log", "a")


def log(msg):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} run{RUN} {msg}"
    print(line, flush=True)
    cmdlog.write(line + "\n"); cmdlog.flush()


def sh(cmd, check=True, capture=False, timeout=600):
    log("$ " + " ".join(cmd))
    r = subprocess.run(cmd, check=False, capture_output=capture, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise SystemExit(f"command failed ({r.returncode}): {' '.join(cmd)}\n{r.stderr if capture else ''}")
    return r


def timed(name, fn):
    t0 = time.monotonic()
    out = fn()
    timing[name] = round(time.monotonic() - t0, 3)
    return out


def teardown():
    subprocess.run(["docker", "rm", "-f", "t1-endpoint", "t1-dns", "t1-cap", "t1-cap-any", "t1-peer"], capture_output=True)
    subprocess.run(["docker", "network", "rm", NET], capture_output=True)


teardown()
sh(["docker", "network", "create", NET])
sh(["docker", "run", "-d", "--name", "t1-dns", "--network", NET, "--cpuset-cpus", CPUS, "t1-sidecar:local",
    "dnsmasq", "-k", "--log-queries", "--log-facility=-", "--no-resolv", "--server=192.168.65.7", "--cache-size=0"])
dns_ip = sh(["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", "t1-dns"], capture=True).stdout.strip()
sh(["docker", "run", "-d", "--name", "t1-endpoint", "--network", NET, "--dns", dns_ip, "--cpuset-cpus", CPUS, "--memory", "6g",
    "-v", f"{HOME}:/home/dev", "-v", "/usr/local/bin/ollama:/usr/local/bin/ollama:ro", "-v", "/usr/local/lib/ollama:/usr/local/lib/ollama:ro",
    "-v", f"{HERE}/fixtures/activity.sh:/opt/activity.sh:ro", "t1-endpoint:local"])
ep_ip = sh(["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", "t1-endpoint"], capture=True).stdout.strip()
sh(["docker", "run", "-d", "--name", "t1-peer", "--network", NET, "--dns", dns_ip, "--cpuset-cpus", CPUS, "python:3.12-slim", "sleep", "infinity"])
sh(["docker", "run", "-d", "--name", "t1-cap", "--network", "container:t1-endpoint", "--cap-add", "NET_ADMIN", "--cap-add", "NET_RAW", "--cpuset-cpus", CPUS,
    "-v", f"{OUT}:/cap", "t1-sidecar:local", "tcpdump", "-i", "eth0", "-s", "0", "-U", "-w", "/cap/eth0.pcap"])
sh(["docker", "run", "-d", "--name", "t1-cap-any", "--network", "container:t1-endpoint", "--cap-add", "NET_ADMIN", "--cap-add", "NET_RAW", "--cpuset-cpus", CPUS,
    "-v", f"{OUT}:/cap", "t1-sidecar:local", "tcpdump", "-i", "any", "-s", "0", "-U", "-w", "/cap/any.pcap"])
time.sleep(2)
log(f"lab up: dns={dns_ip} endpoint={ep_ip}")

# activity inside the endpoint (as dev), then peer calls
timed("activity_endpoint", lambda: sh(["docker", "exec", "-u", "1000:1000", "-e", "HOME=/home/dev", "t1-endpoint", "bash", "/opt/activity.sh"], timeout=900))
peer_py = f"""
import json, urllib.request, urllib.error
EP = "{ep_ip}"
def call(label, url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {{}}, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=120) as r: print(label, r.status, flush=True)
    except urllib.error.HTTPError as e: print(label, e.code, flush=True)
    except Exception as e: print(label, "ERR", type(e).__name__, flush=True)
call("S1 tags", f"http://{{EP}}:11434/api/tags")
call("S1 generate", f"http://{{EP}}:11434/api/generate", json.dumps({{"model":"tinyllama","prompt":"Say hi.","stream":False,"options":{{"num_predict":8,"num_thread":4}}}}).encode(), {{"Content-Type":"application/json"}})
call("S2 chat", f"http://{{EP}}:8000/v1/chat/completions", json.dumps({{"model":"lab-stub-model-7b-instruct","messages":[{{"role":"user","content":"hi"}}]}}).encode(), {{"Content-Type":"application/json","Authorization":"Bearer sk-lab-dummy-0000"}})
call("C1 benign", f"http://{{EP}}:8080/")
"""
r = timed("activity_peer", lambda: sh(["docker", "exec", "t1-peer", "python3", "-c", peer_py], capture=True, timeout=400))
(OUT / "peer.log").write_text(r.stdout + r.stderr)
log("peer: " + r.stdout.replace("\n", " | "))

# osquery while the processes are still running (root inside the container)
queries = json.loads((HERE / "fixtures" / "osquery_queries.json").read_text())
osq_t = {}
for name, sql in queries.items():
    t0 = time.monotonic()
    r = sh(["docker", "exec", "-e", "HOME=/root", "t1-endpoint", "osqueryi", "--json", "--logger_min_status=2", sql], check=False, capture=True, timeout=300)
    osq_t[name] = round(time.monotonic() - t0, 3)
    (OUT / "osquery" / f"{name}.json").write_text(r.stdout if r.returncode == 0 else json.dumps({"error": r.stderr, "rc": r.returncode}))
    if r.returncode != 0:
        log(f"osquery {name} FAILED rc={r.returncode}: {r.stderr.strip()[:300]}")
timing["osquery_per_query"] = osq_t
timing["osquery_total"] = round(sum(osq_t.values()), 3)

# versions inside the endpoint
ver = sh(["docker", "exec", "-e", "HOME=/root", "t1-endpoint", "sh", "-c", "curl --version | head -1; python3 --version; osqueryi --version; ollama --version 2>&1 | tail -1; cat /etc/os-release | head -2"], capture=True, check=False)
(OUT / "versions-endpoint.txt").write_text(ver.stdout + ver.stderr)

# stop capture, collect logs, tear down
time.sleep(3)
sh(["docker", "stop", "-t", "3", "t1-cap", "t1-cap-any"], check=False)
(OUT / "dnsmasq.log").write_text(sh(["docker", "logs", "t1-dns"], capture=True).stdout + sh(["docker", "logs", "t1-dns"], capture=True).stderr)
for f in ["activity.log", "ollama.log", "stub.log", "benign8080.log", "pull.log", "gen.json"]:
    p = HOME / ".lab" / f
    if p.exists():
        (OUT / f).write_text(p.read_text(errors="replace"))
teardown()
(OUT / "timing.json").write_text(json.dumps(timing, indent=1))
log("run complete: " + json.dumps({k: v for k, v in timing.items() if k != 'osquery_per_query'}))
