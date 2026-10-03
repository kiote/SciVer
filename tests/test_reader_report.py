import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paper_review.report import build, page_ranges, reader_claims, review_scope
from paper_review.schema import coverage, digest


def claim(identifier, decision=None, issue='shared-issue'):
    result = {'id': identifier, 'text': identifier+' source wording', 'origin': 'paper_statement',
              'kind': 'comparative', 'source_unit_ids': ['p001-u001'],
              'verification': {'status': 'ambiguous', 'explanation': identifier+' explanation',
                               'evidence_unit_ids': ['p001-u001']}}
    if decision:
        result['review'] = {'decision': decision, 'note': identifier+' reviewer note',
                            'reviewer_type': 'assistant', 'issue_id': issue,
                            'verification_sha256': digest(result['verification'])}
    return result


class ReaderReportTests(unittest.TestCase):
    def fixtures(self):
        document = {'id':'paper','title':'Test paper','source_sha256':'0'*64,
                    'source_reference':'Local PDF',
                    'pages':[{'number':1,'units':[{'id':'p001-u001','page':1,'text':'Source text',
                                                 'bbox':[0,0,10,10]}],
                              'image':'pages/p001.jpg','needs_ocr':False,'privacy_warnings':[]}]}
        state = {'claims':[claim('active-confirmed','confirmed'),
                           claim('closed-dismissed-SENTINEL','dismissed'),
                           claim('pending-candidate')], 'passes':{}, 'task_errors':{}}
        return document,state

    def test_valid_dismissal_excluded_from_reader_selection(self):
        _,state=self.fixtures()
        self.assertEqual([c['id'] for c in reader_claims(state)],['active-confirmed','pending-candidate'])
        self.assertEqual(len(state['claims']),3)  # The audit ledger is not modified.

    def test_dismissed_content_absent_from_entire_html_not_just_hidden_by_css(self):
        document,state=self.fixtures()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch('paper_review.report.ROOT',root),patch('paper_review.report.OUT',root/'outputs'):
                target=build(root/'data/paper',document,state)
                text=target.read_text()
                self.assertNotIn('closed-dismissed-SENTINEL',text)
                self.assertNotIn('dismissed',text)
                self.assertIn('active-confirmed',text)
                self.assertIn('pending-candidate',text)
                self.assertIn('2 active checks shown',text)
                self.assertEqual(text.count('data-kind='),2)
                self.assertEqual(len(state['claims']),3)
                # Same issue group: closed note/link must not contaminate the active summary.
                self.assertNotIn('closed-dismissed-SENTINEL reviewer note',text)
                self.assertEqual(build(root/'data/paper',document,state),target)
                self.assertNotIn('closed-dismissed-SENTINEL',target.read_text())

    def test_technical_matrix_is_collapsed_and_scope_is_plain_language(self):
        document,state=self.fixtures()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch('paper_review.report.ROOT',root),patch('paper_review.report.OUT',root/'outputs'):
                text=build(root/'data/paper',document,state).read_text()
                self.assertNotIn('What has—and has not—been covered?',text)
                self.assertIn('<h2>Review scope</h2>',text)
                self.assertIn('<details id="technical-audit">',text)
                self.assertNotIn('<details id="technical-audit" open',text)
                self.assertLess(text.index('<details id="technical-audit">'),text.index('<th>Input consent</th>'))
                self.assertIn('This review is not finished',text)

    def test_scope_note_preserves_complete_vs_partial_distinction_and_exclusions(self):
        document,state=self.fixtures()
        c=coverage(document,state)
        note,excluded=review_scope(document,state,c)
        self.assertIn('not finished',note)
        c['automated_checks_complete']=True
        note,_=review_scope(document,state,c)
        self.assertIn("paper's text, tables, and figures",note)
        c['pages'][0].update(excluded=True,exclusion_reason='Author sheet only')
        _,excluded=review_scope(document,state,c)
        self.assertEqual(excluded,[('1','Author sheet only')])
        self.assertEqual(page_ranges([1,2,3,8,10,11]),'1–3, 8, 10–11')

    def test_reader_report_uses_action_fields_and_hides_the_large_record_list(self):
        document,state=self.fixtures()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch('paper_review.report.ROOT',root),patch('paper_review.report.OUT',root/'outputs'):
                text=build(root/'data/paper',document,state).read_text()
                self.assertNotIn('Model status:',text)
                self.assertNotIn('Source claims and evidence',text)
                self.assertIn('<h2>Problems and actions</h2>',text)
                for field in ['Problem','Evidence','Effect','Action']:
                    self.assertIn('<h4>'+field+'</h4>',text)
                self.assertIn('<details id="claims">',text)
                self.assertNotIn('<details id="claims" open',text)
                self.assertIn('Label guide:',text)
                self.assertIn('Formal ASD-STE100 compliance has not been verified.',text)

    def test_changed_evidence_resurfaces_stale_claim_without_old_dismissal_note(self):
        document,state=self.fixtures()
        closed=state['claims'][1]
        closed['verification']['explanation']='New evidence requires a fresh review'
        self.assertEqual(len(reader_claims(state)),3)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch('paper_review.report.ROOT',root),patch('paper_review.report.OUT',root/'outputs'):
                text=build(root/'data/paper',document,state).read_text()
                self.assertIn('New evidence requires a fresh review',text)
                self.assertIn('stale decision',text)
                self.assertNotIn('closed-dismissed-SENTINEL reviewer note',text)
