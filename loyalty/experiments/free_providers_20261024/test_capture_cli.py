import unittest, json, io
from PIL import Image
import capture_cli as m
class Contract(unittest.TestCase):
 def test_tiles_keep_every_pixel(self):
  im=Image.new('RGB',(600,2050),(10,20,30));buf=io.BytesIO();im.save(buf,format='PNG')
  tiles=m.tiles(buf.getvalue());self.assertEqual([Image.open(io.BytesIO(x)).size for x in tiles],[(600,1024),(600,1024),(600,2)])
 def test_no_silent_large_capture_truncation(self):
  im=Image.new('RGB',(10,50001));buf=io.BytesIO();im.save(buf,format='PNG')
  with self.assertRaises(ValueError):m.tiles(buf.getvalue())
 def test_no_tools_or_paid_helpers(self):
  conf=m.cli_config('opencode/glm-5.3-flash-free','extract only')
  self.assertEqual(conf['permission'],{'*':'deny'})
  self.assertEqual(conf['small_model'],conf['model'])
  self.assertEqual(conf['agent']['extract']['steps'],1)
  self.assertFalse(conf['compaction']['auto'])
 def test_cli_events_not_reasoning(self):
  s='\n'.join(json.dumps(x)for x in [{'type':'reasoning','part':{'text':'ignore me'}},{'type':'text','part':{'text':'{"code":"7429"}'}},{'type':'step_finish','part':{'reason':'stop'}}])
  self.assertEqual(m.cli_answer(s),'{"code":"7429"}')
 def test_failed_cli_not_answer(self):
  with self.assertRaises(ValueError):m.cli_answer(json.dumps({'type':'error','error':{'message':'denied'}}))
 def test_missing_finish_not_success(self):
  with self.assertRaises(ValueError):m.cli_answer(json.dumps({'type':'text','part':{'text':'{}'}}))
if __name__=='__main__':unittest.main()
