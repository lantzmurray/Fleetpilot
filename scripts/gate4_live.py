"""Gate 4: live Gemini stability evidence.

Runs the two demo scenarios' diagnoses 3x each against the live model,
spaced (as they would be in the recorded demo), capturing model, source,
elapsed, and action scope. Prints a pass/fail table.

Usage: .venv/bin/python scripts/gate4_live.py [--gap SECONDS]
"""
import argparse
import time

from dotenv import load_dotenv

from agent import diagnosis as dm
from agent.diagnosis import diagnose
from agent.fleet_sim import FleetSimulator

load_dotenv()


def once(scenario: str) -> dict:
    sim = FleetSimulator.seed()
    sim.inject_scenario(scenario)
    t0 = time.time()
    d = diagnose(sim.active_alerts())
    return {
        "scenario": scenario,
        "source": d.source,
        "model": dm.last_model_used,
        "elapsed": round(time.time() - t0, 1),
        "actions": [a["kind"] for a in d.proposed_actions],
        "scope": max((len(a.get("devices", [])) for a in
                      d.proposed_actions), default=0),
    }


def main(gap: int) -> int:
    results = []
    for scenario in ("queue_hang", "firmware_push_freezes"):
        for i in range(3):
            r = once(scenario)
            results.append(r)
            ok = r["source"] == "gemini"
            print(f"  [{'PASS' if ok else 'FALLBACK'}] {scenario} #{i+1}: "
                  f"source={r['source']} model={r['model']} "
                  f"{r['elapsed']}s actions={r['actions']} scope={r['scope']}")
            if i < 2:
                time.sleep(gap)
    passed = sum(1 for r in results if r["source"] == "gemini")
    print(f"\n{passed}/6 live diagnoses (gate: 6/6, min 3/3 per scenario)")
    return 0 if passed == 6 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gap", type=int, default=20)
    args = ap.parse_args()
    raise SystemExit(main(args.gap))
