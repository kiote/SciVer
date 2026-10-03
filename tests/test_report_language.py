import unittest

from paper_review.language import STATUS_TEXT, fallback_summary, reader_label, reader_summary, validate_summary
from paper_review.schema import validate_verification


def summary():
    return {'title':'Clarify the comparison.', 'problem':'The statement does not identify the comparison group.',
            'evidence':['The table contains two comparison groups.'],
            'effect':'The reader cannot identify the intended result.',
            'actions':['State the comparison group.', 'Use the correct values from the table.']}


class ReportLanguageTests(unittest.TestCase):
    def test_all_statuses_have_plain_labels_and_valid_short_actions(self):
        for status in STATUS_TEXT:
            claim={'verification':{'status':status}}
            text=fallback_summary(claim)
            self.assertNotIn('_',reader_label(claim,'pending human review'))
            self.assertTrue(text['problem'] and text['evidence'] and text['effect'] and text['actions'])

    def test_long_instruction_is_rejected(self):
        text=summary();text['actions']=['Check '+'word '*21+'.']
        with self.assertRaisesRegex(ValueError,'20 words'):
            validate_summary(text)

    def test_one_action_per_item_and_action_verb_required(self):
        text=summary();text['actions']=['Check the value. Replace the text.']
        with self.assertRaisesRegex(ValueError,'one action'):
            validate_summary(text)
        text['actions']=['Maybe the value needs a change.']
        with self.assertRaisesRegex(ValueError,'action verb'):
            validate_summary(text)

    def test_reviewed_presentation_precedes_model_suggestion(self):
        claim={'verification':{'status':'ambiguous','reader_summary':{**summary(),'title':'Model suggestion.'}},
               'review':{'presentation':summary()}}
        value,origin=reader_summary(claim,'needs_evidence')
        self.assertEqual(value['title'],'Clarify the comparison.')
        self.assertEqual(origin,'reviewed')

    def test_future_policy_requires_a_reader_summary(self):
        result={'status':'ambiguous','explanation':'Scope unclear','evidence_unit_ids':[]}
        with self.assertRaisesRegex(ValueError,'reader summary'):
            validate_verification(result,[],require_reader=True)
        result['reader_summary']=summary()
        self.assertEqual(validate_verification(result,[],require_reader=True)['reader_summary']['title'],'Clarify the comparison.')

    def test_legacy_results_remain_valid_without_a_new_model_call(self):
        result={'status':'ambiguous','explanation':'Scope unclear','evidence_unit_ids':[]}
        self.assertEqual(validate_verification(result,[])['status'],'ambiguous')
