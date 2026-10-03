"""Summarize a completed article demonstration; this is not a SciVer benchmark."""
import argparse
from pathlib import Path

from examples.article_report import summarize_article
from examples.attention_is_all_you_need.prepare import ROOT, build_claims, PDF_URL

RESULTS = ROOT / "examples/attention_is_all_you_need/results"


def summarize(input_path):
    return summarize_article(
        input_path, build_claims(), RESULTS, "1706.03762v7", "Attention Is All You Need", PDF_URL,
        notes=[
            "The downloaded PDF's Table 2 shows EN-FR BLEU **41.8** for Transformer (big), whereas its Section 6.1 prose shows **41.0**.",
            "The parallel-2 check asks whether those numbers agree. This detects a discrepancy; it does not determine which experimental number is authoritative.",
            "This famous paper may be present in model training data; the demonstration is not an independent generalization test.",
        ],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    summarize(args.input)
