"""An owned single claim may treat BR as whitespace without merging blocks."""
import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from html_text import html_text
from normalized import normalize_rates


class HtmlSoftBreaks(unittest.TestCase):
    def test_opt_in_soft_breaks_preserve_real_paragraph_boundaries(self):
        html = '<p>Скидка<br>15%</p><p>Предоплата<br>50%</p>'
        self.assertEqual(html_text(html), 'Скидка\n15%\nПредоплата\n50%')
        value = html_text(html, br_separator=' ')
        self.assertEqual(value, 'Скидка 15%\nПредоплата 50%')
        self.assertEqual([(x['kind'], x['value']) for x in normalize_rates(value)],
                         [('discount', '15')])

    def test_soft_breaks_do_not_join_different_blocks_into_a_rate(self):
        html = '<p>Скидка</p><p>15%</p><li>Кешбэк<br>5%</li><li>Комиссия 20%</li>'
        value = html_text(html, br_separator=' ')
        self.assertEqual(value, 'Скидка\n15%\nКешбэк 5%\nКомиссия 20%')
        self.assertEqual([(x['kind'], x['value']) for x in normalize_rates(value)],
                         [('cashback', '5')])

    def test_opt_in_keeps_inline_tokens_entities_and_original_dom(self):
        dom = BeautifulSoup('<p>SUM<span>MER</span>26<br>&lt;VIP&gt; &amp;lt;tag&amp;gt;</p>', 'html.parser')
        before = str(dom)
        self.assertEqual(html_text(dom, br_separator=' '), 'SUMMER26 <VIP> &lt;tag&gt;')
        self.assertEqual(str(dom), before)


if __name__ == '__main__':
    unittest.main()
