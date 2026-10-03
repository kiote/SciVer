"""Summarize the Responsible-DKT aggregate-table demonstration."""
import argparse
from pathlib import Path

from examples.article_report import summarize_article
from examples.responsible_dkt.prepare import ROOT, TITLE, PDF_URL, build_claims

RESULTS = ROOT / "examples/responsible_dkt/results"


def summarize(input_path):
    return summarize_article(
        input_path, build_claims(), RESULTS, "2604.08263v1", TITLE, PDF_URL,
        notes=[
            "The universal accuracy claim is not supported by every printed Table 4 setting: at 10% training ratio and N=10, Responsible-DKT accuracy is **0.78** versus Classic-DKT **0.84**; at 50% and N=10 both are **0.83**.",
            "This is a scoped check of reported table values, not a reproduction of the experiments, a significance test, or a rejection of the paper's AUC findings.",
            "The drop from inconsistency 0.44 to 0.36 is **8 percentage points**, or about **18.2% relative reduction**—these are different quantities.",
            "Only aggregate tables and selected metric/results prose are provided. Author/contact lists, bibliographic citations and individual-student examples are excluded.",
            "The eight checks and labels were authored from the source before inference; they are not official SciVer annotations or a whole-paper audit.",
        ],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    summarize(args.input)
