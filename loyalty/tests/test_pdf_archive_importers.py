"""Fault injection for retained public PDF bytes, without fabricated offer text.

UniCredit bytes and URL are the actually archived source. The EKP assembler
test reuses those bytes solely as an opaque valid PDF transport payload; its
actual captured source metadata is not interpreted as document contents.
"""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))
import ekp_linked_rules as ekp
import rzd_external as rzd
from normalized import validate_offer

SHA='c9db3bc59fea0645579888f4d1a453c1b5089a7accf601878c66ebfc155f2610'
PDF=Path(__file__).parents[2]/'source-documents'/(SHA+'.pdf')
UNICREDIT='https://www.unicreditbank.ru/content/dam/cee2020-pws-ru/banking/primeclub/CashBackRules.pdf'
EKP='https://mpclinic.ru/upload/1689252399.pdf'
NOW='2026-11-15T12:00:00+00:00'


class ImporterOriginalRetentionTests(unittest.TestCase):
    def test_rzd_hard_failure_keeps_source_identity_without_claiming_a_page(self):
        data=PDF.read_bytes()
        with patch.object(rzd,'extract_pdf',side_effect=ValueError('parser_failure')):
            rows=rzd.bank_pdf_records(data,{'url':UNICREDIT,'label':'Правила Программы лояльности'},
                {'id':'parent-bound-by-caller','content_sha256':None},NOW)
        self.assertEqual(len(rows),1)
        row=rows[0];validate_offer(row)
        self.assertEqual(row['source_url'],UNICREDIT)
        self.assertEqual(row['details']['document_sha256'],SHA)
        self.assertEqual(row['record_kind'],'source_observation')
        self.assertEqual(row['benefit_text'],'')
        self.assertNotIn('pages',row['details'])

    def test_ekp_assembler_validates_download_then_keeps_failed_document(self):
        data=PDF.read_bytes()
        entry={'url':EKP,'parents':[{'partner':'Медпомощь 24',
            'source_url':'https://ekp.spb.ru/api/portal/loyalty/partners',
            'label':'Приложению №1','content_sha256':None}]}
        receipt={'url':EKP,'status':200,'bytes':len(data),'sha256':SHA}
        filename=hashlib.sha256(EKP.encode()).hexdigest()+'.pdf'
        audit={'started_at':NOW,'run_id':'archive-test:1','inventory':{},'results':[
            {'url':EKP,'file':filename,'sha256':SHA,'receipt':receipt,'document_error':'ValueError'}],
            'requests':[receipt],'reserved':0}
        base={'run_id':'parent-test:1','observed_at':NOW}
        with tempfile.TemporaryDirectory() as directory:
            objects=Path(directory)/'objects';objects.mkdir();(objects/filename).write_bytes(data)
            with patch.object(ekp,'discover',return_value=([entry],{'gated_parent_count':0,'links':[]})):
                audit['inventory']={'gated_parent_count':0,'links':[]}
                with patch.object(ekp,'extract_pdf',side_effect=AssertionError('publisher must not retry failed OCR')):
                    result=ekp.assemble(base,audit,Path(directory))
            row=result['records'][0];validate_offer(row)
            self.assertEqual(row['record_kind'],'source_observation')
            self.assertEqual(row['partner_name'],'Медпомощь 24')
            self.assertEqual(row['details']['document_sha256'],SHA)
            self.assertEqual(result['sources'][0]['status'],'partial')
            self.assertEqual(row['rates'],[])
            self.assertNotIn('pages',row['details'])
            (objects/filename).write_bytes(b'<html>not the saved PDF</html>')
            with patch.object(ekp,'discover',return_value=([entry],audit['inventory'])):
                with self.assertRaisesRegex(ValueError,'el_object_hash'):
                    ekp.assemble(base,audit,Path(directory))


if __name__=='__main__':unittest.main()
