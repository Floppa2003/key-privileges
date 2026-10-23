"""Offline contracts. These tests are NOT measurements of Qwen quality or speed."""
import base64
import io
import unittest
import csv
import tempfile
from pathlib import Path
from PIL import Image
import benchmark as b


def png(width, height):
    buf=io.BytesIO()
    Image.new('RGB',(width,height),(17,34,51)).save(buf,format='PNG')
    return buf.getvalue()


class Contracts(unittest.TestCase):
    def test_original_preserves_bytes_and_page_order(self):
        images=[png(1280,1600),png(1280,869)]
        self.assertEqual(b.resized_images(images,0),images)

    def test_resize_preserves_all_pages_and_aspect_ratio(self):
        images=[png(1280,1600),png(1280,869)]
        out=b.resized_images(images,768)
        self.assertEqual(len(out),2)
        self.assertEqual([Image.open(io.BytesIO(x)).size for x in out],[(614,768),(768,521)])
        self.assertEqual(Image.open(io.BytesIO(images[0])).size,(1280,1600))

    def test_small_source_not_upscaled_or_reencoded(self):
        small=png(120,160)
        self.assertEqual(b.resized_images([small],768),[small])

    def test_request_changes_only_image_bytes(self):
        template={'model':'qwen3.5:4b','options':{'seed':1},'messages':[{'role':'system','content':'s'},{'role':'user','content':'Exact text'}]}
        out=b.make_request(template,[b'one',b'two'])
        self.assertEqual(out['messages'][-1]['images'],['b25l','dHdv'])
        del out['messages'][-1]['images']
        self.assertEqual(out,template)
        self.assertNotIn('images',template['messages'][-1])

    def test_order_balanced_across_three_documents(self):
        plan=b.make_plan(['a','b','c'],[0,1024,768],1)
        self.assertEqual([(x['case'],x['edge']) for x in plan], [('a',0),('a',1024),('a',768),('b',1024),('b',768),('b',0),('c',768),('c',0),('c',1024)])

    def test_repeats_retain_every_result_not_best_of(self):
        plan=b.make_plan(['a','b','c'],[0,1024,768],3)
        self.assertEqual(len(plan),27)
        self.assertEqual({x['repeat'] for x in plan},{1,2,3})
        self.assertEqual(len({(x['repeat'],x['case'],x['edge']) for x in plan}),27)

class SummaryContracts(unittest.TestCase):
    def test_timeout_is_not_an_exact_speedup(self):
        rows=[{'repeat':1,'case':'a','edge':0,'status':'timeout','seconds':600,'work_s':None},
              {'repeat':1,'case':'a','edge':768,'status':'completed','seconds':203,'work_s':200}]
        with tempfile.TemporaryDirectory() as tmp:
            b.write_summary(rows,Path(tmp))
            with open(Path(tmp)/'summary.csv') as file: table=list(csv.DictReader(file))
        self.assertEqual(table[1]['speedup_work_vs_original'],'')

    def test_missing_duration_is_not_a_zero_or_a_ratio(self):
        rows=[{'repeat':1,'case':'a','edge':0,'status':'completed','seconds':103,'work_s':100},
              {'repeat':1,'case':'a','edge':768,'status':'completed','seconds':53,'work_s':None}]
        with tempfile.TemporaryDirectory() as tmp:
            # A valid response need not expose every optional telemetry field.
            try:
                b.write_summary(rows,Path(tmp))
            except TypeError as exc:
                self.fail(f'optional telemetry must not crash summary: {exc}')
            with open(Path(tmp)/'summary.csv') as file: table=list(csv.DictReader(file))
        self.assertEqual(table[1]['speedup_work_vs_original'],'')

    def test_ratio_uses_same_document_and_repeat(self):
        rows=[{'repeat':1,'case':'a','edge':0,'status':'completed','seconds':103,'work_s':100},
              {'repeat':1,'case':'a','edge':768,'status':'completed','seconds':53,'work_s':50},
              {'repeat':2,'case':'a','edge':768,'status':'completed','seconds':43,'work_s':40}]
        with tempfile.TemporaryDirectory() as tmp:
            b.write_summary(rows,Path(tmp))
            with open(Path(tmp)/'summary.csv') as file: table=list(csv.DictReader(file))
        self.assertEqual(table[1]['speedup_work_vs_original'],'2.0')
        self.assertEqual(table[2]['speedup_work_vs_original'],'')

if __name__=='__main__': unittest.main()
