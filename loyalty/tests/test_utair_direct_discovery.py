"""Mutation tests for current landing links, never a saved airline answer."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[1]))
import utair_documents as m
from normalized import content_hash, validate_offer
from test_document_text import pdf, NOW
from test_utair_documents import record

ORIGIN='https://eu-s3.beelinecloud.ru'
URL=ORIGIN+'/utair-log/brand-new-rules.pdf?X-Amz-Signature=FIRST_SECRET'

class Response:
    def __init__(self, data, status=200):
        self.data=data; self.status_code=status; self.headers={}
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def iter_content(self,*args):yield self.data

class DirectDocumentTests(unittest.TestCase):
    def entries(self, url=URL):
        return m.discover_documents('<div><a href="'+url+'">New document</a></div>')
    def fetch(self, value='New current rules 27 percent.',url=URL):
        entry=self.entries(url)[0]
        with patch.object(m.requests,'get',return_value=Response(pdf([value]))) as get:
            rows=m.fetch_document(entry,NOW,'a'*64)
        self.assertEqual(get.call_count,1)
        self.assertEqual(get.call_args.args[0],url)
        return rows
    def test_current_direct_pdf_is_discovered(self):
        entry=self.entries()[0]
        self.assertEqual(entry['kind'],'direct_pdf')
        self.assertEqual(entry['url'],URL)
    def test_document_discovery_keeps_literal_labels_and_context(self):
        raw=('<div>Скидка 1<span>0</span>%. '
             '<a href="'+URL+'">Правила &lt;b&gt;VIP&lt;/b&gt;; &amp;lt;tag&amp;gt;</a></div>')
        entry=m.discover_documents(raw)[0]
        self.assertEqual(entry['labels'],['Правила <b>VIP</b>; &lt;tag&gt;'])
        self.assertEqual(entry['contexts'],['Скидка 10%. Правила <b>VIP</b>; &lt;tag&gt;'])
    def test_encoded_pdf_extension_is_discovered_without_rewriting_path(self):
        for path in ('/utair-log/new%2Erules%2Epdf','/utair-log/new-rules.%70%64%66',
                     '/utair-log/new-rules.%50%44%46'):
            with self.subTest(path=path):
                url=ORIGIN+path+'?X-Amz-Signature=FIRST%2BSECRET%2FVALUE'
                try:entry=self.entries(url)[0]
                except RuntimeError as exc:self.fail('Published encoded PDF was lost: '+str(exc))
                self.assertEqual(entry['kind'],'direct_pdf')
                self.assertEqual(entry['url'],url)
                self.assertEqual(entry['resource']['path'],path)
    def test_encoded_extension_read_preserves_signed_url_and_public_identity(self):
        url=ORIGIN+'/utair-log/new%2Erules%2Epdf?X-Amz-Signature=FIRST%2BSECRET%2FVALUE'
        try:row=self.fetch(url=url)[0]
        except RuntimeError as exc:self.fail('Published encoded PDF was lost: '+str(exc))
        self.assertIn('New current rules 27 percent.',row['conditions_text'])
        self.assertEqual(row['details']['direct_document_resources'][0]['path'],'/utair-log/new%2Erules%2Epdf')
        self.assertEqual(row['source_url'],m.ROOT)
        self.assertNotIn('SECRET',json.dumps(row))
        self.assertNotIn('X-Amz-',json.dumps(row))
        validate_offer(row)
    def test_encoded_pdf_extension_keeps_traversal_rejection(self):
        with self.assertRaises((ValueError,RuntimeError)):
            self.entries(ORIGIN+'/utair-log/%2e%2e/private%2Epdf')
    def test_new_paths_and_rotating_queries_are_not_a_fixed_inventory(self):
        a=self.entries()[0]; b=self.entries(URL.replace('FIRST_SECRET','SECOND_SECRET'))[0]
        c=self.entries(URL.replace('brand-new-rules','other-new-document'))[0]
        self.assertEqual(a['key'],b['key']);self.assertNotEqual(a['key'],c['key'])
    def test_query_variants_deduplicate_and_shortlinks_keep_priority(self):
        html='<a href="'+URL+'">first</a><a href="https://ut0.ru/NewLink">short</a><a href="'+URL.replace('FIRST_SECRET','OTHER')+'">alias</a>'
        entries=m.discover_documents(html)
        self.assertEqual(len(entries),2);self.assertEqual(entries[0]['key'],'NewLink')
        self.assertEqual(entries[1]['labels'],['first','alias'])
    def test_read_uses_fresh_response_and_never_persists_query(self):
        a=self.fetch()[0];b=self.fetch('Changed fresh rules 43 percent.',URL.replace('FIRST_SECRET','SECOND_SECRET'))[0]
        self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['content_sha256'],b['content_sha256'])
        self.assertIn('43 percent',b['conditions_text']);self.assertNotIn('27 percent',b['conditions_text'])
        for row in (a,b):
            self.assertEqual(row['source_url'],m.ROOT)
            self.assertEqual(row['link_kind'],'page_block');self.assertIsNone(row['benefit_url'])
            self.assertNotIn('SECRET',json.dumps(row));self.assertNotIn('X-Amz-',json.dumps(row))
            validate_offer(row)
    def test_no_secret_in_failed_read(self):
        entry=self.entries()[0]
        with patch.object(m.requests,'get',side_effect=m.requests.RequestException('private '+URL)):
            with self.assertRaisesRegex(RuntimeError,'^public_document_transport_failed$'):m.fetch_document(entry,NOW,'a'*64)
    def test_refusal_does_not_replay_old_document(self):
        entry=self.entries()[0]
        with patch.object(m.requests,'get',return_value=Response(b'Forbidden',403)):
            with self.assertRaisesRegex(RuntimeError,'^document_http_403$'):m.fetch_document(entry,NOW,'a'*64)
    def test_old_shortlink_id_survives_same_document_alias(self):
        rows=record('ExistingLink','Same fresh rules')+self.fetch('Same fresh rules')
        merged=m.merge_documents(rows)
        self.assertEqual(len(merged),1);self.assertEqual(merged[0]['id'],rows[0]['id'])
        self.assertEqual(len(merged[0]['details']['direct_document_resources']),1)
        validate_offer(merged[0])
    def test_identical_pdf_aliases_keep_all_discovery_labels_and_contexts(self):
        raw=('<div>Only Bronze tier <a href="'+ORIGIN+'/utair-log/first.pdf">Hotel rules</a></div>'
             '<div>Only Gold tier <a href="'+ORIGIN+'/utair-log/second.pdf">Transfer rules</a></div>')
        entries=m.discover_documents(raw)
        rows=[]
        with patch.object(m.requests,'get',return_value=Response(pdf(['Same document rules for both links.']))):
            for entry in entries:rows.extend(m.fetch_document(entry,NOW,'a'*64))
        merged=m.merge_documents(rows)
        self.assertEqual(len(merged),1)
        row=merged[0]
        self.assertEqual(row['id'],rows[0]['id'])
        self.assertEqual(row['details']['discovery_label'],'Hotel rules')
        self.assertEqual(row['details'].get('discovery_labels'),['Hotel rules','Transfer rules'])
        self.assertEqual(row['details']['discovery_contexts'],
                         ['Only Bronze tier Hotel rules','Only Gold tier Transfer rules'])
        self.assertEqual(len(row['details']['direct_document_resources']),2)
        self.assertEqual(row['conditions_text'],rows[0]['conditions_text'])
        self.assertIn('Same document rules for both links.',row['conditions_text'])
        validate_offer(row)
    def test_untrusted_direct_route_is_not_discovered(self):
        for url in ['https://evil.example/utair-log/a.pdf','https://eu-s3.beelinecloud.ru.evil/utair-log/a.pdf']:
            with self.assertRaisesRegex(RuntimeError,'no_public_document_links_discovered'):self.entries(url)
    def test_malformed_trusted_origin_links_fail_closed(self):
        for url in [URL.replace('https:','http:'),ORIGIN+'/other-bucket/a.pdf',ORIGIN+'/utair-log/../private.pdf',ORIGIN+'/utair-log/%2e%2e/private.pdf',URL.replace('https://','https://user:pass@'),URL+'#section']:
            with self.assertRaises(ValueError):self.entries(url)
    def test_publisher_rejects_forged_path_identity_or_deep_link(self):
        row=self.fetch()[0]
        for mutate in [lambda r:r['details']['direct_document_resources'][0].update(path='/utair-log/other.pdf'),
                       lambda r:r.update(benefit_url=ORIGIN+'/utair-log/brand-new-rules.pdf'),
                       lambda r:r.update(source_url=ORIGIN+'/utair-log/brand-new-rules.pdf'),
                       lambda r:r['details']['direct_document_resources'][0].update(path='/utair-log/a.pdf?secret=1')]:
            bad=copy.deepcopy(row);mutate(bad);bad['content_sha256']=content_hash(bad)
            with self.assertRaises(ValueError):validate_offer(bad)

if __name__=='__main__':unittest.main()
