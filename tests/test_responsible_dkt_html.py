import base64
import hashlib
import re
import unittest
from pathlib import Path

from examples.responsible_dkt.html_report import ROOT, CSS, JS, accuracy_rows, origin, render_report
from examples.responsible_dkt.prepare import CROPS, build_claims


class ResponsibleDktHtmlTests(unittest.TestCase):
    def fixtures(self):
        records = build_claims()
        for r in records:
            r['response'] = 'Answer: yes' if r['label'] else 'Answer: no'
            r['inference'] = {'provider': 'github-copilot', 'model': 'gpt-5.5', 'thinking': 'high'}
        checks = {'n': 8, 'correct': 8}
        source = {'title': 'Example paper', 'credit': 'Example author', 'pdf_sha256': '0'*64,
                  'renderer': 'test renderer', 'crops': CROPS,
                  'crop_sha256': {k: '0'*64 for k in CROPS}}
        images = {k: b'fake-png-for-rendering-tests-only' for k in CROPS}
        return records, checks, source, images

    def render(self, *fixtures):
        return render_report(*fixtures, output=ROOT / 'outputs/responsible_dkt/report.html')

    def test_false_controls_are_not_presented_as_paper_errors(self):
        records, checks, source, images = self.fixtures()
        origins = [origin(r)[0] for r in records]
        self.assertEqual(origins.count('paper'), 1)
        self.assertEqual(origins.count('control'), 3)
        self.assertEqual(origins.count('supported'), 4)
        page = self.render(records, checks, source, images)
        self.assertIn('We did not find that mistaken wording in the paper.', page)
        self.assertIn('only one is tied to an actual statement in the paper', page)
        self.assertIn('not a score for the paper', page)

    def test_table_transcription_has_one_loss_one_tie_and_ten_accuracy_wins(self):
        rows = accuracy_rows()
        self.assertEqual(sum(r['delta_pp'] < 0 for r in rows), 1)
        self.assertEqual(sum(r['delta_pp'] == 0 for r in rows), 1)
        self.assertEqual(sum(r['delta_pp'] > 0 for r in rows), 10)
        self.assertEqual(sum(r['r_auc'] > r['c_auc'] for r in rows), 12)
        self.assertEqual(rows[0]['delta_pp'], -6)

    def test_model_text_and_claims_are_escaped(self):
        records, checks, source, images = self.fixtures()
        records[0]['claim'] = '<img src=x onerror=alert(1)>'
        records[0]['response'] = 'Answer: yes\n<script>alert(1)</script>'
        page = self.render(records, checks, source, images)
        self.assertNotIn('<script>alert(1)</script>', page)
        self.assertNotIn('<img src=x onerror=alert(1)>', page)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', page)
        self.assertEqual(page.count('<script>'), 1)

    def test_assets_are_embedded_and_csp_hashes_match(self):
        page = self.render(*self.fixtures())
        self.assertEqual(page.count('src="data:image/png;base64,'), 3)
        self.assertNotIn('<script src=', page)
        self.assertNotIn('<link rel="stylesheet"', page)
        for tag, expected in [('style', CSS), ('script', JS)]:
            content = re.search(r'<'+tag+r'>(.*?)</'+tag+r'>', page, re.S).group(1)
            self.assertEqual(content, expected)
            digest = base64.b64encode(hashlib.sha256(content.encode()).digest()).decode()
            self.assertIn('sha256-'+digest, page)
        self.assertNotIn('/Users/', page)
        self.assertNotIn('/home/', page)

    def test_output_outside_repo_rejected_to_avoid_private_link_paths(self):
        with self.assertRaisesRegex(ValueError, 'inside the repo'):
            render_report(*self.fixtures(), output=Path('/tmp/outside-sci-report.html'))

    def test_inconsistent_totals_rejected(self):
        records, checks, source, images = self.fixtures()
        checks['correct'] = 7
        with self.assertRaisesRegex(ValueError, 'totals'):
            self.render(records, checks, source, images)


if __name__ == '__main__':
    unittest.main()
