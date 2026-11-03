#!/usr/bin/env python3
"""Монитор для cron: запускает triage.py, печатает сводку только если есть новые письма.

NO_NEW -> агент не запускается (Hermes cron monitor-паттерн).
Настройки: --config FILE (иначе config.json рядом с монитором; пусто = без файла).
Монитору нужен только workdir — папка проекта, где лежит triage.py со своим config.json.
"""
import argparse, json, os, subprocess, sys
from datetime import date

ap = argparse.ArgumentParser()
ap.add_argument("--config", default=None, help="путь к config.json")
args = ap.parse_args()

HERE = os.path.dirname(os.path.abspath(__file__))
cfg_path = args.config or os.environ.get("TRIAGE_CONFIG") or os.path.join(HERE, "config.json")
cfg = {}
if os.path.exists(cfg_path):
    try:
        cfg = json.load(open(cfg_path, encoding="utf-8")) or {}
    except Exception as e:
        print(f"[warn] не удалось прочитать {cfg_path} ({e})", file=sys.stderr)

WORK = cfg.get("workdir") or HERE
os.chdir(WORK)

# triage.py сам читает настройки (свой config.json) и ключ — монитору подставлять нечего
r = subprocess.run([sys.executable, os.path.join(WORK, "triage.py")],
                   capture_output=True, text=True, timeout=900)
out = (r.stdout or "") + (r.stderr or "")

# сколько строк в сегодняшнем jsonl
today = date.today().isoformat()
jsonl = os.path.join(WORK, "output", f"triage_{today}.jsonl")
n = sum(1 for _ in open(jsonl, encoding="utf-8")) if os.path.exists(jsonl) else 0

if "разобрано 0" in out and n == 0:
    print("NO_NEW")
else:
    print(out)
    summary = os.path.join(WORK, "output", f"summary_{today}.md")
    if os.path.exists(summary):
        print()
        print(open(summary, encoding="utf-8").read())
