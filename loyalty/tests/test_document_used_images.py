"""Only images used by page drawing can make its native text incomplete."""
import io
import sys
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

sys.path.insert(0, str(Path(__file__).parents[1]))
from document_text import extract_pdf
from known_pdf import pdf_pages
from normalized import validate_offer
from test_document_images import image_pdf
from test_document_text import make_rows


def native_page_with_unused_resources(data):
    reader = PdfReader(io.BytesIO(data))
    page = reader.pages[0]
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 20 20 Td (22 24 26) Tj ET\n')
    writer = PdfWriter()
    page[NameObject('/Contents')] = writer._add_object(stream)
    writer.add_page(page)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class UsedImageBoundaries(unittest.TestCase):
    def assert_native_only(self, data):
        doc = extract_pdf(data, allow_ocr=False)
        self.assertEqual(doc['pages'][0]['text'], '22 24 26')
        self.assertEqual(doc['pages'][0]['method'], 'native_pdf_text')
        self.assertEqual(doc['errors'], [])
        self.assertEqual(doc['ocr_pages'], 0)
        record = make_rows(doc)[0]
        validate_offer(record)
        self.assertNotIn('document_text_extraction_partial', record['warnings'])
        self.assertEqual(pdf_pages(data), ['22 24 26'])

    def test_unused_page_image_resource_does_not_require_ocr(self):
        data = native_page_with_unused_resources(image_pdf(form_depth=0, native_text='22 24 26'))

        self.assert_native_only(data)

    def test_unused_nested_forms_do_not_require_ocr_for_their_images(self):
        for inline in (False, True):
            with self.subTest(inline=inline):
                data = image_pdf(form_depth=3, image_count=0 if inline else 1,
                                 inline_count=1 if inline else 0, native_text='22 24 26')
                self.assert_native_only(native_page_with_unused_resources(data))

    def test_same_image_resources_still_require_review_when_actually_drawn(self):
        for depth, inline in ((0, False), (3, False), (0, True), (3, True)):
            with self.subTest(depth=depth, inline=inline):
                data = image_pdf(form_depth=depth, image_count=0 if inline else 1,
                                 inline_count=1 if inline else 0, native_text='22 24 26')
                doc = extract_pdf(data, allow_ocr=False)

                self.assertEqual(doc['pages'][0]['text'], '22 24 26')
                self.assertEqual(doc['pages'][0]['method'], 'missing_text')
                self.assertEqual(doc['errors'], [{'page': 1, 'reason': 'ocr_disabled'}])
                with self.assertRaisesRegex(ValueError, 'pdf_missing_text_layer_review_required'):
                    pdf_pages(data)


if __name__ == '__main__':
    unittest.main()
