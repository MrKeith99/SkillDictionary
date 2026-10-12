"""Where everything lives. The only module that knows the repo layout."""
import json, os
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SKILLS = os.path.join(DATA, "skills")
VOCAB = os.path.join(DATA, "vocabulary")
CHALLENGES = os.path.join(DATA, "challenges")
SCHEMA = os.path.join(ROOT, "schema")
TEMPLATES = os.path.join(ROOT, "templates")
DIST = os.path.join(ROOT, "dist")          # committed: JSON for consumers
BUILD = os.path.join(ROOT, "build")        # not committed: sheets, reports, PDFs
RULEBOOK = os.environ.get("RULEBOOK_DIR") or os.path.join(ROOT, "external", "RuleBook")


def rel(path):
    return os.path.relpath(path, ROOT)


def load_yaml(path):
    with open(path) as fh:
        return yaml.safe_load(fh)


def load_json(path):
    with open(path) as fh:
        return json.load(fh)


def write_json(obj, path, indent=2):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=indent)


def write_text(text, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def template(name):
    with open(os.path.join(TEMPLATES, name)) as fh:
        return fh.read()
