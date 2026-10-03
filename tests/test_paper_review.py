import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paper_review.schema import calculate, coverage, digest, review_decision, validate_extraction, validate_verification
from paper_review.store import page_signature, project_path
from paper_review.pipeline import BudgetExhausted, ModelTasks, inventory, run, validate_batch
from paper_review.__main__ import page_numbers


def fixture_page(number=1):
    return {'number':number,'units':[{'id':f'p{number:03d}-u001','page':number,'role':'text','bbox':[0,0,10,10],
                                     'text':'Model A outperforms Model B in every setting.'}],
            'image':f'pages/p{number:03d}.jpg','image_sha256':'test','needs_ocr':False,'privacy_warnings':[]}


def extraction(page):
    u=page['units'][0]
    return {'claims':[{'text':u['text'],'origin':'paper_statement','source_quote':u['text'],
                       'source_unit_ids':[u['id']],'kind':'comparative'}],
            'units':[{'unit_id':u['id'],'disposition':'claims','reason':'Actual authored comparison'}]}


class ReviewSchemaTests(unittest.TestCase):
    def test_no_unaccounted_units(self):
        p=fixture_page();r=extraction(p);r['units']=[]
        with self.assertRaisesRegex(ValueError,'accounted'):
            validate_extraction(r,p['units'])

    def test_invented_negative_claim_or_stronger_paraphrase_rejected(self):
        p=fixture_page();r=extraction(p);r['claims'][0]['text']='Model A is always wrong.'
        with self.assertRaisesRegex(ValueError,'verbatim'):
            validate_extraction(r,p['units'])

    def test_quote_must_be_in_the_source(self):
        p=fixture_page();r=extraction(p)
        r['claims'][0]['text']=r['claims'][0]['source_quote']='An invented statement.'
        with self.assertRaisesRegex(ValueError,'not present'):
            validate_extraction(r,p['units'])

    def test_no_gold_labels_or_model_assigned_internal_ids(self):
        p=fixture_page();r=extraction(p);r['claims'][0]['label']=False
        with self.assertRaisesRegex(ValueError,'gold labels'):
            validate_extraction(r,p['units'])

    def test_visual_placeholder_is_not_a_paper_statement(self):
        p=fixture_page();p['units'][0]['role']='visual'
        with self.assertRaisesRegex(ValueError,'not present'):
            validate_extraction(extraction(p),p['units'])

    def test_missing_evidence_not_automatically_false(self):
        p=fixture_page()
        good={'status':'insufficient_evidence','explanation':'Need another table','evidence_unit_ids':[], 'calculations':[]}
        self.assertEqual(validate_verification(good,p['units'])['status'],'insufficient_evidence')
        bad={**good,'status':'contradicted'}
        with self.assertRaisesRegex(ValueError,'needs evidence'):
            validate_verification(bad,p['units'])

    def test_unknown_evidence_and_unsafe_calculations_rejected(self):
        p=fixture_page();r={'status':'supported','explanation':'test','evidence_unit_ids':['outside-unit']}
        with self.assertRaisesRegex(ValueError,'unknown'):
            validate_verification(r,p['units'])
        with self.assertRaisesRegex(ValueError,'Unsupported'):
            calculate({'operation':'eval','a':'1','b':'2'})
        self.assertEqual(calculate({'operation':'difference','a':'44','b':'36'})['computed'],'8')

    def test_eight_checked_claims_do_not_imply_full_document_coverage(self):
        doc={'pages':[fixture_page(1),fixture_page(2)]}
        state={'passes':{'primary-1':extraction(doc['pages'][0]),'audit-1':extraction(doc['pages'][0])},
               'claims':[{'id':str(i),'verification':{'status':'supported'}} for i in range(8)]}
        c=coverage(doc,state)
        self.assertFalse(c['inventory_complete'])
        self.assertEqual(c['verified'],8)
        self.assertIn('Partial',c['label'])

    def test_scanned_or_unreadable_pages_prevent_complete_inventory(self):
        p=fixture_page();p['needs_ocr']=True
        doc={'pages':[p]};state={'passes':{'primary-1':extraction(p),'audit-1':extraction(p)},'claims':[]}
        self.assertFalse(coverage(doc,state)['inventory_complete'])
        p['needs_ocr']=False;state['passes']['audit-1']['units'][0]['disposition']='unreadable'
        self.assertFalse(coverage(doc,state)['inventory_complete'])

    def test_model_candidate_is_not_reviewer_confirmed(self):
        doc={'pages':[fixture_page()]};state={'claims':[{'id':'c-test','verification':{'status':'contradicted'}}]}
        c=coverage(doc,state)
        self.assertEqual(c['candidate_findings'],1);self.assertEqual(c['confirmed_findings'],0)

    def test_stale_human_decision_is_not_a_confirmed_finding(self):
        claim={'id':'c-test','origin':'paper_statement','verification':{'status':'contradicted'}}
        claim['review']={'decision':'confirmed','verification_sha256':digest(claim['verification'])}
        self.assertEqual(review_decision(claim),'confirmed')
        claim['verification']={'status':'ambiguous'}
        self.assertIn('stale',review_decision(claim))
        self.assertEqual(coverage({'pages':[fixture_page()]},{'claims':[claim]})['confirmed_findings'],0)

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):project_path('../private')
        self.assertEqual(page_numbers('1,3-5',5),{1,3,4,5})
        with self.assertRaises(ValueError):page_numbers('9',5)


