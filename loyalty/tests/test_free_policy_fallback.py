"""Exercise the actual HTTP->browser policy fallback, never bypass a refusal."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).parents[1]))
import free_access_probe as p
from test_free_access_probe import KEY, ROOTS, USAGE, Response, page, document, response_for

URL = 'https://ekp.spb.ru/robots.txt'

def browser_policy(target=URL, rules='User-agent: *\nAllow: /'):
    return '<html data-loyalty-probe-location="'+target+'"><body><pre>'+rules+'</pre></body></html>'


if __name__=='__main__':unittest.main()

class DocumentBaseTests(unittest.TestCase):
    def test_actual_browser_base_resolves_relative_catalogue_links(self):
        url='https://coralbonus.ru/klub-privilegii/'
        raw=document(url).replace('<head>','<head><base href="https://coralbonus.ru/">').replace('/partner/123','katalog/')
        cleaned,meta=p.sanitized_page(raw,url)
        self.assertIn('href="https://coralbonus.ru/katalog/"',cleaned)
        self.assertNotIn('klub-privilegii/katalog',cleaned)
        self.assertEqual(meta['document_base_url'],'https://coralbonus.ru/')

    def test_foreign_or_unsafe_base_is_not_silently_followed(self):
        for base in ('https://foreign.example/','http://coralbonus.ru/','javascript:alert(1)'):
            raw=document('https://coralbonus.ru/klub-privilegii/').replace('<head>','<head><base href="'+base+'">')
            with self.subTest(base=base),self.assertRaises(p.ProbeError):
                p.sanitized_page(raw,'https://coralbonus.ru/klub-privilegii/')
