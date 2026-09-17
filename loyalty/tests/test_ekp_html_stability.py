"""Stable sanitized source bytes; absent H1 is not absent page content."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
import ekp_linked_rules as e
from test_ekp_linked_rules import html

class HtmlStability(unittest.TestCase):
    def test_document_prologue_does_not_change_on_reparse(self):
        raw=b'<!DOCTYPE html>\n'+html()+b'\n\n'
        cleaned=e.clean_html(raw)
        self.assertEqual(cleaned,e.clean_html(cleaned.encode()))
        self.assertIn('Условия услуги',cleaned)

    def test_title_without_h1_is_source_identity_not_invented_title(self):
        for title in ('Программа для участников','Обновленные публичные условия'):
            raw=html().decode().replace('<h1>Условия услуги</h1>','').replace('Публичные условия',title)
            actual,body=e.html_fields(e.clean_html(raw))
            self.assertEqual(actual,title)
            self.assertIn('Покупка производится в кассе',body)

    def test_multiple_owned_headings_still_require_review(self):
        with self.assertRaises(ValueError):
            e.html_fields(e.clean_html(html().replace(b'</main>',b'<h1>Other</h1></main>')))

    def test_title_cannot_promote_empty_javascript_shell(self):
        with self.assertRaises(ValueError):
            e.html_fields(e.clean_html(b'<html><head><title>Public page</title></head><body><script>load()</script></body></html>'))

if __name__=='__main__':unittest.main()
