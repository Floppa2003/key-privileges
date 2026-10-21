"""Actual PDF geometry changes: executable fixture, no old brand/tier names."""
import io
import shutil
import sys
import unittest
from pathlib import Path
from pypdf import PdfWriter, PdfReader
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
sys.path.insert(0,str(Path(__file__).parents[1]))
from tsvetnoy_source import matrix, source_fields


def document(names, *, offset=25, widths=None, values=None, header=True):
    widths=widths or [130]+[65]*len(names)+[60,100]
    height=650;writer=PdfWriter();page=writer.add_blank_page(offset+sum(widths)+25,height)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    chunks=[]
    def text(x,y,value):
        value=value.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')
        chunks.append(f'BT /F1 10 Tf {x} {y} Td ({value}) Tj ET')
    def row(y,labels):
        x=offset
        for width,label in zip(widths,labels):
            chunks.append(f'{x} {y} {width} 30 re S');text(x+4,y+10,label);x+=width
    if header:row(570,['Brand',*names,'Progress','Notes'])
    text(offset,550,'Floor 1')
    row(500,['Example',*(values or [f'{i+1}%' for i in range(len(names))]),'-','Restrictions'])
    text(offset,470,'Current footnote. No stacking. Verify availability.')
    stream=DecodedStreamObject();stream.set_data('\n'.join(chunks).encode('ascii'))
    page[NameObject('/Contents')]=writer._add_object(stream)
    output=io.BytesIO();writer.write(output);return output.getvalue()


class DynamicMatrix(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(shutil.which('pdftotext'),'PDF extraction tests require poppler-utils')

    def test_new_four_tier_table_on_different_page_width(self):
        names=['Entry','Plus','Max','Explorer']
        rows,notes=matrix(document(names),names)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['tier_names'],names)
        self.assertEqual(rows[0]['cells'][1:-2],['1%','2%','3%','4%'])
        self.assertIn('No stacking',notes)
        self.assertNotIn('Example',notes)

    def test_pdf_column_order_not_the_order_of_html_cards(self):
        names=['Custom','Silver','First','Last']
        rows,_=matrix(document(names,offset=90),list(reversed(names)))
        self.assertEqual(rows[0]['tier_names'],names)

    def test_variable_column_widths_and_count(self):
        names=['A','B','C','D','E']
        rows,_=matrix(document(names,widths=[170,40,50,60,70,80,65,140]),names)
        self.assertEqual(len(rows[0]['cells']),8)
        self.assertEqual(rows[0]['cells'][1:6],['1%','2%','3%','4%','5%'])

    def test_unresolved_cell_is_not_silently_skipped(self):
        with self.assertRaisesRegex(ValueError,'row_shape'):
            matrix(document(['A','B'],values=['1%','unknown']),['A','B'])

    def test_header_mismatch_does_not_borrow_previous_tier_names(self):
        with self.assertRaisesRegex(ValueError,'header'):
            matrix(document(['A','B']),['A','Different'])

    def test_continuation_without_header_requires_same_geometry(self):
        writer=PdfWriter()
        for data in (document(['A','B']),document(['A','B'],header=False)):
            writer.add_page(PdfReader(io.BytesIO(data)).pages[0])
        out=io.BytesIO();writer.write(out)
        rows,_=matrix(out.getvalue(),['A','B'])
        self.assertEqual([r['tier_names'] for r in rows],[['A','B'],['A','B']])

    def test_changed_continuation_geometry_without_header_fails(self):
        writer=PdfWriter()
        for data in (document(['A','B']),document(['A','B'],offset=70,header=False)):
            writer.add_page(PdfReader(io.BytesIO(data)).pages[0])
        out=io.BytesIO();writer.write(out)
        with self.assertRaisesRegex(ValueError,'header'):matrix(out.getvalue(),['A','B'])

    def test_each_page_header_can_reorder_columns(self):
        writer=PdfWriter()
        for names in (['A','B'],['B','A']):writer.add_page(PdfReader(io.BytesIO(document(names))).pages[0])
        out=io.BytesIO();writer.write(out)
        rows,_=matrix(out.getvalue(),['A','B'])
        self.assertEqual([r['tier_names'] for r in rows],[['A','B'],['B','A']])

    def test_dynamic_columns_reach_scoped_benefits(self):
        names=['Entry','Plus','Max','Explorer']
        rows,notes=matrix(document(names),names)
        e=dict(projection_version=2,tier_names=names,native='brand:Floor 1:Example',url='https://tsvetnoy.com/pdf/current.pdf',
            page_sha256='a'*64,document={'key':'current.pdf'},row=rows[0],footnotes=notes,tier_conditions='Current thresholds.',registration='Register.')
        f=source_fields(e)
        self.assertEqual([(t['scope']['member_tier'],t['value']) for t in f['terms']],list(zip(names,['1','2','3','4'])))

    def test_status_accumulation_note_is_not_a_reward(self):
        from expansion_common import ExcludedOffer
        names=['A','B'];rows,notes=matrix(document(names,values=['-','-']),names)
        e=dict(projection_version=2,tier_names=names,native='brand:Floor 1:Example',url='https://tsvetnoy.com/pdf/current.pdf',
            page_sha256='a'*64,document={'key':'current.pdf'},row=rows[0],footnotes=notes,tier_conditions='Thresholds',registration='Register')
        e['row']['cells'][-1]='Только накопления'
        with self.assertRaisesRegex(ExcludedOffer,'accumulation_only'):source_fields(e)
        e['row']['cells'][-1]='Подарок по новому абонементу'
        self.assertEqual(source_fields(e)['kind'],'source_observation')
        e['row']['cells'][-1]='Новая карта в подарок при покупке'
        self.assertEqual(source_fields(e)['terms'][0]['kind'],'partner_privilege')


if __name__=='__main__':unittest.main()
