"""R1: hosted one-take rehearsal evidence.

Runs the exact judged demo sequence against the deployed Cloud Run service,
three consecutive times, capturing elapsed time, diagnosis source, model, and
end states for both locked workflows. Prints a pass/fail table.

Usage: .venv/bin/python scripts/rehearse_hosted.py [BASE_URL] [--runs N]
"""
import argparse
import sys
import time

import requests

BASE = "https://fleetpilot-118750462659.us-central1.run.app"
TIMEOUT = 90  # per request; Gate 4 showed 3-7s diagnoses


def check(label: str, cond: bool, detail: str) -> bool:
    print(f"    [{'PASS' if cond else 'FAIL'}] {label}: {detail}")
    return cond


def rehearsal(base: str, idx: int) -> bool:
    print(f"\n=== Rehearsal {idx} ===")
    ok = True
    t_all = time.time()

    # Scene 1: queue hang -> one RCA -> safe auto-fix -> 0 alerts
    t0 = time.time()
    r = requests.post(f"{base}/api/scenario/queue_hang", timeout=TIMEOUT).json()
    t_q = time.time() - t0
    src = r["last_summary"].get("diagnosis_source")
    ok &= check("queue diagnosis", src == "gemini",
                f"source={src} model={r['health']['model']} {t_q:.1f}s")
    ok &= check("queue alerts cleared",
                r["fleet"]["alerts_open"] == 0,
                f"alerts_open={r['fleet']['alerts_open']} "
                f"devices={r['fleet']['devices']}")
    jobs = r["evidence"]["print_jobs"]
    released = sum(1 for j in jobs if j.get("status") == "released")
    quarantined_jobs = sum(1 for j in jobs if j.get("status") == "quarantined")
    ok &= check("job backlog released",
                len(jobs) == 30 and released == 29 and quarantined_jobs == 1,
                f"{released} released, {quarantined_jobs} quarantined "
                f"of {len(jobs)}")
    ok &= check("no fallback flag", not r["health"]["fallback_active"],
                f"reason={r['health']['fallback_reason']}")

    # Scene 2: guarded firmware rollout -> approval -> 5-device pilot abort
    t0 = time.time()
    r = requests.post(f"{base}/api/scenario/firmware_push_freezes",
                      timeout=TIMEOUT).json()
    t_f = time.time() - t0
    src = r["last_summary"].get("diagnosis_source")
    ok &= check("firmware diagnosis", src == "gemini",
                f"source={src} model={r['health']['model']} {t_f:.1f}s")
    ok &= check("human gate engaged", len(r["pending_approvals"]) == 1,
                f"pending={len(r['pending_approvals'])}")
    ok &= check("run isolation", r["run_id"] != previous_run.get("id"),
                f"run_id={r['run_id']}")
    previous_run["id"] = r["run_id"]
    approval_id = r["pending_approvals"][0]["id"]

    t0 = time.time()
    r = requests.post(f"{base}/api/approve/{approval_id}",
                      timeout=TIMEOUT).json()
    rep = r.get("rollout_report") or {}
    ok &= check("pilot scope", rep.get("pilot_size") == 5,
                f"pilot_size={rep.get('pilot_size')}")
    ok &= check("guarded outcome",
                rep.get("pilot_completed") == 2
                and len(rep.get("quarantined", [])) == 3
                and rep.get("outcome") == "aborted",
                f"completed={rep.get('pilot_completed')} "
                f"quarantined={len(rep.get('quarantined', []))} "
                f"outcome={rep.get('outcome')}")
    ok &= check("fleet untouched", rep.get("fleet_untouched") == 25,
                f"untouched={rep.get('fleet_untouched')}")
    ok &= check("no auto expansion", len(r["pending_approvals"]) == 0,
                f"pending={len(r['pending_approvals'])}")

    total = time.time() - t_all
    ok &= check("time budget", total < 195, f"total {total:.1f}s (<3:15)")
    return ok


previous_run: dict = {"id": None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default=BASE)
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()

    h = requests.get(f"{args.base}/health", timeout=TIMEOUT).json()
    print(f"Warmup: {args.base} rev={h.get('revision')} "
          f"model={h.get('model')} status={h.get('status')}")

    results = [rehearsal(args.base, i + 1) for i in range(args.runs)]
    passed = sum(results)
    print(f"\n{passed}/{args.runs} rehearsals passed (gate: 3/3)")
    return 0 if passed == args.runs else 1


if __name__ == "__main__":
    sys.exit(main())
