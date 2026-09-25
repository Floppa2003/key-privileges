import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import merchant_blocks_v2 as v2

T={'merchant':'Synthetic','program':'Example Club','aliases':['EC']}

class BlocksV2(unittest.TestCase):
    def test_list_items_are_independent_evidence_blocks(self):
        md=('## Есть ли скидки?\n\n'
            '- Для всех участников скидка 5%.\n'
            '- -15% при оплате курса картой EC.\n'
            '- Можно оплатить материнским капиталом.\n')
        d=v2.build(md,url='https://example.test/',observed_at='x',completeness='source_excerpt')
        items=[b for b in d['blocks'] if b['kind']=='list_item']
        self.assertEqual(len(items),3)
        ekp=[b for b in items if '-15%' in b['text']][0]
        self.assertNotIn('скидка 5%',ekp['text'])
        self.assertNotIn('материнским',ekp['text'])

    def test_sentences_in_one_paragraph_are_separate_blocks(self):
        md=('## EC\n\n'
            'Новые клиенты получают скидку 20% на весь срок. '
            'Действующие клиенты получают скидку 10%. '
            'Подробности доступны в приложении EC.\n')
        d=v2.build(md,url='https://example.test/',observed_at='x')
        sentences=[b for b in d['blocks'] if b['kind']=='sentence']
        self.assertEqual(len(sentences),3)
        self.assertIn('20%',sentences[0]['text']);self.assertNotIn('10%',sentences[0]['text'])
        self.assertIn('10%',sentences[1]['text']);self.assertNotIn('20%',sentences[1]['text'])

    def test_every_block_is_exact_original_slice(self):
        md='## EC\r\n\r\nПервая скидка 10%. Вторая скидка 20%.\r\n- Условие A.\r\n- Условие B.\r\n'
        d=v2.build(md,url='https://example.test/',observed_at='x')
        for block in d['blocks']:
            self.assertEqual(block['text'],md[block['start']:block['end']])

    def test_prompt_preamble_has_no_concrete_example_block_ids(self):
        d=v2.build('## EC\n\nДержателям EC скидка 20%.\n',url='https://example.test/',observed_at='x')
        value=v2.prompt(T,d)
        preamble=value.split('TARGET and SOURCE:',1)[0]
        self.assertNotIn('b0001',preamble)
        self.assertNotIn('b0002',preamble)
        self.assertIn('"program":[]',preamble)
        self.assertIn('separate offer',preamble.lower())

    def test_prompt_requires_code_evidence_refs_and_complete_shape(self):
        d=v2.build('## EC\n\nДержателям EC скидка 20% по промокоду.\n',url='https://example.test/',observed_at='x')
        preamble=v2.prompt(T,d).split('TARGET and SOURCE:',1)[0]
        self.assertIn('refs MUST be nonempty',preamble)
        self.assertIn('uncertainties',preamble)
        self.assertIn('state=no_offer',preamble)

    def test_v2_does_not_change_v1_version_contract(self):
        self.assertEqual(v2.VERSION,'merchant-blocks-v2')

if __name__=='__main__':unittest.main()
