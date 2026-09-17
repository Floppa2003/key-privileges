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


class RemovedNodeWhitespace(unittest.TestCase):
    def test_removed_nodes_do_not_leave_noncanonical_whitespace(self):
        for gap in ('\n<script>ignored()</script>\n', '\n<style>ignored</style>\n',
                    ' <iframe></iframe> ', '\n<form><input value="secret"></form>\n'):
            for container in ('head','body'):
                with self.subTest(gap=gap,container=container):
                    raw=html().decode().replace('</'+container+'>',gap+'</'+container+'>')
                    first=e.clean_html(raw)
                    self.assertEqual(first,e.clean_html(first.encode()))
                    self.assertNotIn('ignored',first)
                    self.assertNotIn('secret',first)

    def test_canonical_roundtrip_preserves_owned_text_and_tables(self):
        raw=html().decode().replace('</main>',
            '<p>Ставка 17% &amp; ограничения</p><pre>  A\n\n B  </pre>'
            '<table><tr><td>Категория</td><td>0%</td></tr></table>'
            '\n<script>ignored()</script>\n</main>')
        clean=e.clean_html(raw)
        title,conditions=e.html_fields(clean)
        from bs4 import BeautifulSoup
        soup=BeautifulSoup(clean,'html.parser')
        self.assertEqual(soup.pre.get_text(),'  A\n\n B  ')
        self.assertEqual([n.get_text() for n in soup.select('td')],['Категория','0%'])
        self.assertIn('Ставка 17% & ограничения',conditions)
        for _ in range(3):
            again=e.clean_html(clean.encode())
            self.assertEqual(again,clean)
            self.assertEqual(e.html_fields(again),(title,conditions))
            clean=again

    def test_canonical_output_remains_fail_closed_for_tampered_content(self):
        from bs4 import BeautifulSoup
        clean=e.clean_html(html())
        bad=clean.replace('</body>','<script>new()</script></body>')
        self.assertNotEqual(bad,e.clean_html(bad))
        attrs=clean.replace('<main>', '<main onclick="bad()">')
        self.assertNotEqual(attrs,e.clean_html(attrs))
        with self.assertRaises(ValueError):
            e.clean_html(clean.replace('</body>','<input type="password"></body>'))

if __name__=='__main__':unittest.main()
