import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from examples.attention_is_all_you_need.prepare import CROPS, PDF_SHA256, build_claims
from examples.attention_is_all_you_need.report import summarize


class ArticleExampleTests(unittest.TestCase):
    def test_predefined_checks_are_balanced_and_have_valid_evidence_fields(self):
        claims = build_claims()
        self.assertEqual(len(claims), 8)
        self.assertEqual(len({x['sample_id'] for x in claims}), 8)
        counts = Counter((x['claim_type'], x['label']) for x in claims)
        self.assertEqual(len(counts), 8)
        self.assertTrue(all(value == 1 for value in counts.values()))
        for x in claims:
            fields = ('image_path',) if x['claim_type'] in {'direct', 'analytical'} else ('item1_path', 'item2_path')
            for field in fields:
                self.assertTrue(x[field].startswith('data/attention_is_all_you_need/'))
            self.assertNotIn('response', x)

    def test_source_pin_and_crop_bounds(self):
        self.assertEqual(len(PDF_SHA256), 64)
        for crop in CROPS.values():
            x0, y0, x1, y1 = crop['box']
            self.assertTrue(0 <= x0 < x1 <= 612)
            self.assertTrue(0 <= y0 < y1 <= 792)

    def test_source_based_arithmetic_checks(self):
        ratio = (2.3e19 / 213e6) / (3.3e18 / 65e6)
        self.assertAlmostEqual(ratio, 2.1, delta=0.05)
        n, d = 128, 512
        self.assertEqual(n ** 2 * d / (n * d ** 2), 0.25)
        self.assertEqual((2*n) ** 2 * d / (n ** 2 * d), 4)
        self.assertEqual((2*n) * d ** 2 / (n * d ** 2), 2)

    def test_incomplete_run_cannot_produce_a_success_report(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'partial.json'
            path.write_text('[]')
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                summarize(path)

    def test_changed_claims_cannot_be_scored_as_the_original_checks(self):
        records = build_claims()
        records[0]['claim'] = 'changed claim'
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'changed.json'
            path.write_text(json.dumps(records))
            with self.assertRaisesRegex(ValueError, 'predefined'):
                summarize(path)


if __name__ == '__main__':
    unittest.main()
