"""Resort list ownership and attribution at the public source read boundary."""
import hashlib
import sys
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parents[1]))
import mantera_hotel as hotel
import mantera_partners as partners
import mantera_source as mantera
from normalized import validate_offer
from test_public_reward_sources import NOW, common, html

CLAUSE = (
    'Уже сейчас в отелях Долина 960, Кортьярд и Марриотт бонусы можно и копить, '
    'и тратить. В остальных отелях Курорта Красная Поляна пока доступно только '
    'начисление, но совсем скоро появится и списание'
)


def resort(markup):
    soup = BeautifulSoup(html('mantera-redemption-list.html'), 'html.parser')
    owner = next(n for n in soup.select('.markdown') if 'Уже сейчас в отелях' in n.get_text())
    owner.clear()
    for child in list(BeautifulSoup(markup, 'html.parser').contents):
        owner.append(child)
    return str(soup)


def legacy_list():
    """Synthetic layout variation of the same historical paired fixture."""
    soup = BeautifulSoup(html('mantera-redemption.html'), 'html.parser')
    clause = next(n for n in soup.select('.markdown p') if 'Уже сейчас в отелях' in n.get_text())
    clause.name = 'li'
    clause.wrap(soup.new_tag('ul'))
    return str(soup)


class ManteraResortOwnership(unittest.TestCase):
    def test_current_public_list_owns_only_redemption_clause(self):
        raw = html('mantera-redemption-list.html')
        evidence = partners.parse_resort(raw)
        self.assertEqual(evidence['clause'], CLAUSE)
        self.assertEqual(evidence['url'], partners.RESORT_URL)
        self.assertEqual(evidence['page_sha256'], hashlib.sha256(raw.encode()).hexdigest())
        self.assertEqual([r[2] for r in evidence['table']], ['3 %', '5 %', '7 %', '10 %', '15 %'])
        for neighbour in ('3 000', 'ко дню рождения', 'Присоединяйтесь', 'до 50% от покупки'):
            self.assertNotIn(neighbour, evidence['clause'])

    def test_existing_paragraph_still_parses(self):
        evidence = partners.parse_resort(html('mantera-redemption.html'))
        self.assertEqual(evidence['clause'], CLAUSE + '. Присоединяйтесь, чтобы получать '
                         'максимум от каждого дня в горах и за их пределами.')

    def test_nested_paragraph_is_one_owner_and_excludes_wrapper_text(self):
        raw = resort('<ul><li>Пояснение списка.<p>' + CLAUSE + '</p>'
                     '<p>Также 3 000 бонусов ко дню рождения.</p></li></ul>')
        self.assertEqual(partners.parse_resort(raw)['clause'], CLAUSE)

    def test_inline_markup_and_layout_whitespace_preserve_the_named_clause(self):
        literal = CLAUSE.replace('Уже сейчас', 'Уже\nсейчас').replace('960', '<strong>960</strong>')
        self.assertEqual(partners.parse_resort(resort('<ul><li>' + literal + '</li></ul>'))['clause'], CLAUSE)

    def test_distinct_matching_sibling_blocks_are_ambiguous_even_when_identical(self):
        for markup in ('<p>{0}</p><ul><li>{0}</li></ul>', '<ul><li>{0}</li><li>{0}</li></ul>'):
            with self.subTest(markup=markup), self.assertRaisesRegex(ValueError, 'mantera_resort_redemption_clause'):
                partners.parse_resort(resort(markup.format(CLAUSE)))

    def test_wrapper_with_its_own_matching_clause_is_not_deduplicated(self):
        with self.assertRaisesRegex(ValueError, 'mantera_resort_redemption_clause'):
            partners.parse_resort(resort('<ul><li>' + CLAUSE + '<p>' + CLAUSE + '</p></li></ul>'))

    def test_general_intro_and_outside_markdown_do_not_supply_hotel_redemption(self):
        raw = resort('<p>Копите бонусы и оплачивайте ими до 50% от покупки у нас и у партнеров.</p>')
        for candidate in (raw, raw + '<ul><li>' + CLAUSE + '</li></ul>'):
            with self.subTest(outside=candidate != raw), self.assertRaisesRegex(ValueError, 'mantera_resort_redemption_clause'):
                partners.parse_resort(candidate)

    def test_list_layout_keeps_historical_source_to_common_values_and_identity(self):
        original, _ = partners.parse_pair(html('mantera-partners.html'), html('mantera-redemption.html'), NOW)
        rows, inventory = partners.parse_pair(html('mantera-partners.html'), legacy_list(), NOW)
        self.assertEqual({r['id'] for r in rows}, {r['id'] for r in original})
        self.assertEqual(len(inventory['names']), 11)
        for row in rows:
            validate_offer(row)
            benefits = common(row)['benefits']
            self.assertEqual([b['value'] for b in benefits if b['kind'] == 'earn_points'], ['3', '5', '7', '10', '15'])
            expected = ['20', '20', '30', '40', '50'] if row['partner_name'] in partners.REDEMPTION_ALIASES.values() else []
            self.assertEqual([b['value'] for b in benefits if b['kind'] == 'redeem_points'], expected)
            self.assertTrue(all(b['reward_unit'] == 'Mantera_bonus_not_cash' for b in benefits))

    def test_list_layout_keeps_cross_source_rate_conflict_guard(self):
        with self.assertRaisesRegex(ValueError, 'mantera_partner_source_rate_conflict'):
            partners.parse_pair(html('mantera-partners.html'), legacy_list().replace('3 %', '4 %'), NOW)

    def test_unmapped_list_name_does_not_grant_redemption_to_other_hotels(self):
        raw = legacy_list().replace('Долина 960, Кортьярд и Марриотт', 'Новый отель Марриотт')
        rows, _ = partners.parse_pair(html('mantera-partners.html'), raw, NOW)
        for row in rows:
            self.assertIn('Новый отель Марриотт', row['conditions_text'])
            self.assertFalse(any(b['kind'] == 'redeem_points' for b in common(row)['benefits']))


