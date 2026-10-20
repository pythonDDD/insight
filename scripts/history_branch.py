#!/usr/bin/env python3
"""Keep hourly snapshots on a data branch without rewriting source history."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "insight-data"
FILES = ("snapshot.json", "history.json")


def git(*args, input=None, check=True):
    return subprocess.run(["git", *args], cwd=ROOT, input=input, capture_output=True, text=True, check=check)


def restore():
    exists = git("ls-remote", "--exit-code", "--heads", "origin", BRANCH, check=False)
    if exists.returncode == 2:
        print("First run: no previous data branch.")
        return
    if exists.returncode:
        raise RuntimeError("Unable to check data branch. Restore aborted to protect history.")
    git("fetch", "origin", f"{BRANCH}:refs/remotes/origin/{BRANCH}", "--depth=1")
    for name in FILES:
        result = git("show", f"origin/{BRANCH}:{name}")
        payload = json.loads(result.stdout)
        if name == "history.json" and not isinstance(payload.get("snapshots"), list):
            raise ValueError("Invalid history")
        if name == "snapshot.json" and payload.get("schemaVersion") != 1:
            raise ValueError("Invalid snapshot")
        (ROOT / "site/data" / name).write_text(result.stdout, encoding="utf-8")
    print("Restored previous public observations.")


def save():
    tree_lines = []
    for name in FILES:
        p = ROOT / "site/data" / name
        if not p.is_file():
            raise RuntimeError(f"Missing {name}")
        sha = git("hash-object", "-w", str(p)).stdout.strip()
        tree_lines.append(f"100644 blob {sha}\t{name}")
    tree = git("mktree", input="\n".join(tree_lines) + "\n").stdout.strip()
    parent = git("rev-parse", "--verify", f"refs/remotes/origin/{BRANCH}", check=False)
    args = ["-c", "user.name=github-actions[bot]", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com", "commit-tree", tree]
    if parent.returncode == 0:
        args += ["-p", parent.stdout.strip()]
    snapshot = json.loads((ROOT / "site/data/snapshot.json").read_text(encoding="utf-8"))
    args += ["-m", f"Observe public markets {snapshot['generatedAt']}"]
    commit = git(*args).stdout.strip()
    # Normal fast-forward push; an unexpected concurrent writer is never overwritten.
    git("push", "origin", f"{commit}:refs/heads/{BRANCH}")
    print("Saved hourly observations to insight-data.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("restore", "save"):
        raise SystemExit("usage: history_branch.py restore|save")
    globals()[sys.argv[1]]()
