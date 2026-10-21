"""AC-block run scheduler (2026-10-19).

Works through output/_ac/queue.json one job at a time on CPU slot A (logical CPUs 0-15), under the
user's resource cap: ALL bot solves together <= 50 % CPU (33 of 66 logical CPUs) and <= 50 % RAM
(96 of 192 GB).  The parallel Claude session uses slot B (CPUs 16-32); this scheduler never touches B.

A job is launched only when
  (a) no scenario_runner process is currently pinned to / running on slot A,
  (b) bot RAM (sum of RSS of all scenario_runner python processes, any session) + RAM_PER_JOB <= RAM_CAP,
  (c) the job's tag has no result yet (meta.json) and is not marked running/done in queue.json.
The queue file is re-read every cycle, so jobs can be appended/reordered while this runs.
Launch = scripts/paper_2/ac_run.sh <tag> <scenario> <warmstart> KEY=VAL...  (isolated output/_ac/<tag>/),
then the new python solve process gets affinity = slot A.  Every event is one line in output/_ac/scheduler.log.
"""
import json, os, subprocess, sys, time
from datetime import datetime
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "output" / "_ac" / "queue.json"
LOG = ROOT / "output" / "_ac" / "scheduler.log"
SLOT_A = list(range(0, 16))
RAM_CAP_GB = 96.0
RAM_PER_JOB_GB = 45.0
CYCLE_S = 120


def log(msg):
    line = f"{datetime.now():%F %T} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def solves():
    out = []
    for p in psutil.process_iter(["pid", "cmdline", "memory_info"]):
        try:
            cl = " ".join(p.info["cmdline"] or [])
            if "scenario_runner" in cl and "-s " in cl:
                out.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return out


def slot_a_busy(sol):
    for p in sol:
        try:
            if set(p.cpu_affinity()) & set(SLOT_A) and len(p.cpu_affinity()) <= 20:
                return True
        except psutil.Error:
            pass
    return False


def bot_ram_gb(sol):
    """RAM of ALL big python processes (any session, any launcher) -- the 2026-10-21 check showed the
    other session's solve was missed by the cmdline filter above (104 GB vs the 96 GB cap)."""
    tot = 0
    for p in psutil.process_iter(["memory_info", "name"]):
        try:
            if "python" in (p.info["name"] or "").lower() and p.info["memory_info"]                     and p.info["memory_info"].rss > 8 * 2**30:
                tot += p.info["memory_info"].rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return tot / 2**30


def load_queue():
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def save_queue(q):
    QUEUE.write_text(json.dumps(q, indent=2), encoding="utf-8")


def done(job):
    d = ROOT / "output" / "_ac" / job["tag"] / "paper2_runs"
    return any(d.glob("*/meta.json"))


def launch(job):
    args = ["bash", "scripts/paper_2/ac_run.sh", job["tag"], job["scenario"], job.get("warmstart", "-")]
    args += [f"{k}={v}" for k, v in job.get("env", {}).items()]
    env = dict(os.environ, AC_THREADS=str(job.get("threads", 16)))
    outf = open(ROOT / "output" / "_ac" / f"{job['tag']}.out", "w", encoding="utf-8")
    proc = subprocess.Popen(args, cwd=ROOT, env=env, stdout=outf, stderr=subprocess.STDOUT)
    # pin the python solve process as soon as it exists (affinity is inherited by its threads)
    for _ in range(120):
        time.sleep(2)
        try:
            for ch in psutil.Process(proc.pid).children(recursive=True):
                if "scenario_runner" in " ".join(ch.cmdline()):
                    ch.cpu_affinity(SLOT_A)
                    return proc, ch.pid
        except psutil.Error:
            pass
    return proc, None


def main():
    log(f"scheduler start (RAM cap {RAM_CAP_GB} GB, slot A = CPUs 0-15, {RAM_PER_JOB_GB} GB reserved per job)")
    running = {}  # tag -> Popen
    while True:
        try:
            q = load_queue()
        except Exception as e:  # noqa: BLE001
            log(f"queue read error: {e}")
            time.sleep(CYCLE_S)
            continue
        for tag, pr in list(running.items()):
            if pr.poll() is not None:
                log(f"FINISHED {tag} rc={pr.returncode}")
                for j in q:
                    if j["tag"] == tag:
                        j["state"] = "done" if done(j) else "failed"
                save_queue(q)
                del running[tag]
        pending = [j for j in q if j.get("state", "queued") == "queued" and not done(j)]
        if not pending and not running:
            log("queue empty and nothing running -> scheduler exits (ALL RUNS DONE)")
            return
        sol = solves()
        ram = bot_ram_gb(sol)
        if ram > RAM_CAP_GB:
            log(f"ALERT bot RAM {ram:.0f} GB > cap {RAM_CAP_GB:.0f} GB")
        if pending and not running and not slot_a_busy(sol) and ram + RAM_PER_JOB_GB <= RAM_CAP_GB:
            job = pending[0]
            log(f"LAUNCH {job['tag']} ({job['scenario']}) bot RAM before = {ram:.0f} GB")
            proc, pid = launch(job)
            job["state"] = "running"
            save_queue(q)
            running[job["tag"]] = proc
            log(f"STARTED {job['tag']} python PID {pid} pinned to CPUs 0-15")
        elif pending:
            log(f"wait: next={pending[0]['tag']} slotA_busy={slot_a_busy(sol)} botRAM={ram:.0f}GB "
                f"solves={len(sol)} pending={len(pending)}")
        time.sleep(CYCLE_S)


if __name__ == "__main__":
    main()