class ManteraSourceErrorAttribution(unittest.IsolatedAsyncioTestCase):
    async def collect_with_pages(self, overrides):
        pages = {
            hotel.URL: html('mantera-congress.html'),
            partners.ROSTER_URL: html('mantera-partners.html'),
            partners.RESORT_URL: html('mantera-redemption.html'),
            **overrides,
        }

        @asynccontextmanager
        async def public_source(browser, url):
            client = AsyncMock()
            value = pages[url]
            if isinstance(value, Exception):
                client.read.side_effect = value
            else:
                client.read.return_value = value
            yield client

        client = AsyncMock()
        client.browser = object()
        client.deadline = float('inf')
        client.read.return_value = html('mantera-faq.html')
        report = {'errors': []}
        with patch('public_transport.PublicSource', public_source):
            rows = await mantera.collect(client, {'id': mantera.SOURCE, 'url': mantera.URL}, report, NOW, 500)
        self.assertEqual(len(rows), 6)
        self.assertNotIn('mantera_public_inventory', report)
        self.assertEqual(len(report['errors']), 1)
        self.assertEqual(report['errors'][0]['phase'], 'public_partner_inventory')
        return report['errors'][0]

    async def test_resort_parse_failure_reports_resort_url_and_keeps_independent_rows(self):
        error = await self.collect_with_pages({partners.RESORT_URL: resort('<p>Общие условия.</p>')})
        self.assertEqual(error['url'], partners.RESORT_URL)
        self.assertEqual(error['reason'], 'mantera_resort_redemption_clause')

    async def test_roster_parse_failure_still_reports_roster_url(self):
        error = await self.collect_with_pages({partners.ROSTER_URL: '<h1>Нет списка участников</h1>'})
        self.assertEqual(error['url'], partners.ROSTER_URL)
        self.assertEqual(error['reason'], 'mantera_partner_page_identity')

    async def test_resort_read_failure_reports_resort_url_without_changing_reason(self):
        for failure, reason in ((RuntimeError('http_503'), 'http_503'), (TimeoutError('read timed out'), 'TimeoutError')):
            with self.subTest(reason=reason):
                error = await self.collect_with_pages({partners.RESORT_URL: failure})
                self.assertEqual(error['url'], partners.RESORT_URL)
                self.assertEqual(error['reason'], reason)

    async def test_cross_source_disagreement_reports_both_sources(self):
        error = await self.collect_with_pages({partners.RESORT_URL: html('mantera-redemption.html').replace('3 %', '4 %')})
        self.assertEqual(error['url'], partners.ROSTER_URL)
        self.assertEqual(error['reason'], 'mantera_partner_source_rate_conflict')
        self.assertEqual(error['source_urls'], [partners.ROSTER_URL, partners.RESORT_URL])


if __name__ == '__main__':
    unittest.main()
