"""Every variant and challenge, as written to dist/, against the JSON Schemas."""
import os
from jsonschema import Draft202012Validator
from .. import paths
from . import RULE


def run(b):
    sv = Draft202012Validator(paths.load_json(os.path.join(paths.SCHEMA, "variant.schema.json")))
    cv = Draft202012Validator(paths.load_json(os.path.join(paths.SCHEMA, "challenge.schema.json")))
    fail = 0
    print(RULE)
    print("SCHEMA — variants")
    for e in b.variants_doc()["variants"]:
        for err in sv.iter_errors(e):
            print(f"  {e.get('id', '?'):26s} {'/'.join(map(str, err.path)) or '<root>'}: {err.message}")
            fail += 1
    n = fail
    print(f"  -> {n} schema errors")
    print("SCHEMA — challenges")
    for slug, ch in b.challenges_doc()["challenges"].items():
        for err in cv.iter_errors(ch):
            print(f"  {slug:16s} {'/'.join(map(str, err.path)) or '<root>'}: {err.message}")
            fail += 1
    print(f"  -> {fail - n} schema errors")
    return fail
