import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from examples.responsible_dkt.prepare import CROPS, build_claims, extract_body
from examples.responsible_dkt.report import summarize


class ResponsibleDktExampleTests(unittest.TestCase):
    def test_claims_are_balanced_and_only_use_aggregate_tables(self):
        claims = build_claims()
        self.assertEqual(len(claims), 8)
        self.assertEqual(len({x['sample_id'] for x in claims}), 8)
        counts = Counter((x['claim_type'], x['label']) for x in claims)
        self.assertEqual(len(counts), 8)
        self.assertTrue(all(value == 1 for value in counts.values()))
        for claim in claims:
            self.assertEqual(claim['section'], ['3.4.1', '4.2'])
            fields = ('image_path',) if claim['claim_type'] in {'direct', 'analytical'} else ('item1_path', 'item2_path')
            for field in fields:
                self.assertIn(Path(claim[field]).stem, CROPS)
                self.assertTrue(claim[field].startswith('data/responsible_dkt/'))

    def test_crops_exclude_following_student_examples(self):
        self.assertLess(CROPS['table4']['box'][3], 571)
        self.assertLess(CROPS['table6']['box'][3], 483)
        for crop in CROPS.values():
            x0, y0, x1, y1 = crop['box']
            self.assertTrue(0 <= x0 < x1 <= 612)
            self.assertTrue(0 <= y0 < y1 <= 792)

    def test_context_extraction_removes_bibliographic_names_and_page_headers(self):
        text = '\n3.4.1 Evaluation\nMetric definitions [Example Author, 2025].\n15\n arXiv Template A P REPRINT\nMore definitions.\n3.4.2 Interpretability\n'
        body = extract_body(text, r'\n3\.4\.1\s+Evaluation\s*\n', r'\n3\.4\.2\s+Interpretability\s*\n')
        self.assertIn('Metric definitions', body)
        self.assertIn('More definitions', body)
        self.assertNotIn('Example Author', body)
        self.assertNotIn('arXiv Template', body)
        self.assertNotIn('15', body)

    def test_relative_reduction_is_not_percentage_point_reduction(self):
        early_relative = (18.92 - 14.35) / 18.92 * 100
        inconsistency_relative = (0.44 - 0.36) / 0.44 * 100
        self.assertAlmostEqual(early_relative, 24.2, delta=0.05)
        self.assertAlmostEqual(inconsistency_relative, 18.2, delta=0.05)
        self.assertGreater(early_relative, inconsistency_relative)
        self.assertAlmostEqual((0.44 - 0.36) * 100, 8.0)

    def test_incomplete_run_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'partial.json'
            path.write_text(json.dumps([]))
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                summarize(path)


if __name__ == '__main__':
    unittest.main()
