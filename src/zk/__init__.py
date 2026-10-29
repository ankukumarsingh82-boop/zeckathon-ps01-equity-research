"""Zeckathon PS-01: capital-market infrastructure valuation toolkit."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
INPUTS = ROOT / "data" / "inputs"
OUT = ROOT / "outputs"
CONFIG = ROOT / "config"
