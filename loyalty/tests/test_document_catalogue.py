"""Archive lookup uses public source metadata, never inferred PDF benefits."""
import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
from document_catalogue import document_sources, build_documents, document_digest
from catalogue_view import record_row
from test_catalogue_view import record

SHA = '905bb3b03f3b98709054b14c5ae08974a6f7be775857819cf8cd2cb688be683b'
URL = 'https://rgo.ru/upload/medialibrary/2ed/jm89ty2fg8j8an3g362l5uq6lij95owe/Moya_Kompaniya_RGO_belaya_20.01.26.pdf'
PROGRAM = 'Программа лояльности членов РГО'
LABEL = 'Специальные тарифные условия для членов РГО со скидкой до 35%'


def source(*, visual=False):
    return dict(id='0a0098138bc98b72304e07f0c5401e911d158db35381124ea068e52a56a30167' if visual else
        '83d74bac9b968c1dbd428d957cbd805cfa4872e39ca4f707c0bae92ec9967ce4',
        origin='parser_offers', source_row=574 if visual else 971,
        partner='Билайн' if visual else '', program=PROGRAM,
        title='Билайн' if visual else 'Презентация PowerPoint',
        kind='partner_offer' if visual else 'program_rules', source_url=URL,
        observed_at='2026-09-14T13:52:41.717848+00:00' if visual else '2026-11-14T12:19:32.114244+00:00',
        source_status='published' if visual else 'public_rules_ocr_unverified',
        details={'document_sha256':SHA,
                 'extraction_method':'digest_bound_visual_review' if visual else 'live_pdf_native_text_or_ocr',
                 'discovery_label':LABEL, 'ocr_pages':0 if visual else 1})


class DocumentProjectionTests(unittest.TestCase):
    def test_same_bytes_and_program_recover_partner_without_promoting_ocr_to_benefit(self):
        inputs=[source(),source(visual=True)]; before=copy.deepcopy(inputs)
        rows=build_documents(document_sources(inputs))
        self.assertEqual(len(rows),1)
        row=rows[0]
        self.assertEqual(row[0],'Билайн')
        self.assertEqual(row[1],PROGRAM)
        self.assertIn('Требует просмотра',row[3])
        self.assertIn(URL,row[4])
        self.assertTrue(row[5].endswith('/'+SHA+'.pdf'))
        self.assertEqual(row[6],inputs[0]['observed_at'])
        self.assertEqual(row[8],SHA)
        self.assertEqual(inputs,before)

    def test_unknown_partner_stays_findable_by_document_and_discovery_label(self):
        row=build_documents(document_sources([source()]))[0]
        self.assertEqual(row[0],'Партнёр не указан')
        self.assertIn(LABEL,' '.join(row))
        self.assertNotIn('Билайн',row[0])

    def test_newer_parse_observation_replaces_old_failure_status_for_the_same_bytes(self):
        older = source()
        older['observed_at'] = '2026-11-13T12:19:32.114244+00:00'
        older['origin'] = 'parser_documents_archive'
        older['details'].update(extraction_method='source_pdf_original_only',
                                document_errors=[{'reason': 'RuntimeError'}])
        current = source()
        row = build_documents(document_sources([older, current, source(visual=True)]))[0]
        self.assertEqual(row[0], 'Билайн')
        self.assertIn('OCR не проверен', row[3])
        self.assertNotIn('текст не извлечён', row[3])
        # Failed parts at the latest observation still require review.
        older['observed_at'] = current['observed_at']
        row = build_documents(document_sources([older, current]))[0]
        self.assertIn('текст не извлечён', row[3])

    def test_partners_are_not_borrowed_across_programmes(self):
        other=source(visual=True);other['program']='Backit — денежный кешбэк'
        rows=build_documents(document_sources([source(),other]))
        self.assertEqual(len(rows),2)
        rgo=next(r for r in rows if r[1]==PROGRAM)
        self.assertEqual(rgo[0],'Партнёр не указан')

    def test_missing_archived_bytes_keeps_original_url_without_fake_copy(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'PDF_ARCHIVE_DIR':tmp}):
            row=build_documents(document_sources([source()]))[0]
        self.assertEqual(row[5],'')
        self.assertEqual(row[4],URL)
        self.assertIn('Копия не сохранена',row[3])

    def test_original_only_failure_and_archived_bulk_are_still_listed(self):
        raw=source();raw['kind']='source_observation'
        raw['details'].update(extraction_method='source_pdf_original_only',document_part={'number':1,'total':5},page_count=20)
        raw['origin']='parser_documents_archive';raw['source_status']='archived'
        row=build_documents(document_sources([raw]))[0]
        self.assertIn('Требует просмотра',row[3])
        self.assertIn('текст не извлечён',row[3])
        self.assertIn('parser_documents_archive',row[9])

    def test_real_image_pdf_without_ocr_is_marked_as_requiring_viewing(self):
        from document_text import extract_pdf, document_records
        original=Path(__file__).parents[2]/'source-documents'/(SHA+'.pdf')
        doc=extract_pdf(original.read_bytes(),allow_ocr=False)
        self.assertEqual(doc['ocr_pages'],0)
        self.assertEqual(doc['pages'][0]['method'],'missing_text')
        parsed=document_records('rgo','pdf:beeline',PROGRAM,None,URL,
            '2026-11-15T12:00:00+00:00',doc,
            parent_source='https://rgo.ru/membership/loyalty-program/',label=LABEL)
        raw=source()
        raw.update(details=parsed[0]['details'],source_status=parsed[0]['source_status'])
        row=build_documents(document_sources([raw]))[0]
        self.assertIn('Требует просмотра',row[3])
        self.assertIn('текст извлечён не полностью',row[3])

    def test_offer_copy_column_is_verified_and_does_not_change_offer_cells(self):
        n=record(LABEL,partner='Билайн',program=PROGRAM,source_url=URL,details={'document_sha256':SHA})
        row,_=record_row(n,'2026-11-15')
        self.assertEqual(len(row),18)
        self.assertEqual(row[9],URL)
        self.assertTrue(row[17].endswith('/'+SHA+'.pdf'))
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'PDF_ARCHIVE_DIR':tmp}):
            missing,_=record_row(n,'2026-11-15')
        self.assertEqual(missing[:17],row[:17]);self.assertEqual(missing[17],'')

    def test_tsvetnoy_page_hash_is_only_pdf_hash_for_document_bound_brand(self):
        raw={'source_url':'https://tsvetnoy.com/pdf/22b576a39b.pdf','details':{
            'public_reward_evidence':{'url':'https://tsvetnoy.com/pdf/22b576a39b.pdf',
                'document':{'key':'22b576a39b.pdf'},'page_sha256':SHA}}}
        self.assertEqual(document_digest(raw),SHA)
        raw['details']['public_reward_evidence']['url']='https://tsvetnoy.com/loyalty/'
        self.assertEqual(document_digest(raw),'')


if __name__=='__main__':unittest.main()
