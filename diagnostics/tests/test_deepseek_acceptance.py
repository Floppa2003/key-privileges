import io
from pathlib import Path
import sys
import unittest
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deepseek_acceptance import tile_png

class TilingTests(unittest.TestCase):
    def test_all_rows_survive_in_order_including_short_last_tile(self):
        image=Image.new('RGB',(5,2050))
        for y in range(image.height):
            for x in range(image.width): image.putpixel((x,y),(x,y%256,y//256))
        buf=io.BytesIO();image.save(buf,format='PNG')
        pieces=tile_png(buf.getvalue())
        self.assertEqual(len(pieces),3)
        restored=Image.new('RGB',image.size)
        for i,raw in enumerate(pieces):
            part=Image.open(io.BytesIO(raw));restored.paste(part,(0,i*1024))
        self.assertEqual(restored.tobytes(),image.tobytes())
    def test_tall_source_is_not_silently_truncated(self):
        buf=io.BytesIO();Image.new('RGB',(1,40961)).save(buf,format='PNG')
        with self.assertRaisesRegex(ValueError,'image_budget_no_truncation'):tile_png(buf.getvalue())

if __name__=='__main__':unittest.main()
