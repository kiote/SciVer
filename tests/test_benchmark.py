import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from acc_evaluation import get_acc, parse_verdict
from benchmarks.prepare_slice import select_indices
from benchmarks.run import DEFAULT_MODELS, file_name, run_model, scores
from main import build_parser, main as run_inference
from model_inference.pi_rpc import PiRpcClient, PiRpcError, _resolve_pi_model, generate_response
from utils.constant import DEFAULT_MODEL, DEFAULT_PI_THINKING


class DefaultModelTests(unittest.TestCase):
    def test_cli_and_benchmark_default_to_gpt55_high(self):
        args = build_parser().parse_args(['--data_path', 'sample.json'])
        self.assertEqual(args.model, 'pi/github-copilot/gpt-5.5')
        self.assertEqual(_resolve_pi_model(args.model, args.thinking), ('github-copilot/gpt-5.5', 'high'))
        self.assertEqual(DEFAULT_MODELS[0], DEFAULT_MODEL)
        self.assertEqual(DEFAULT_PI_THINKING, 'high')

    def test_explicit_overrides_and_pi_current(self):
        args = build_parser().parse_args(['--data_path', 'sample.json', '--model', 'pi/github-copilot/gpt-5.4', '--thinking', 'medium'])
        self.assertEqual(_resolve_pi_model(args.model, args.thinking), ('github-copilot/gpt-5.4', 'medium'))
        with patch.dict('os.environ', {'PI_PROVIDER': 'github-copilot', 'PI_MODEL': 'gpt-5.4', 'PI_REASONING_LEVEL': 'medium'}):
            self.assertEqual(_resolve_pi_model(DEFAULT_MODEL), ('github-copilot/gpt-5.5', 'high'))
            self.assertEqual(_resolve_pi_model('pi/current'), ('github-copilot/gpt-5.4', 'medium'))
            self.assertEqual(_resolve_pi_model('pi/current', 'high'), ('github-copilot/gpt-5.4', 'high'))

    def test_pi_subprocess_gets_explicit_defaults(self):
        with patch('model_inference.pi_rpc.subprocess.Popen') as spawn:
            spawn.return_value.stdout.readline.return_value = b''
            client = PiRpcClient()
            try:
                cmd = spawn.call_args.args[0]
                self.assertEqual(cmd[cmd.index('--model') + 1], 'github-copilot/gpt-5.5')
                self.assertEqual(cmd[cmd.index('--thinking') + 1], 'high')
            finally:
                client.close()

    def test_cli_routes_default_to_pi_not_azure(self):
        with patch('model_inference.pi_rpc.generate_response') as generate:
            run_inference(DEFAULT_MODEL, {}, [], 'unused.json')
            generate.assert_called_once_with(model_name=DEFAULT_MODEL, prompt={}, queries=[],
                                             output_path='unused.json', n=1, thinking=None)

    def test_non_pi_backend_does_not_get_thinking_argument(self):
        with patch('model_inference.ollama_chat.generate_response') as generate:
            run_inference('ollama/local', {}, [], 'unused.json')
            self.assertNotIn('thinking', generate.call_args.kwargs)
        with self.assertRaisesRegex(ValueError, 'only to pi/'):
            run_inference('ollama/local', {}, [], 'unused.json', thinking='high')

    def test_model_fallback_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch('model_inference.pi_rpc.PiRpcClient') as factory:
            client = factory.return_value
            client.get_state.return_value = {'thinkingLevel': 'high',
                'model': {'provider': 'github-copilot', 'id': 'gpt-5.4', 'input': ['text', 'image']}}
            target = str(Path(directory) / 'result.json')
            with self.assertRaisesRegex(PiRpcError, 'different model/reasoning'):
                generate_response(DEFAULT_MODEL, {}, [{}], target)
            client.prompt_and_wait.assert_not_called()
            client.close.assert_called_once()
            self.assertFalse(Path(target).exists())


class VerdictTests(unittest.TestCase):
    def test_final_answer_overrides_earlier_yes(self):
        self.assertFalse(parse_verdict('It might look like yes, but the final answer is: Answer: no'))

    def test_supported_formats(self):
        for value in ('Answer: yes', 'Therefore, the final answer is: Yes.', '**Answer:** yes', 'yes'):
            self.assertTrue(parse_verdict(value), value)
        for value in ('Therefore, the final answer is: No.', 'Answer: no', '**no**'):
            self.assertFalse(parse_verdict(value), value)

    def test_malformed_is_not_refuted(self):
        for value in ('', None, [], 'insufficient evidence', 'yesterday', 'I would not say yes',
                      'Answer: yes/no', 'final answer is: yes or no'):
            self.assertIsNone(parse_verdict(value))
        result = get_acc([{'claim_type': 'direct', 'label': False, 'response': 'cannot determine'}])
        self.assertEqual(result['total'], 0)
        self.assertIsNone(result['parallel'])

    def test_truncation_and_failures_count_as_wrong(self):
        rows = [{'claim_type': 'direct', 'label': True, 'prediction': True,
                 'response': 'yes', 'wall_seconds': 1, 'stop_reason': 'length'},
                {'claim_type': 'direct', 'label': False, 'prediction': None,
                 'response': '', 'wall_seconds': 1, 'error': 'PiRpcError'}]
        self.assertEqual(scores(rows)['total']['correct'], 0)
        self.assertEqual(scores(rows)['total']['errors'], 1)


