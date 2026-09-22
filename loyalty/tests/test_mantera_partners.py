"""Actual source DOM and negative canaries for named participant/earning scope."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).parents[1]))
import mantera_partners as p
import mantera_source as m
import mantera_hotel as h
from test_public_reward_sources import html, common, NOW
from catalogue_view import record_row
from normalized import validate_offer, content_hash


def pair(a=None, b=None):
    return p.parse_pair(a or html('mantera-partners.html'), b or html('mantera-redemption.html'), NOW)


def report(rows, meta):
    return {'source_id':m.SOURCE, 'status':'ok', 'errors':[], 'normalized':len(rows),
            'observed_at':NOW, 'mantera_public_inventory':meta}


class PublicManteraPartners(unittest.TestCase):
    def test_reads_all_eleven_names_despite_the_six_counter(self):
        rows, meta = pair()
        self.assertEqual((len(meta['names']), meta['declared_count'], len(rows)), (11,6,10))
        self.assertNotIn(p.CONGRESS, [r['partner_name'] for r in rows])
        for row in rows:
            self.assertIn('source_partner_counter_conflicts_with_named_roster',row['warnings'])
            self.assertIn('именованных позиций в списке: 11',row['conditions_text'])
            validate_offer(row)

    def test_only_exact_three_hotels_receive_spending_caps(self):
        rows, _ = pair()
        for r in rows:
            n = common(r)
            expected = r['partner_name'] in p.REDEMPTION_ALIASES.values()
            earned = [x for x in n['benefits'] if x['kind']=='earn_points']
            spent = [x for x in n['benefits'] if x['kind']=='redeem_points']
            self.assertEqual([x['value'] for x in earned], ['3','5','7','10','15'])
            self.assertEqual([x['value'] for x in spent], ['20','20','30','40','50'] if expected else [])
            self.assertTrue(all(x['scope']['hotel']==r['partner_name'] for x in n['benefits']))
            view, reason = record_row(n, NOW[:10])
            self.assertIsNone(reason)
            for clause in ('до оформления', 'невозможно', 'промокода', '24 месяца'):
                self.assertIn(clause, view[4]+'\n'+view[5])
            if expected:
                self.assertIn(p.RESORT_URL, view[5])
            else:
                self.assertIn('отдельно не подтверждена', view[5])
                self.assertNotIn('Оплата накопленными', view[2])

    def test_unknown_roster_item_does_not_inherit_marriott_spending(self):
        s = BeautifulSoup(html('mantera-partners.html'),'html.parser')
        node=s.new_tag('li'); node.string='Новый Марриотт другой город'
        s.select('.accordion__item-content ul')[0].append(node)
        rows, meta=pair(str(s))
        r=next(r for r in rows if r['partner_name']=='Новый Марриотт другой город')
        self.assertNotIn('redeem_points', [b['kind'] for b in common(r)['benefits']])
        self.assertEqual(len(meta['names']),12)

    def test_names_are_stable_across_layout_order_and_stars(self):
        rows, _=pair(); s=BeautifulSoup(html('mantera-partners.html'),'html.parser')
        ul=s.select('.accordion__item-content ul')[0]
        ul.insert(0,ul.find_all('li',recursive=False)[-1].extract())
        reordered,_=pair(str(s))
        self.assertEqual({r['id'] for r in rows},{r['id'] for r in reordered})
        self.assertEqual(p.native_id('Долина 960 4*'),p.native_id('Долина 960'))

    def test_empty_duplicate_and_paginated_roster_fail(self):
        for mode in ('empty','duplicate','pagination'):
            s=BeautifulSoup(html('mantera-partners.html'),'html.parser')
            ul=s.select('.accordion__item-content ul')[0]
            if mode=='empty': ul.clear()
            elif mode=='duplicate': ul.append(copy.copy(ul.li))
            else:
                n=s.new_tag('a',attrs={'class':'load-more'});ul.parent.append(n)
            with self.assertRaises(ValueError): pair(str(s))

    def test_missing_critical_terms_and_rate_conflict_fail(self):
        s=BeautifulSoup(html('mantera-partners.html'),'html.parser')
        next(n for n in s.select('.accordion__item') if h.QUESTIONS[0] in n.get_text()).decompose()
        with self.assertRaises(ValueError): pair(str(s))
        with self.assertRaisesRegex(ValueError,'source_rate_conflict'):
            pair(b=html('mantera-redemption.html').replace('3 %','4 %'))

    def test_new_redemption_alias_needs_review_instead_of_guessing(self):
        with self.assertRaisesRegex(ValueError,'unreviewed_name_mapping'):
            pair(b=html('mantera-redemption.html').replace('Долина 960, Кортьярд и Марриотт','Неизвестный отель'))

    def test_rehash_cannot_change_identity_or_promote_unknown_spending(self):
        rows,_=pair()
        for field,value in [('partner_name','Sochi Park'),('conditions_text',''),('source_url','https://sochiparkhotel.ru/'),('warnings',[])]:
            r=copy.deepcopy(rows[0]);r[field]=value;r['content_sha256']=content_hash(r)
            with self.assertRaises(ValueError):validate_offer(r)

    def test_inventory_health_uses_id_set_not_magic_six_or_sixteen(self):
        rows,meta=pair();all_rows=m.parse(html('mantera-faq.html'),NOW)+[h.parse(html('mantera-congress.html'),NOW)]+rows
        self.assertTrue(p.health(report(all_rows,meta),all_rows))
        self.assertFalse(p.health(report(all_rows[:-1],meta),all_rows[:-1]))
        damaged=copy.deepcopy(all_rows);damaged[-1]['id']=damaged[-2]['id']
        self.assertFalse(p.health(report(damaged,meta),damaged))
        r=report(all_rows,meta);r['status']='partial';r['errors']=[{'reason':'timeout'}]
        self.assertFalse(p.health(r,all_rows))

    def test_unrelated_navigation_and_invitation_not_in_reader(self):
        # Fixture does not contain unrelated hotel navigation, prices or scripts.
        rows,_=pair()
        for r in rows:
            self.assertNotIn('Новый год 2027',r['benefit_text'])
            self.assertNotIn('Фильтр вакансий',r['conditions_text'])
            self.assertNotIn('Присоединяйтесь,',r['conditions_text'])


class PublicManteraPartial(unittest.IsolatedAsyncioTestCase):
    async def test_partner_failure_keeps_successful_faq_and_hotel(self):
        c=AsyncMock();c.browser=object();c.deadline=float('inf');c.read.return_value=html('mantera-faq.html')
        report={'errors':[]}
        with patch('mantera_partners.collect',side_effect=RuntimeError('http_403')), patch('public_transport.PublicSource') as context:
            context.return_value.__aenter__.return_value.read.return_value=html('mantera-congress.html')
            records=await m.collect(c,{'id':m.SOURCE,'url':m.URL},report,NOW,500)
        self.assertEqual(len(records),6)
        self.assertEqual(report['errors'][-1]['phase'],'public_partner_inventory')
        self.assertNotIn('mantera_public_inventory',report)
