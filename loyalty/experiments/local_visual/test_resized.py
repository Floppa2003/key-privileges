import io
import unittest
from PIL import Image
try:
    import resized_retry as retry
except ImportError:
    retry=None

class ReducedImages(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(retry,'Reduced-image retry is not implemented')

    def image(self,width,height):
        out=io.BytesIO();Image.new('RGB',(width,height)).save(out,format='PNG');return out.getvalue()

    def test_every_page_is_kept_with_same_aspect_ratio(self):
        values=retry.reduce_images([self.image(300,600),self.image(600,300)],200)
        self.assertEqual([Image.open(io.BytesIO(x)).size for x in values],[(100,200),(200,100)])

    def test_small_page_is_not_upscaled_or_reencoded(self):
        raw=self.image(100,200)
        self.assertEqual(retry.reduce_images([raw],768),[raw])

    def test_bad_size_or_unreadable_image_refused(self):
        for edge in (0,-1,True):
            with self.assertRaises(ValueError):retry.reduce_images([self.image(100,200)],edge)
        with self.assertRaises(ValueError):retry.reduce_images([b'not an image'],768)

if __name__=='__main__':unittest.main()
