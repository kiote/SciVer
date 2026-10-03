import unittest
from pathlib import Path
from unittest.mock import patch

from paper_review.__main__ import main


def document():
    return {'pages':[{'number':n,'units':[],'needs_ocr':False} for n in [1,2]]}


class CompletionContractTests(unittest.TestCase):
    def test_partial_pages_require_explicit_partial_flag(self):
        state={'passes':{},'claims':[]}
        with patch('sys.argv',['paper_review','run','sample','--pages','1','--max-calls','0']), patch('paper_review.__main__.load',return_value=(Path('.'),document(),state)), patch('paper_review.__main__.run') as execute:
            with self.assertRaises(SystemExit) as error:
                main()
            self.assertEqual(error.exception.code,2)
            execute.assert_not_called()

    def test_full_run_cannot_exit_successfully_if_checks_remain_pending(self):
        state={'passes':{},'claims':[]}
        def paused(*args,**kwargs):state['execution']={'state':'paused_budget'}
        with patch('sys.argv',['paper_review','run','sample','--max-calls','0']), patch('paper_review.__main__.load',return_value=(Path('.'),document(),state)), patch('paper_review.__main__.run',side_effect=paused), patch('paper_review.__main__.save'), patch('paper_review.__main__.build',return_value=Path('report.html')):
            with self.assertRaises(SystemExit) as error:
                main()
            self.assertEqual(error.exception.code,3)
            self.assertEqual(state['execution']['mode'],'full')

    def test_explicit_partial_run_is_still_labelled_partial(self):
        state={'passes':{},'claims':[]}
        def paused(*args,**kwargs):state['execution']={'state':'paused_budget'}
        with patch('sys.argv',['paper_review','run','sample','--pages','1','--partial','--max-calls','0']), patch('paper_review.__main__.load',return_value=(Path('.'),document(),state)), patch('paper_review.__main__.run',side_effect=paused), patch('paper_review.__main__.save'), patch('paper_review.__main__.build',return_value=Path('report.html')):
            main()
            self.assertEqual(state['execution']['mode'],'partial')


if __name__=='__main__':unittest.main()
