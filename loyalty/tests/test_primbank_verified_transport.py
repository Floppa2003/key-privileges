"""Exact public tariff URL with scoped verified national CA trust, never verify=False."""
import asyncio
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]))
from recovered_contract import CA_PROFILE, checked_config, transport_evidence
from recovered_sources import ScopedReader, collect_recovered
from normalized import validate_offer, content_hash
from test_known_pdf import PRIM, NOW
from known_pdf import parse_pdf_pages

SID='af_primbank_rules'
URL='https://www.primbank.ru/d/tariffs-aeroflot-bonus'
def config():return {'id':SID,'name':'PrimBank PDF','url':URL,'mode':'recovered','access_profile':CA_PROFILE}

class VerifiedPdfTests(unittest.TestCase):
    def test_profile_is_exact_endpoint_and_not_system_trust(self):
        self.assertEqual(checked_config(config())['url'],URL)
        for bad in ({**config(),'url':URL+'/other'},{**config(),'url':URL.replace('https:','http:')},{**config(),'access_profile':'insecure'}):
            with self.assertRaises(ValueError):checked_config(bad)
        reader=ScopedReader(config(),{},time.monotonic()+90)
        self.assertIs(reader.verify,True)
        with self.assertRaises(ValueError):reader.allowed('https://www.primbank.ru/private/')
        reader.__exit__()
    def test_binary_pdf_does_not_require_utf8(self):
        reader=ScopedReader(config(),{},time.monotonic()+90)
        data=b'%PDF-1.7\n%\xff\xfe binary'
        with patch.object(reader,'_get',return_value=(200,{},data)):
            self.assertEqual(reader.read(URL)[1],data)
        reader.__exit__()
    def test_legacy_verified_standard_tls_rows_still_validate(self):
        row=parse_pdf_pages(SID,PRIM,NOW,document_sha256='f'*64);validate_offer(row)
        row['details']['transport']={**transport_evidence(SID),'hostname_and_expiry_verified':False}
        row['content_sha256']=content_hash(row)
        with self.assertRaises(ValueError):validate_offer(row)
    def test_binary_response_cannot_promote_a_challenge(self):
        reader=ScopedReader(config(),{},time.monotonic()+90)
        with patch.object(reader,'_get',return_value=(403,{},b'<html>Access denied</html>')):
            with self.assertRaisesRegex(RuntimeError,'http_403'):reader.read(URL)
        reader.__exit__()

class VerifiedPdfRouting(unittest.IsolatedAsyncioTestCase):
    async def test_dispatcher_reuses_existing_pdf_parser_and_records_trust(self):
        import collect_normalized as collector
        import known_pdf
        cfg=next(c for c in json.loads((Path(__file__).parents[1]/'sources_normalized.json').read_text()) if c['id']==SID)
        with patch.object(ScopedReader,'__enter__',return_value=ScopedReader(config(),{},time.monotonic()+90)),patch.object(ScopedReader,'__exit__'),patch.object(ScopedReader,'read',return_value=({},b'%PDF-test')),patch.object(known_pdf,'pdf_pages',return_value=PRIM):
            report,rows=await collector.one(None,cfg,NOW,500)
        self.assertEqual(report['status'],'ok');self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['details']['transport'],transport_evidence(SID))
        validate_offer(rows[0])
