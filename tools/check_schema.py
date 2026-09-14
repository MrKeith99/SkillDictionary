#!/usr/bin/env python3
"""Validate dictionary and challenge files against the JSON Schemas."""
import json, os, sys
from jsonschema import Draft202012Validator

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

skill_s = json.load(open(os.path.join(ROOT, "schema", "skill.schema.json")))
chal_s = json.load(open(os.path.join(ROOT, "schema", "challenge.schema.json")))
sv, cv = Draft202012Validator(skill_s), Draft202012Validator(chal_s)

fail = 0
print("=" * 78)
print("SCHEMA — dictionary entries")
for e in json.load(open(os.path.join(ROOT, "dist", "dictionary.json")))["skills"]:
    for err in sv.iter_errors(e):
        print(f"  {e.get('id','?'):26s} {'/'.join(map(str,err.path)) or '<root>'}: {err.message}")
        fail += 1
print(f"  -> {fail} schema errors")

print("=" * 78)
print("SCHEMA — challenge files")
n = fail
for slug, ch in json.load(open(os.path.join(ROOT, "dist", "challenges.json")))["challenges"].items():
    for err in cv.iter_errors(ch):
        print(f"  {slug:16s} {'/'.join(map(str,err.path)) or '<root>'}: {err.message}")
        fail += 1
print(f"  -> {fail - n} schema errors")
print("=" * 78)
print("SCHEMA PASS" if not fail else f"SCHEMA FAIL ({fail})")
sys.exit(1 if fail else 0)
