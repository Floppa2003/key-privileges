"""Only finite, well-formed public Nuxt wrapper paths may be decoded."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from magnit_partners import public_data


def page(values):
    return '<script id="__NUXT_DATA__">' + json.dumps(values) + '</script>'


class MagnitStateWrapperTests(unittest.TestCase):
    def assert_rejected(self, values):
        try:
            public_data(page(values), 'partners-offers')
        except ValueError:
            return
        except Exception as exc:
            self.fail('Malformed public state raised an uncontrolled exception: ' + repr(exc))
        self.fail('Malformed public state was accepted')

    def test_root_and_data_wrapper_cycles_terminate(self):
        # A separate process makes the regression terminate even if the decoder
        # once again loops before reaching its ordinary reference checks.
        script = '''import json, sys
from magnit_partners import public_data
raw = '<script id="__NUXT_DATA__">' + sys.argv[1] + '</script>'
try:
    public_data(raw, 'partners-offers')
except ValueError:
    sys.exit(0)
raise AssertionError('cyclic public state was accepted')
'''
        cases = ([['Reactive', 0]],
                 [['ShallowReactive', 1], ['Reactive', 0]],
                 [{'data': 1}, ['Reactive', 1]])
        for values in cases:
            with self.subTest(values=values):
                try:
                    result = subprocess.run([sys.executable, '-c', script, json.dumps(values)],
                                            cwd=Path(__file__).parents[1],
                                            capture_output=True, text=True, timeout=5)
                except subprocess.TimeoutExpired:
                    self.fail('A wrapper cycle did not terminate')
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_empty_or_non_object_root_and_data_fail_as_invalid_state(self):
        for values in ([], [None], [[]], [{}], [{'data': 1}, None],
                       [{'data': 1}, []], [{'data': 1}, {'different-key': 2}, 'public']):
            with self.subTest(values=values):
                self.assert_rejected(values)

    def test_wrapper_reference_requires_a_nonnegative_integer_in_bounds(self):
        for ref in (-1, 99, True, '1', None):
            values = [['Reactive', ref], {'data': 2}, {'partners-offers': 3}, 'public']
            with self.subTest(ref=ref):
                self.assert_rejected(values)

    def test_data_reference_cannot_use_negative_or_boolean_indexing(self):
        for ref in (-1, True):
            values = [{'data': ref}, {'partners-offers': 2}, 'public']
            with self.subTest(ref=ref):
                self.assert_rejected(values)

    def test_wrappers_have_exactly_one_reference_at_each_owned_level(self):
        for wrapper in (['Reactive'], ['Reactive', 1, 'unexpected']):
            with self.subTest(level='root', wrapper=wrapper):
                self.assert_rejected([wrapper, {'data': 2}, {'partners-offers': 3}, 'public'])
        for wrapper in (['ShallowReactive'], ['Reactive', 3, 'unexpected']):
            with self.subTest(level='public', wrapper=wrapper):
                self.assert_rejected([{'data': 1}, {'partners-offers': 2}, wrapper, 'public'])

    def test_valid_public_wrappers_do_not_traverse_private_sibling_stores(self):
        values = [['ShallowReactive', 1], {'data': 2, 'pinia': 9},
                  ['Reactive', 3], {'partners-offers': 4, 'user-profile': 8},
                  [5], {'id': 6, 'title': 7}, 17, 'Партнёр',
                  ['Reactive', 8], ['UnknownPrivateWrapper', 9]]
        self.assertEqual(public_data(page(values), 'partners-offers'), [{'id': 17, 'title': 'Партнёр'}])

    def test_public_nested_wrapper_cycles_are_rejected(self):
        self.assert_rejected([{'data': 1}, {'partners-offers': 2}, ['Reactive', 2]])


if __name__ == '__main__':
    unittest.main()
