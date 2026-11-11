import json
from pathlib import Path

SPECS_PATH = Path(__file__).resolve().parent.parent / "config" / "specs.json"

def load_specs(path = SPECS_PATH):
    with open(path, encoding = "utf-8") as file:
        specs = json.load(file)
        return specs