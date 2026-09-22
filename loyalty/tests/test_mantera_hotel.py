"""Replay the hotel's actual public participation page, not a six-hotel guess."""
import copy, sys, unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).parents[1]))
import mantera_hotel as h
import mantera_source as m
from test_public_reward_sources import html, common, NOW
from catalogue_view import record_row

class ManteraHotelTests(unittest.TestCase):
    def test_named_hotel_and_all_tier_earning_rates(self):
        r=h.parse(html('mantera-congress.html'),NOW)
        self.assertEqual(r['partner_name'],'Mantera Resort & Congress')
        n=common(r)
        self.assertEqual([b['value'] for b in n['benefits']],['3','5','7','10','15'])
        self.assertTrue(all(b['kind']=='earn_points' for b in n['benefits']))
        self.assertTrue(all('annual_spend_clause' in b['scope'] for b in n['benefits']))
        reader,reason=record_row(n,NOW[:10]);self.assertIsNone(reason)
        for x in ('до оформления','невозможно','не подтверждена','только накапливать'):
            self.assertIn(x,reader[5])
    def test_hotel_not_inferred_from_generic_group_page(self):
        s=BeautifulSoup(html('mantera-congress.html'),'html.parser')
        node=next(n for n in s.select('p') if 'включая отель '+h.NAME in n.get_text())
        node.string='Группа объединяет разные отели.'
        raw=str(s)
        with self.assertRaises(ValueError):h.parse(raw,NOW)
    def test_missing_conditions_or_duplicate_table_fails(self):
        for bad in ('condition','table'):
            s=BeautifulSoup(html('mantera-congress.html'),'html.parser')
            if bad=='condition':s.select('.MuiAccordion-root')[0].decompose()
            else:s.body.append(copy.copy(s.table))
            with self.assertRaises(ValueError):h.parse(str(s),NOW)
    def test_hotel_rate_change_is_not_hardcoded(self):
        old=h.parse(html('mantera-congress.html'),NOW)
        s=BeautifulSoup(html('mantera-congress.html'),'html.parser')
        s.select('tbody tr')[0].select('td')[2].string='4%'
        new=h.parse(str(s),NOW)
        self.assertEqual(old['id'],new['id'])
        self.assertEqual(common(new)['benefits'][0]['value'],'4')

class ManteraPartialTests(unittest.IsolatedAsyncioTestCase):
    async def test_hotel_failure_keeps_five_successful_faq_rows_and_partial_evidence(self):
        client=AsyncMock();client.browser=object();client.deadline=float('inf')
        client.read.return_value=html('mantera-faq.html')
        report={'errors':[]}
        with patch('public_transport.PublicSource') as context:
            context.return_value.__aenter__.side_effect=RuntimeError('http_403')
            rows=await m.collect(client,{'id':m.SOURCE,'url':m.URL},report,NOW,500)
        self.assertEqual(len(rows),5)
        self.assertEqual(report['errors'][0]['reason'],'http_403')
        self.assertEqual(report['discovered'],6)
