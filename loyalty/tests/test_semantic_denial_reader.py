"""Owned denial survives public publication and the actual catalogue reader."""
import copy
import unittest

from catalogue_view import record_row
from normalized import make_offer
from test_dom_card_boundaries import project


NOW = '2026-11-13T00:00:00+00:00'
MODIFIED_DENIALS = (
    ('уже не', ('предоставляется', 'действует', 'распространяется на алкоголь')),
    ('больше не', ('предоставляется', 'действует', 'распространяется на алкоголь')),
    ('временно не', ('предоставляется', 'действует', 'распространяется на алкоголь')),
    ('сейчас не', ('предоставляется', 'действует', 'распространяется на алкоголь')),
    ('пока не', ('предоставляется', 'действует', 'распространяется на алкоголь')),
    ('не будет', ('предоставляться', 'действовать', 'распространяться на алкоголь')),
    ('вам не', ('предоставляется', 'действует', 'распространяется на алкоголь')),
)


class SemanticDenialReader(unittest.TestCase):
    def public_chain(self, benefit, conditions='', record_kind='partner_offer'):
        source = make_offer('moskvich', 'semantic-denial-fixture', 'Карта', 'Example',
                            benefit, 'https://moskvichmag.ru/programma-loyalnosti/',
                            NOW, conditions=conditions, record_kind=record_kind)
        before = copy.deepcopy(source)
        common = project(source)
        reader, reason = record_row(common, NOW[:10])
        self.assertEqual(source, before)
        self.assertEqual(common['raw']['benefit'], benefit)
        self.assertEqual(common['raw']['conditions'], conditions)
        return source, common, reader, reason

    def test_inactive_only_numeric_discount_never_becomes_a_reader_offer(self):
        for amount in ('10', '17,5', '23'):
            for denial in ('больше не действует', 'временно не предоставляется',
                           'не предоставляется'):
                body = f'Скидка {amount}% {denial}.'
                with self.subTest(body=body):
                    source, common, reader, _ = self.public_chain(body)
                    self.assertEqual(source['rates'], [])
                    self.assertEqual(common['benefits'], [])
                    self.assertIsNone(reader)

    def test_product_exclusion_keeps_visible_rate_in_either_field(self):
        for amount, value in (('10', '10'), ('17,5', '17.5'), ('23', '23')):
            for in_benefit in (False, True):
                with self.subTest(amount=amount, in_benefit=in_benefit):
                    offer = f'Скидка {amount}% на меню.'
                    exclusion = 'Акция не действует на алкоголь.'
                    benefit = offer + ' ' + exclusion if in_benefit else offer
                    conditions = '' if in_benefit else exclusion
                    source, common, reader, reason = self.public_chain(benefit, conditions)
                    self.assertEqual([(r['kind'], r['value']) for r in source['rates']],
                                     [('discount', value)])
                    self.assertEqual([(b['kind'], b['value']) for b in common['benefits']],
                                     [('discount', value)])
                    self.assertIsNone(reason)
                    self.assertEqual(reader[2], offer)
                    self.assertIn(exclusion, reader[5])

    def test_complete_closure_hides_offer_in_either_field(self):
        for closure in ('Акция не действует.', 'Акция больше не действует.',
                        'Акция уже не действует.', 'Акция временно не действует.',
                        'Акция сейчас не действует.', 'Акция пока не действует.',
                        'Акция завершена.'):
            for in_benefit in (False, True):
                with self.subTest(closure=closure, in_benefit=in_benefit):
                    benefit = 'Скидка 10% на меню.'
                    if in_benefit:
                        benefit += ' ' + closure
                    _, _, reader, reason = self.public_chain(
                        benefit, '' if in_benefit else closure)
                    self.assertIsNone(reader)
                    self.assertEqual(reason, 'неактивное предложение')

    def test_temporal_partial_closure_preserves_visible_offer_in_either_field(self):
        for modifier in ('уже', 'больше', 'временно', 'сейчас', 'пока'):
            for restriction in ('на алкоголь', 'в понедельник'):
                for in_benefit in (False, True):
                    exclusion = f'Акция {modifier} не действует {restriction}.'
                    with self.subTest(exclusion=exclusion, in_benefit=in_benefit):
                        offer = 'Скидка 10% на меню.'
                        _, common, reader, reason = self.public_chain(
                            offer + ' ' + exclusion if in_benefit else offer,
                            '' if in_benefit else exclusion)
                        self.assertEqual([(b['kind'], b['value']) for b in common['benefits']],
                                         [('discount', '10')])
                        self.assertIsNone(reason)
                        self.assertEqual(reader[2], offer)
                        self.assertIn(exclusion, reader[5])

    def test_denial_stays_local_to_its_own_equal_or_different_rate(self):
        for denied, live, value in (('10', '10', '10'), ('23', '17,5', '17.5')):
            for separator in ('. ', ', но ', '; ', '\n'):
                for reverse in (False, True):
                    inactive = f'Скидка {denied}% больше не действует'
                    active = f'Скидка {live}% на меню'
                    parts = [active, inactive] if reverse else [inactive, active]
                    body = separator.join(parts) + '.'
                    with self.subTest(body=body):
                        source, common, reader, reason = self.public_chain(body)
                        self.assertEqual([(r['kind'], r['value']) for r in source['rates']],
                                         [('discount', value)])
                        self.assertEqual([(b['kind'], b['value']) for b in common['benefits']],
                                         [('discount', value)])
                        self.assertIsNone(reason)
                        self.assertIsNotNone(reader)

    def test_live_nonnumeric_perks_do_not_need_numeric_benefits(self):
        for body in ('Бокал игристого в подарок при заказе меню.',
                     'Приоритетное обслуживание при предъявлении карты.',
                     'Скидка 23% больше не действует. Бокал игристого в подарок при заказе меню.'):
            with self.subTest(body=body):
                _, common, reader, reason = self.public_chain(body)
                self.assertFalse(any(b['value'] is not None for b in common['benefits']))
                self.assertIsNone(reason)
                self.assertIsNotNone(reader)

    def test_legacy_reader_fallback_cannot_resurrect_explicit_denial(self):
        _, common, reader, _ = self.public_chain(
            'Скидка 17,5% временно не предоставляется.', record_kind='legacy_offer')
        self.assertEqual(common['benefits'], [])
        self.assertIsNone(reader)

    def test_conflicting_schedules_in_different_fields_do_not_prove_expiry(self):
        _, _, reader, reason = self.public_chain(
            'Скидка 10% на меню. Акция действует до 10.11.2026.',
            'Акция действует до 10.11.2031.')
        self.assertIsNone(reason)
        self.assertIsNotNone(reader)

    def test_dated_whole_offer_completion_keeps_its_existing_closure_meaning(self):
        for closure in ('Предложение завершено 10 ноября 2026.',
                        'Кампания закончилась 10 ноября 2026.'):
            for in_benefit in (False, True):
                with self.subTest(closure=closure, in_benefit=in_benefit):
                    benefit = 'Скидка 10% на меню.'
                    if in_benefit:
                        benefit += ' ' + closure
                    _, _, reader, reason = self.public_chain(
                        benefit, '' if in_benefit else closure)
                    self.assertIsNone(reader)
                    self.assertEqual(reason, 'неактивное предложение')

    def test_unquantified_nonapplicability_does_not_supply_an_offer(self):
        for body in ('Скидка не распространяется.',
                     'Скидка не распространяется на алкоголь.'):
            with self.subTest(body=body):
                _, common, reader, _ = self.public_chain(body)
                self.assertEqual(common['benefits'], [])
                self.assertIsNone(reader)

    def test_denied_free_delivery_does_not_become_a_reader_benefit(self):
        for kind in ('partner_offer', 'legacy_offer'):
            with self.subTest(kind=kind):
                source, common, reader, _ = self.public_chain(
                    'Бесплатная доставка не предоставляется.', record_kind=kind)
                self.assertEqual(source['rates'], [])
                self.assertEqual(common['benefits'], [])
                self.assertIsNone(reader)

    def test_denied_delivery_cannot_displace_a_live_sibling_headline(self):
        inactive = 'Бесплатная доставка не предоставляется.'
        active = 'Скидка 17% на меню.'
        for parts in ((inactive, active), (active, inactive)):
            with self.subTest(parts=parts):
                source, common, reader, reason = self.public_chain(' '.join(parts))
                self.assertEqual([(r['kind'], r['value']) for r in source['rates']],
                                 [('discount', '17')])
                self.assertEqual([(b['kind'], b['value']) for b in common['benefits']],
                                 [('discount', '17')])
                self.assertIsNone(reason)
                self.assertEqual(reader[2], active)

    def test_positive_delivery_and_gift_keep_their_reader_benefit(self):
        for body in ('Бесплатная доставка предоставляется.',
                     'Бесплатная доставка заказа предоставляется.',
                     'Бокал игристого в подарок при заказе меню.'):
            with self.subTest(body=body):
                source, common, reader, reason = self.public_chain(body)
                self.assertEqual(source['rates'], [])
                self.assertFalse(any(b['value'] is not None for b in common['benefits']))
                self.assertIsNone(reason)
                self.assertEqual(reader[2], body)

    def test_temporal_cancellation_never_creates_a_positive_numeric_benefit(self):
        for modifier in ('сейчас', 'пока'):
            for amount in ('10', '17,5'):
                body = f'Скидка {amount}% {modifier} не действует.'
                with self.subTest(body=body):
                    source, common, reader, _ = self.public_chain(body)
                    self.assertEqual(source['rates'], [])
                    self.assertEqual(common['benefits'], [])
                    self.assertIsNone(reader)

    def test_temporal_cancellation_is_local_to_its_numeric_occurrence(self):
        for modifier in ('сейчас', 'пока'):
            for denied in ('17', '23'):
                inactive = f'Скидка {denied}% {modifier} не действует.'
                active = 'Скидка 17% на меню.'
                for parts in ((inactive, active), (active, inactive)):
                    with self.subTest(modifier=modifier, parts=parts):
                        source, common, reader, reason = self.public_chain(' '.join(parts))
                        self.assertEqual([(r['kind'], r['value']) for r in source['rates']],
                                         [('discount', '17')])
                        self.assertEqual([(b['kind'], b['value']) for b in common['benefits']],
                                         [('discount', '17')])
                        self.assertIsNone(reason)
                        self.assertEqual(reader[2], active)

    def test_unquantified_discount_denial_cannot_erase_an_affirmative_perk(self):
        for active in ('Бесплатная доставка предоставляется',
                       'Бокал игристого в подарок предоставляется'):
            for inactive in ('скидка не предоставляется', 'скидка не действует',
                             'скидка не распространяется на алкоголь'):
                for parts in ((active, inactive), (inactive, active)):
                    body = ', а '.join(parts) + '.'
                    with self.subTest(body=body):
                        source, common, reader, reason = self.public_chain(body)
                        self.assertEqual(source['rates'], [])
                        self.assertFalse(any(b['value'] is not None for b in common['benefits']))
                        if 'в подарок' in active:
                            self.assertIn('gift', [b['kind'] for b in common['benefits']])
                        self.assertIsNone(reason)
                        self.assertIn(active, reader[2])

    def test_unquantified_denial_only_discount_stays_excluded(self):
        for kind in ('partner_offer', 'legacy_offer'):
            for body in ('Скидка не предоставляется.', 'Скидка не действует.',
                         'Скидка не распространяется.',
                         'Скидка не распространяется на алкоголь.'):
                with self.subTest(kind=kind, body=body):
                    _, common, reader, _ = self.public_chain(body, record_kind=kind)
                    self.assertEqual(common['benefits'], [])
                    self.assertIsNone(reader)

    def test_coordinated_nonnumeric_perks_share_their_plural_denial(self):
        for kind in ('partner_offer', 'legacy_offer'):
            for modifier in ('', 'сейчас ', 'пока '):
                body = f'Бесплатная доставка и подарок {modifier}не предоставляются.'
                with self.subTest(kind=kind, body=body):
                    source, common, reader, _ = self.public_chain(body, record_kind=kind)
                    self.assertEqual(source['rates'], [])
                    self.assertEqual(common['benefits'], [])
                    self.assertIsNone(reader)

    def test_shared_denial_reaches_a_recognized_gift_in_either_component_order(self):
        for first, second in (('Бесплатная доставка', 'комплиментарный напиток'),
                              ('Комплиментарный напиток', 'бесплатная доставка'),
                              ('Бесплатная доставка', 'бокал в подарок'),
                              ('Бокал в подарок', 'бесплатная доставка')):
            for modifier in ('', 'сейчас '):
                body = f'{first} и {second} {modifier}не предоставляются.'
                with self.subTest(body=body):
                    source, common, reader, _ = self.public_chain(body)
                    self.assertEqual(source['rates'], [])
                    self.assertEqual(common['benefits'], [])
                    self.assertIsNone(reader)

    def test_live_coordination_and_separate_denials_keep_the_live_perk(self):
        for body in (
            'Бесплатная доставка и подарок предоставляются.',
            'Бесплатная доставка и подарок предоставляются, но скидка не предоставляется.',
            'Бесплатная доставка предоставляется, а подарок не предоставляется.',
            'Бесплатная доставка предоставляется и подарок не предоставляется.',
            'Бесплатная доставка, а подарок не предоставляется.',
            'Бесплатная доставка и подарок не предоставляется.',
            'Комплиментарный напиток предоставляется и бесплатная доставка не предоставляется.',
            'Комплиментарный напиток и бесплатная доставка не предоставляется.',
        ):
            with self.subTest(body=body):
                _, common, reader, reason = self.public_chain(body)
                self.assertFalse(any(b['value'] is not None for b in common['benefits']))
                self.assertIsNone(reason)
                self.assertIn('доставка', reader[2])

    def test_denied_coordination_does_not_displace_a_live_sibling(self):
        inactive = 'Бесплатная доставка и подарок сейчас не предоставляются.'
        active = 'Скидка 17% на меню.'
        for parts in ((inactive, active), (active, inactive)):
            with self.subTest(parts=parts):
                source, common, reader, reason = self.public_chain(' '.join(parts))
                self.assertEqual([(r['kind'], r['value']) for r in source['rates']],
                                 [('discount', '17')])
                self.assertEqual([(b['kind'], b['value']) for b in common['benefits']],
                                 [('discount', '17')])
                self.assertIsNone(reason)
                self.assertEqual(reader[2], active)

    def test_supported_modifier_matrix_keeps_unquantified_denials_excluded(self):
        for modifier, predicates in MODIFIED_DENIALS:
            for predicate in predicates:
                for kind in ('partner_offer', 'legacy_offer'):
                    body = f'Скидка {modifier} {predicate}.'
                    with self.subTest(body=body, kind=kind):
                        source, common, reader, _ = self.public_chain(body, record_kind=kind)
                        self.assertEqual(source['rates'], [])
                        self.assertEqual(common['benefits'], [])
                        self.assertIsNone(reader)

    def test_modified_unquantified_denial_cannot_erase_or_displace_a_live_perk(self):
        for modifier, predicates in MODIFIED_DENIALS:
            for predicate in predicates:
                inactive = f'Скидка {modifier} {predicate}'
                for active in ('Бесплатная доставка предоставляется',
                               'Бокал игристого в подарок предоставляется'):
                    for parts in ((inactive, active), (active, inactive)):
                        for separator in ('. ', ', а '):
                            body = separator.join(parts) + '.'
                            with self.subTest(body=body):
                                _, common, reader, reason = self.public_chain(body)
                                self.assertFalse(any(b['value'] is not None for b in common['benefits']))
                                self.assertIsNone(reason)
                                if separator == '. ':
                                    self.assertEqual(reader[2], active + '.')
                                else:
                                    self.assertIn(active, reader[2])

    def test_modified_unquantified_restriction_keeps_a_live_quantified_discount(self):
        active = 'Скидка 10% на меню.'
        for modifier, predicates in MODIFIED_DENIALS:
            for predicate in predicates:
                restriction = f'Скидка {modifier} {predicate}.'
                for parts in ((restriction, active), (active, restriction)):
                    with self.subTest(parts=parts):
                        source, common, reader, reason = self.public_chain(' '.join(parts))
                        self.assertEqual([(r['kind'], r['value']) for r in source['rates']],
                                         [('discount', '10')])
                        self.assertEqual([(b['kind'], b['value']) for b in common['benefits']],
                                         [('discount', '10')])
                        self.assertIsNone(reason)
                        self.assertEqual(reader[2], active)
                        self.assertIn(restriction, reader[5])

    def test_modified_quantified_product_exclusion_preserves_its_discount(self):
        for modifier, predicates in MODIFIED_DENIALS:
            body = f'Скидка 10% {modifier} {predicates[2]}.'
            with self.subTest(body=body):
                source, common, reader, reason = self.public_chain(body)
                self.assertEqual([(r['kind'], r['value']) for r in source['rates']],
                                 [('discount', '10')])
                self.assertEqual([(b['kind'], b['value']) for b in common['benefits']],
                                 [('discount', '10')])
                self.assertIsNone(reason)
                self.assertEqual(reader[2], body)


if __name__ == '__main__':
    unittest.main()