class SelectionTests(unittest.TestCase):
    def test_balanced_deterministic_and_no_mirrored_question(self):
        rows = []
        for typ in ('direct', 'parallel', 'sequential', 'analytical'):
            for n in range(8):
                for label in (True, False):
                    rows.append({'paperid': str(n), 'request_id': n, 'claim_type': typ, 'label': label})
        selected = select_indices(rows)
        self.assertEqual(selected, select_indices(rows))
        self.assertEqual(len(selected), 16)
        counts = Counter((rows[i]['claim_type'], rows[i]['label']) for i in selected)
        self.assertEqual(len(counts), 8)
        self.assertTrue(all(n == 2 for n in counts.values()))
        self.assertEqual(len({(rows[i]['paperid'], rows[i]['claim_type'], rows[i]['request_id']) for i in selected}), 16)


class RunConfigurationTests(unittest.TestCase):
    def run_with_fake_client(self, directory, actual_thinking="high"):
        model = 'pi/github-copilot/gpt-5.4'
        manifest_file = directory / 'manifest.json'
        manifest_file.write_text('{}')
        query = {'sample_id': 'test-0000', 'claim_type': 'direct', 'label': True}
        with patch.multiple('benchmarks.run', MANIFEST=manifest_file,
                            versions=lambda: {}, _query_images=lambda q: [],
                            prepare_qa_text_input=lambda *args: ({}, 'claim')):
            with patch('benchmarks.run.PiRpcClient') as factory, patch('benchmarks.run.subprocess.check_output', return_value='test-pi'):
                client = factory.return_value
                client.get_state.return_value = {'thinkingLevel': actual_thinking,
                    'model': {'provider': 'github-copilot', 'id': 'gpt-5.4', 'input': ['text', 'image']}}
                client.prompt_and_wait.return_value = 'Answer: yes'
                client.last_assistant = {'stopReason': 'stop', 'usage': {}}
                report = run_model(model, [query], {'revision': 'test'}, thinking='high', results_dir=directory)
                factory.assert_called_once_with(model='github-copilot/gpt-5.4', thinking='high')
                return report

    def test_requested_reasoning_is_used_and_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            report = self.run_with_fake_client(Path(directory))
            self.assertEqual(report['config']['thinking'], 'high')
            self.assertEqual(report['examples'][0]['effective_thinking'], 'high')
            self.assertEqual(report['scores']['total']['correct'], 1)

    def test_clamped_reasoning_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'reasoning level'):
                self.run_with_fake_client(Path(directory), actual_thinking='medium')
            self.assertFalse((Path(directory) / file_name('pi/github-copilot/gpt-5.4')).exists())

    def test_existing_different_run_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / file_name('pi/github-copilot/gpt-5.4')
            original = json.dumps({'config': {'thinking': 'medium'}, 'examples': []})
            path.write_text(original)
            with self.assertRaisesRegex(ValueError, 'different --results-dir'):
                self.run_with_fake_client(Path(directory))
            self.assertEqual(path.read_text(), original)


class RpcTests(unittest.TestCase):
    def client(self):
        client = PiRpcClient.__new__(PiRpcClient)
        client.timeout = 10
        client._next_id = 1
        client._settled = False
        client.last_assistant = None
        return client

    def test_early_settled_is_not_lost(self):
        client = self.client()
        message = {'role': 'assistant', 'stopReason': 'stop', 'content': [{'type': 'text', 'text': 'Answer: yes'}]}
        def ack(_):
            client._settled = True
            client.last_assistant = message
            return {'success': True, 'data': {'disposition': 'started'}}
        with patch.object(client, '_send'), patch.object(client, '_wait_for_response', side_effect=ack):
            self.assertEqual(client.prompt_and_wait('claim'), 'Answer: yes')

    def test_provider_error_not_an_empty_success(self):
        client = self.client()
        def ack(_):
            client._settled = True
            client.last_assistant = {'stopReason': 'error', 'errorMessage': 'test failure'}
            return {'success': True, 'data': {'disposition': 'started'}}
        with patch.object(client, '_send'), patch.object(client, '_wait_for_response', side_effect=ack):
            with self.assertRaises(PiRpcError):
                client.prompt_and_wait('claim')


if __name__ == '__main__':
    unittest.main()
