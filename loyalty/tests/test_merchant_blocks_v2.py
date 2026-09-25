import sys
import unittest
import json
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

    def test_scoped_prompt_excludes_neighbor_list_promotions(self):
        md=('## Есть ли скидки?\n\n'
            '- Для всех участников скидка 5%.\n'
            '- -15% при оплате курса картой EC.\n'
            '- Можно оплатить материнским капиталом.\n')
        d=v2.build(md,url='https://example.test/',observed_at='x')
        value=v2.scoped_prompt(T,d)
        payload=json.loads(value.split('TARGET and SOURCE:',1)[1])
        source=''.join(x['text'] for x in payload['blocks'])
        self.assertIn('-15%',source)
        self.assertNotIn('скидка 5%',source)
        self.assertNotIn('материнским капиталом',source)
        self.assertIn('Есть ли скидки?',source)

    def test_scoped_prompt_keeps_full_section_when_heading_names_programme(self):
        md=('## Example Club\n\n'
            'Держателям карты скидка 20%.\n\n'
            'Не суммируется с другими скидками.\n')
        d=v2.build(md,url='https://example.test/',observed_at='x')
        payload=json.loads(v2.scoped_prompt(T,d).split('TARGET and SOURCE:',1)[1])
        source=''.join(x['text'] for x in payload['blocks'])
        self.assertIn('скидка 20%',source)
        self.assertIn('Не суммируется',source)

    def test_scoped_prompt_strengthens_code_date_and_duplicate_contracts(self):
        d=v2.build('## EC\n\nДержателям EC скидка 20%.\n',url='https://example.test/',observed_at='x')
        preamble=v2.scoped_prompt(T,d).split('TARGET and SOURCE:',1)[0]
        self.assertIn('literal requires a nonempty',preamble)
        self.assertIn('Do not emit duplicate offers',preamble)
        self.assertIn('at most one functional role',preamble)

    def test_v2_does_not_change_v1_version_contract(self):
        self.assertEqual(v2.VERSION,'merchant-blocks-v2')

    def test_duplicate_audience_benefit_pair_is_not_multiple_offer_variants(self):
        md=('## Example Club\n\n'
            'Держателям EC предоставляется скидка 20%.\n\n'
            'Промокод EC20.\n')
        d=v2.build(md,url='https://example.test/',observed_at='x')
        base={'program':['b0000'],'audience':['b0001'],'benefit':['b0001'],
              'conditions':[],'redemption':[],
              'code':{'state':'not_stated','value':'','refs':[]},
              'dates':[],'uncertainties':[]}
        out={'source_sha256':d['source_sha256'],'state':'candidates','notes':'',
             'offers':[base,{**base,'redemption':['b0002'],
                 'code':{'state':'literal','value':'EC20','refs':['b0002']}}]}
        result=v2.check(T,d,out)
        self.assertIn('duplicate_offer_variant',result['problems'])

    def test_scoped_prompt_keeps_following_access_condition_without_program_name(self):
        md=('Партнёр EC предоставляет специальное предложение, подробнее в личном кабинете.\n\n'
            'Для просмотра условий необходимо авторизоваться в личном кабинете.\n')
        d=v2.build(md,url='https://example.test/',observed_at='x',completeness='source_excerpt')
        payload=json.loads(v2.scoped_prompt(T,d).split('TARGET and SOURCE:',1)[1])
        source=''.join(x['text'] for x in payload['blocks'])
        self.assertIn('Партнёр EC предоставляет специальное предложение',source)
        self.assertIn('Для просмотра условий необходимо авторизоваться',source)

    def test_program_identity_can_be_anchored_by_explicit_audience_benefit(self):
        target={'merchant':'Museum','program':'Единая карта петербуржца',
                'aliases':['ЕКП','Единой карты петербуржца']}
        md=('## В музей — с Единой картой петербуржца\n\n'
            'Держатели Единой карты петербуржца могут получить скидку 10% на входной билет.\n')
        d=v2.build(md,url='https://example.test/',observed_at='2026-09-25')
        out={'source_sha256':d['source_sha256'],'state':'candidates','notes':'',
             'offers':[{'program':['b0000'],'audience':['b0001'],'benefit':['b0001'],
                        'conditions':[],'redemption':[],
                        'code':{'state':'not_stated','value':'','refs':[]},
                        'dates':[],'uncertainties':[]}]}
        result=v2.check(target,d,out)
        self.assertNotIn('wrong_program',result['problems'])
        self.assertEqual(result['status'],'references_checked_needs_semantic_review')

    def test_duplicate_refs_inside_one_field_are_idempotent(self):
        md=('## Example Club\n\n'
            'Держателям EC предоставляется скидка 20%.\n\n'
            'Скидка не суммируется с другими предложениями.\n')
        d=v2.build(md,url='https://example.test/',observed_at='x')
        out={'source_sha256':d['source_sha256'],'state':'candidates','notes':'',
             'offers':[{'program':['b0000'],'audience':['b0001'],'benefit':['b0001'],
                        'conditions':['b0002','b0002','b0002'],'redemption':[],
                        'code':{'state':'not_stated','value':'','refs':[]},
                        'dates':[],'uncertainties':[]}]}
        result=v2.check(T,d,out)
        self.assertNotIn('duplicate_reference',result['problems'])
        self.assertEqual([x['id'] for x in result['offers'][0]['fields']['conditions']],['b0002'])

    def test_scoped_prompt_keeps_anaphoric_same_discount_continuation(self):
        md=('## Новости\n\n'
            'Держатели EC получают скидку 5% на индивидуальное посещение.\n\n'
            'Такая же скидка 5% предоставляется на организованную экскурсию для группы до 25 человек.\n\n'
            'Единственное условие - наличие EC у организатора группы.\n\n'
            'Другая акция: скидка 50% для всех посетителей.\n')
        d=v2.build(md,url='https://example.test/',observed_at='x',completeness='source_excerpt')
        payload=json.loads(v2.scoped_prompt(T,d).split('TARGET and SOURCE:',1)[1])
        source=''.join(x['text'] for x in payload['blocks'])
        self.assertIn('Держатели EC получают скидку 5%',source)
        self.assertIn('Такая же скидка 5%',source)
        self.assertIn('Единственное условие',source)
        self.assertNotIn('Другая акция',source)

if __name__=='__main__':unittest.main()
