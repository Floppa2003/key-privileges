"""New partner IDs and altered terms are inputs, not acceptance constants."""
import sys
import copy
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from ekp_catalog import parse_catalog, preview_record
except ImportError:
    parse_catalog = preview_record = None

NOW = '2026-09-15T12:00:00+00:00'
ROOT = 'https://ekp.spb.ru/capabilities/loyalty/'


def card(ident='123', name='Новый партнер', benefit='Скидка 17%', gated=False):
    return f'''<div class="v-card"><div class="v-card-title">{name}</div>
    <div class="v-card-subtitle">{benefit}</div>
    <div class="v-card-text line-clamp-2">Описание {name}</div>
    <div class="v-card-text text-caption">#<span>Спорт</span></div>
    <div class="v-card-actions">{'Требуется авторизация' if gated else ''}
    <a href="/capabilities/loyalty/tiles/{ident}">Подробнее</a>
    <span class="v-chip"><div class="v-chip__content">{benefit}</div></span></div></div>'''


def page(body):
    return '<html><title>Партнеры</title><main><div class="text-h4">Партнеры</div>' + body + '</main></html>'


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(parse_catalog, 'EKP catalog parser is not implemented')

    def test_real_filter_panel_is_not_a_partner(self):
        controls = '<div class="v-card"><div class="v-input">Все регионы</div><span class="v-chip__content">Все</span></div>'
        self.assertEqual(len(parse_catalog(page(controls+card()), ROOT)['cards']), 1)

    def test_new_identity_name_and_rate_are_read(self):
        out = parse_catalog(page(card('987654','Другой партнер','Скидка 23%')), ROOT)
        self.assertEqual(len(out['cards']), 1)
        self.assertEqual(out['cards'][0]['native_id'], '987654')
        self.assertEqual(out['cards'][0]['partner_name'], 'Другой партнер')
        self.assertEqual(out['cards'][0]['benefit_text'], 'Скидка 23%')

    def test_reordered_cards_keep_their_own_terms(self):
        a, b = card('1','А','Скидка 7%'), card('2','Б','Скидка 19%')
        one = parse_catalog(page(a+b), ROOT)['cards']
        two = parse_catalog(page(b+a), ROOT)['cards']
        self.assertEqual({c['native_id']: c for c in one}, {c['native_id']: c for c in two})

    def test_mobile_desktop_benefit_is_not_added_twice(self):
        out = parse_catalog(page(card()), ROOT)['cards'][0]
        self.assertEqual(out['benefit_text'], 'Скидка 17%')

    def test_conflicting_responsive_labels_are_an_error(self):
        raw = card().replace('<div class="v-chip__content">Скидка 17%', '<div class="v-chip__content">Скидка 90%')
        with self.assertRaises(ValueError):
            parse_catalog(page(raw), ROOT)

    def test_footer_suggestions_do_not_become_catalog_cards(self):
        out = parse_catalog(page(card())+'<footer>'+card('777')+'</footer>', ROOT)
        self.assertEqual([c['native_id'] for c in out['cards']], ['123'])

    def test_foreign_link_is_rejected_not_certified(self):
        raw = card().replace('/capabilities/loyalty/tiles/123','https://evil.example/capabilities/loyalty/tiles/123')
        with self.assertRaises(ValueError):
            parse_catalog(page(raw), ROOT)

    def test_credential_query_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_catalog(page(card('123?token=private')), ROOT)

    def test_duplicate_identity_is_not_silently_deduplicated(self):
        with self.assertRaises(ValueError):
            parse_catalog(page(card()+card()), ROOT)

    def test_shell_is_not_an_empty_success(self):
        with self.assertRaises(ValueError):
            parse_catalog(page('Показать еще'), ROOT)

    def test_authentication_notice_is_preserved(self):
        out = parse_catalog(page(card(gated=True)), ROOT)['cards'][0]
        self.assertTrue(out['authentication_required'])

    def test_missing_title_is_not_borrowed_from_neighbor(self):
        raw = card().replace('class="v-card-title"','class="not-title"')
        with self.assertRaises(ValueError):
            parse_catalog(page(raw+card('2')), ROOT)

    def test_preview_does_not_certify_unread_detail(self):
        parsed = parse_catalog(page(card(gated=True)), ROOT)
        row = preview_record(parsed['cards'][0], NOW, parsed['page_sha256'])
        self.assertIsNone(row['benefit_url'])
        self.assertEqual(row['source_url'], ROOT)
        self.assertEqual(row['source_status'], 'public_catalog_preview')
        self.assertTrue(row['details']['authentication_required'])
        self.assertFalse(row['details']['detail_fetched'])
        self.assertEqual(row['promo_codes'], [])

    def test_changed_rate_keeps_id_but_changes_hash(self):
        a = parse_catalog(page(card()), ROOT)
        b = parse_catalog(page(card(benefit='Скидка 21%')), ROOT)
        r1 = preview_record(a['cards'][0], NOW, a['page_sha256'])
        r2 = preview_record(b['cards'][0], NOW, b['page_sha256'])
        self.assertEqual(r1['id'], r2['id'])
        self.assertNotEqual(r1['content_sha256'], r2['content_sha256'])

    def test_mixed_tags_are_not_inferred_as_category_or_regions(self):
        parsed = parse_catalog(page(card().replace('Спорт','Карелия')), ROOT)
        row = preview_record(parsed['cards'][0], NOW, parsed['page_sha256'])
        self.assertIsNone(row['category'])
        self.assertEqual(row['details']['card']['tags'], ['Карелия'])

    def test_absent_auth_notice_does_not_prove_public_redemption(self):
        parsed = parse_catalog(page(card()), ROOT)
        row = preview_record(parsed['cards'][0], NOW, parsed['page_sha256'])
        self.assertIsNone(row['details']['authentication_required'])

    def test_final_tiles_alias_is_retained_as_observed_source(self):
        url = ROOT + 'tiles'
        parsed = parse_catalog(page(card()), url)
        row = preview_record(parsed['cards'][0], NOW, parsed['page_sha256'], catalog_url=url)
        self.assertEqual(row['source_url'], url)

    def test_rehashed_promotion_or_neighbor_text_fails_publisher(self):
        from normalized import validate_offer, content_hash
        parsed = parse_catalog(page(card(gated=True)),ROOT)
        original = preview_record(parsed['cards'][0], NOW, parsed['page_sha256'])
        changes = [
            ('record_kind','partner_offer'), ('benefit_url',original['details']['card']['detail_url']),
            ('partner_name','Чужой партнер'), ('benefit_text','Скидка 90%'),
            ('conditions_text','Чужие условия'), ('source_status','published'),
            ('title','Чужой заголовок'), ('category','Придуманная категория'),
        ]
        for field,value in changes:
            with self.subTest(field=field):
                changed=copy.deepcopy(original)
                changed[field]=value
                changed['content_sha256']=content_hash(changed)
                with self.assertRaises(ValueError): validate_offer(changed)

    def test_nested_card_cannot_insert_neighbor_text(self):
        nested=card().replace('Описание Новый партнер',card('999'))
        with self.assertRaises(ValueError): parse_catalog(page(nested),ROOT)

    def test_preview_evidence_does_not_share_mutable_input_tags(self):
        parsed=parse_catalog(page(card()),ROOT)
        row=preview_record(parsed['cards'][0],NOW,parsed['page_sha256'])
        parsed['cards'][0]['tags'].append('Чужое')
        self.assertEqual(row['details']['card']['tags'],['Спорт'])

    def test_real_publisher_and_common_projection_keep_evidence_only(self):
        from sheets_normalized import prepare, SCHEMAS
        from unified_normalization import make_input, normalize_record
        parsed=parse_catalog(page(card()),ROOT)
        row=preview_record(parsed['cards'][0],NOW,parsed['page_sha256'])
        report=dict(source_id='ekp',name='ЕКП — каталог',root=ROOT,status='partial',
                    discovered=1,normalized=1,failed=1,coverage='preview_only',region=None,
                    errors=[{'phase':'coverage','reason':'unread_details'}],observed_at=NOW)
        out=prepare(dict(schema_version=2,run_id='test',observed_at=NOW,records=[row],sources=[report]))
        fields={k:{'value':v} for k,v in zip(SCHEMAS['parser_offers'],out['parser_offers'][0])}
        raw=make_input(dict(id=row['id'],origin='parser_offers',row=2,fields=fields))
        n=normalize_record(raw,as_of='2026-09-15')
        self.assertEqual(n['quality']['level'],'evidence_only')
        self.assertEqual(n['benefits'],[])
        self.assertEqual(n['codes'],[])
        self.assertIsNone(n['eligibility_verified'])
        self.assertEqual(n['raw']['details']['card'],row['details']['card'])

    def test_card_count_is_not_pinned_to_thirty(self):
        for count in (1, 3, 37):
            self.assertEqual(len(parse_catalog(page(''.join(card(str(i)) for i in range(count))),ROOT)['cards']),count)

if __name__ == '__main__':
    unittest.main()
