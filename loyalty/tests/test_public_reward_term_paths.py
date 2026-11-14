"""Native Magnit clauses exercise the source-owned term handoff contract."""
import copy
import unittest
from unittest.mock import patch

from public_reward_projection import fields, make_record
from test_observed_campaign_periods import AS_OF, CAPTURE, retained_without_dates
from unified_normalization import normalize_record


SOURCE = 'magnit_partners_public'


class PublicRewardTermPaths(unittest.TestCase):
    def setUp(self):
        capture = CAPTURE['magnit']
        self.fields = fields(SOURCE, capture['evidence'])
        self.raw = retained_without_dates(make_record(SOURCE, capture['evidence'], capture['observed_at']))

    def project(self, derived):
        with patch('public_reward_projection.fields', return_value=derived):
            return normalize_record(self.raw, as_of=AS_OF)

    def test_owned_condition_and_activation_fragments_are_supported(self):
        for path in ('/conditions', '/activation'):
            with self.subTest(path=path):
                derived = copy.deepcopy(self.fields)
                clause = self.raw[path[1:]].splitlines()[0]
                derived['terms'] = [dict(kind='partner_privilege', fragment=clause, path=path,
                                         scope={'source_clause': clause}, standalone_offer=False)]
                n = self.project(derived)
                self.assertEqual(n['benefits'][0]['evidence'], {'path': path, 'text': clause})
                self.assertIs(n['benefits'][0]['standalone_offer'], False)
                self.assertEqual(n['raw'], self.raw)

    def test_scoped_native_caps_link_only_to_the_matching_channel(self):
        derived = copy.deepcopy(self.fields)
        native = (
            ('cashdesk', '2000', '- 2 000 бонусов за покупки на кассе'),
            ('online', '4000', '- или 4 000 бонусов за онлайн-заказы'),
        )
        derived['terms'] = [dict(kind='partner_privilege', fragment=derived['benefit'],
                                 scope={'purchase_channel': channel}) for channel, _, _ in native]
        derived['condition_terms'] = [dict(kind='benefit_cap', value=value, unit='points',
            qualifier='up_to', basis_value='1', basis_unit='month',
            reward_unit='Magnit_bonus_not_cash', fragment=literal,
            scope={'purchase_channel': channel}) for channel, value, literal in native]
        n = self.project(derived)
        caps = {c['scope']['purchase_channel']: c for c in n['conditions'] if c['kind'] == 'benefit_cap'}
        self.assertEqual(set(caps), {'cashdesk', 'online'})
        for benefit in n['benefits']:
            own = benefit['scope']['purchase_channel']
            other = 'online' if own == 'cashdesk' else 'cashdesk'
            self.assertIn(caps[own]['id'], benefit['condition_ids'])
            self.assertNotIn(caps[other]['id'], benefit['condition_ids'])
            self.assertEqual(caps[own]['evidence']['path'], '/conditions')

    def test_default_benefit_path_and_standalone_behavior_are_unchanged(self):
        n = self.project(self.fields)
        self.assertEqual(n['benefits'][0]['evidence']['path'], '/benefit')
        self.assertIs(n['benefits'][0]['standalone_offer'], True)

    def test_foreign_paths_and_other_standalone_overrides_fail(self):
        for field, value, message in (
            ('path', '/details/public_reward_evidence/title', 'term_path'),
            ('standalone_offer', True, 'standalone_override'),
            ('standalone_offer', 0, 'standalone_override'),
        ):
            with self.subTest(field=field, value=value):
                derived = copy.deepcopy(self.fields)
                derived['terms'][0][field] = value
                with self.assertRaisesRegex(ValueError, message):
                    self.project(derived)


if __name__ == '__main__':
    unittest.main()
