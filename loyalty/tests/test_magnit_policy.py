"""No network: distinguish a literal empty-query rule from a site-wide ban."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from protego import Protego
from magnit_policy import QuerylessMagnitPolicy
A='LoyaltyCatalogResearchBot'

class QuerylessRules(unittest.TestCase):
    def test_pinned_bug_reproduction_and_narrow_fix(self):
        rules='User-agent: *\nDisallow: /*?$'
        self.assertFalse(Protego.parse(rules).can_fetch('https://magnit.ru/partners',A))
        p=QuerylessMagnitPolicy(rules)
        for path in ('/partners','/partners/','/partners/1768'):
            self.assertTrue(p.can_fetch('https://magnit.ru'+path,A))
        self.assertFalse(p.can_fetch('https://magnit.ru/partners?',A))
    def test_explicit_catalogue_ban_preserved(self):
        p=QuerylessMagnitPolicy('User-agent: *\nDisallow: /*?$\nDisallow: /partners')
        self.assertFalse(p.can_fetch('https://magnit.ru/partners/1768',A))
    def test_site_wide_ban_preserved(self):
        p=QuerylessMagnitPolicy('User-agent: *\nDisallow: /')
        self.assertFalse(p.can_fetch('https://magnit.ru/partners',A))
    def test_specific_allow_and_agent_groups(self):
        rules='User-agent: other\nDisallow: /*?$\nUser-agent: *\nDisallow: /partners\nAllow: /partners/1768\nCrawl-delay: 2'
        p=QuerylessMagnitPolicy(rules)
        self.assertFalse(p.can_fetch('https://magnit.ru/partners',A));self.assertTrue(p.can_fetch('https://magnit.ru/partners/1768',A))
        self.assertEqual(p.crawl_delay(A),2)
    def test_non_card_urls_unchanged(self):
        rules='User-agent: *\nDisallow: /*?$\nDisallow: /account'
        p=QuerylessMagnitPolicy(rules);base=Protego.parse(rules)
        for u in ('https://magnit.ru/account','https://elsewhere.test/partners','http://magnit.ru/partners','https://magnit.ru/partners?a=1','https://magnit.ru/partners%3F'):
            self.assertEqual(p.can_fetch(u,A),base.can_fetch(u,A))

if __name__=='__main__':unittest.main()