class ReviewPipelineTests(unittest.TestCase):
    def test_budget_and_input_approval_enforced_without_provider_calls(self):
        p=fixture_page();state={};doc={'pages':[p]}
        with tempfile.TemporaryDirectory() as folder:
            tasks=ModelTasks(Path(folder),doc,state,0)
            with patch('paper_review.pipeline.PiRpcClient') as client:
                with self.assertRaises(PermissionError):tasks.call('x','task',{},[p],lambda r:r)
                state['approved_pages']={'1':page_signature(p)}
                with self.assertRaises(BudgetExhausted):tasks.call('x','task',{},[p],lambda r:r)
                client.assert_not_called()

    def test_validated_task_cache_avoids_repeat_model_call(self):
        p=fixture_page();state={'approved_pages':{'1':page_signature(p)}};doc={'pages':[p]}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);(path/'pages').mkdir();(path/p['image']).write_bytes(b'fake')
            with patch('paper_review.pipeline.PiRpcClient') as factory:
                client=factory.return_value
                client.get_state.return_value={'model':{'provider':'github-copilot','id':'gpt-5.5','input':['text','image']},'thinkingLevel':'high'}
                client.prompt_and_wait.return_value=json.dumps(extraction(p));client.last_assistant={'stopReason':'stop'}
                first=ModelTasks(path,doc,state,1)
                result=first.call('primary-1','extract',{'units':p['units']},[p],lambda r:validate_extraction(r,p['units']))
                first.close()
                second=ModelTasks(path,doc,state,0)
                self.assertEqual(second.call('primary-1','extract',{'units':p['units']},[p],lambda r:validate_extraction(r,p['units'])),result)
                self.assertEqual(second.used,0)
                self.assertEqual(client.prompt_and_wait.call_count,1)

    def test_batch_results_must_account_for_every_claim(self):
        p=fixture_page();claims=[{'id':'c-one'},{'id':'c-two'}]
        answers={'results':[{'claim_id':'c-one','status':'supported','explanation':'test','evidence_unit_ids':[p['units'][0]['id']]}]}
        with self.assertRaisesRegex(ValueError,'every claim'):
            validate_batch(answers,claims,p['units'])

    def test_transformed_batch_cache_can_be_revalidated_without_new_calls(self):
        p=fixture_page();state={'approved_pages':{'1':page_signature(p)}};doc={'pages':[p]}
        raw={'results':[{'claim_id':'c-one','status':'supported','explanation':'test','evidence_unit_ids':[p['units'][0]['id']]}]}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);(path/'pages').mkdir();(path/p['image']).write_bytes(b'fake')
            with patch('paper_review.pipeline.PiRpcClient') as factory:
                client=factory.return_value
                client.get_state.return_value={'model':{'provider':'github-copilot','id':'gpt-5.5','input':['text','image']},'thinkingLevel':'high'}
                client.prompt_and_wait.return_value=json.dumps(raw);client.last_assistant={'stopReason':'stop'}
                validator=lambda r:validate_batch(r,[{'id':'c-one'}],p['units'])
                first=ModelTasks(path,doc,state,1);one=first.call('batch','verify',{},[p],validator);first.close()
                second=ModelTasks(path,doc,state,0);two=second.call('batch','verify',{},[p],validator)
                self.assertEqual(one,two);self.assertEqual(second.used,0)
                self.assertEqual(client.prompt_and_wait.call_count,1)

    def test_explicit_exclusions_are_not_pending_pages(self):
        p=fixture_page();doc={'pages':[p,fixture_page(2)]}
        state={'page_exclusions':{'2':{'reason':'Reference list only','page_sha256':digest(doc['pages'][1])}},
               'passes':{'primary-1':extraction(p),'audit-1':extraction(p)},'claims':[]}
        c=coverage(doc,state)
        self.assertEqual(c['in_scope_pages'],1);self.assertEqual(c['excluded_pages'],1)
        self.assertTrue(c['pages'][1]['excluded'])
        self.assertTrue(c['automated_checks_complete'])
        state['task_errors']={'primary-1':'error'}
        self.assertFalse(coverage(doc,state)['automated_checks_complete'])

    def test_independent_passes_merge_without_synthetic_controls(self):
        p=fixture_page();state={'passes':{'primary-1':extraction(p),'audit-1':extraction(p)},'claims':[]}
        inventory(state)
        self.assertEqual(len(state['claims']),1)
        self.assertEqual(state['claims'][0]['origin'],'paper_statement')
        self.assertNotIn('label',state['claims'][0])

    def test_new_projects_request_and_validate_short_reader_summaries(self):
        p=fixture_page();doc={'pages':[p],'ingest_config':{'reader_language_policy':'ste-inspired-v1'}}
        state={'approved_pages':{'1':page_signature(p)},'passes':{},'claims':[]};instructions=[]
        concise={'title':'Check the comparison.','problem':'The comparison needs a source check.',
                 'evidence':['The statement compares two models.'],'effect':'The reader needs the source values.',
                 'actions':['Compare the values in the table.']}
        class FakeTasks:
            def __init__(self,*a,**k):self.used=0
            def close(self):pass
            def call(self,key,instruction,payload,pages,validator):
                if key.startswith('verify-'):
                    instructions.append(instruction)
                    return validator({'status':'ambiguous','explanation':'Scope needs review','evidence_unit_ids':[p['units'][0]['id']],
                                      'reader_summary':concise})
                return extraction(p)
        with tempfile.TemporaryDirectory() as folder,patch('paper_review.pipeline.ModelTasks',FakeTasks):
            run(Path(folder),doc,state,{1},0)
        self.assertIn('reader_summary',instructions[0])
        self.assertEqual(state['claims'][0]['verification']['reader_summary']['title'],'Check the comparison.')

    def test_verification_payload_does_not_leak_previous_verdict_or_review(self):
        p=fixture_page();doc={'pages':[p]};state={'approved_pages':{'1':page_signature(p)},'passes':{'primary-1':extraction(p),'audit-1':extraction(p)},'claims':[]}
        inventory(state)
        state['claims'][0]['verification']={'status':'contradicted'}
        state['claims'][0]['review']={'decision':'confirmed'}
        captured=[]
        class FakeTasks:
            def __init__(self,*a,**k):self.used=0
            def close(self):pass
            def call(self,key,instruction,payload,pages,validator):
                if key.startswith('verify-'):
                    captured.append(payload['claim'])
                    return validator({'status':'supported','explanation':'test','evidence_unit_ids':[p['units'][0]['id']]})
                return extraction(p)
        with tempfile.TemporaryDirectory() as folder,patch('paper_review.pipeline.ModelTasks',FakeTasks):
            run(Path(folder),doc,state,{1},0)
        self.assertEqual(len(captured),1)
        self.assertNotIn('verification',captured[0]);self.assertNotIn('review',captured[0])
