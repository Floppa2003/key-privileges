"""Real PDF resource graphs exercise the native-text/OCR boundary."""
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject,
)

sys.path.insert(0, str(Path(__file__).parents[1]))
from document_text import extract_pdf
from test_document_text import make_rows
from normalized import validate_offer


def image_pdf(*, form_depth=1, image_count=1, shared_image=False,
              native_text='Page 1', cycle=False, execute_cycle=False,
              form_calls=1, form_padding=0):
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    font = DictionaryObject({
        NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Helvetica'),
    })
    xobjects = DictionaryObject()
    first_image = None
    for index in range(image_count):
        if shared_image and first_image is not None:
            reference = first_image
        else:
            image = DecodedStreamObject()
            image.set_data(bytes([0, 255, 255, 0]))
            image.update({
                NameObject('/Type'): NameObject('/XObject'),
                NameObject('/Subtype'): NameObject('/Image'),
                NameObject('/Width'): NumberObject(2),
                NameObject('/Height'): NumberObject(2),
                NameObject('/ColorSpace'): NameObject('/DeviceGray'),
                NameObject('/BitsPerComponent'): NumberObject(8),
            })
            reference = writer._add_object(image)
            first_image = reference
        xobjects[NameObject('/Im' + str(index))] = reference
    drawing = b''.join(
        ('q 400 0 0 400 0 0 cm /Im' + str(index) + ' Do Q\n').encode('ascii')
        for index in range(image_count)
    )
    for depth in range(form_depth):
        form = DecodedStreamObject()
        form.set_data(drawing + (b'%' + b'x' * form_padding + b'\n' if depth == 0 and form_padding else b''))
        form.update({
            NameObject('/Type'): NameObject('/XObject'),
            NameObject('/Subtype'): NameObject('/Form'),
            NameObject('/BBox'): ArrayObject([NumberObject(n) for n in (0, 0, 500, 500)]),
            NameObject('/Resources'): DictionaryObject({NameObject('/XObject'): xobjects}),
        })
        reference = writer._add_object(form)
        if (cycle or execute_cycle) and depth == 0:
            # Shared resource dictionaries may legally contain the Form itself.
            xobjects[NameObject('/Self')] = reference
            if execute_cycle:
                form.set_data(form.get_data() + b'/Self Do\n')
        xobjects = DictionaryObject({NameObject('/Fm'): reference})
        drawing = b'q /Fm Do Q\n'
    if form_depth:
        drawing *= form_calls
    page[NameObject('/Resources')] = DictionaryObject({
        NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)}),
        NameObject('/XObject'): xobjects,
    })
    content = DecodedStreamObject()
    content.set_data(drawing + ('BT /F1 12 Tf 20 20 Td (' + native_text + ') Tj ET\n').encode('ascii'))
    page[NameObject('/Contents')] = writer._add_object(content)
    result = io.BytesIO()
    writer.write(result)
    return result.getvalue()


class ImageResourceTests(unittest.TestCase):
    def test_nested_image_with_native_footer_is_not_accepted_as_complete_text(self):
        for depth in (0, 1, 3):
            with self.subTest(depth=depth):
                doc = extract_pdf(image_pdf(form_depth=depth), allow_ocr=False)
                self.assertEqual(doc['pages'][0]['method'], 'missing_text')
                self.assertEqual(doc['pages'][0]['native_text'], 'Page 1')
                self.assertEqual(doc['errors'], [{'page': 1, 'reason': 'ocr_disabled'}])

    def test_nested_image_uses_ocr_and_preserves_uncertainty_in_record(self):
        with patch('document_text.ocr_pages', return_value={
            1: ('Scanned source terms 735', {'minimum_numeric_confidence': 77}),
        }):
            doc = extract_pdf(image_pdf(form_depth=2))
        self.assertEqual(doc['pages'][0]['text'], 'Scanned source terms 735')
        self.assertEqual(doc['pages'][0]['native_text'], 'Page 1')
        self.assertEqual(doc['pages'][0]['method'], 'ocr_unverified')
        self.assertEqual(doc['ocr_pages'], 1)
        self.assertEqual(doc['errors'], [])
        record = make_rows(doc)[0]
        validate_offer(record)
        self.assertEqual(record['source_status'], 'public_rules_ocr_unverified')
        self.assertIn('ocr_text_unverified_no_manual_corrections', record['warnings'])

    def test_forms_without_images_do_not_force_ocr_for_sparse_native_text(self):
        doc = extract_pdf(image_pdf(form_depth=3, image_count=0, native_text='22 24 26'), allow_ocr=False)
        self.assertEqual(doc['pages'][0]['text'], '22 24 26')
        self.assertEqual(doc['pages'][0]['method'], 'native_pdf_text')
        self.assertEqual(doc['errors'], [])

    def test_shared_image_aliases_do_not_inflate_the_image_heavy_heuristic(self):
        text = 'Public contact information with a detailed reference for this document.'
        doc = extract_pdf(image_pdf(image_count=10, shared_image=True, native_text=text), allow_ocr=False)
        self.assertEqual(doc['pages'][0]['text'], text)
        self.assertEqual(doc['pages'][0]['method'], 'native_pdf_text')
        self.assertEqual(doc['errors'], [])

    def test_distinct_nested_images_can_require_ocr_despite_a_longer_footer(self):
        text = 'Public contact information with a detailed reference for this document.'
        doc = extract_pdf(image_pdf(image_count=10, native_text=text), allow_ocr=False)
        self.assertEqual(doc['pages'][0]['method'], 'missing_text')
        self.assertEqual(doc['errors'], [{'page': 1, 'reason': 'ocr_disabled'}])

    def test_unused_form_self_reference_is_valid_and_does_not_hide_images(self):
        cases = [('Page 1', 'missing_text', [{'page': 1, 'reason': 'ocr_disabled'}]),
                 ('This page has readable native source text and an unused resource alias.',
                  'native_pdf_text', [])]
        for text, method, errors in cases:
            with self.subTest(text=text):
                try:
                    doc = extract_pdf(image_pdf(cycle=True, native_text=text), allow_ocr=False)
                except ValueError as exc:
                    self.fail('Valid shared Form resources were rejected: ' + str(exc))
                self.assertEqual(doc['pages'][0]['text'], text)
                self.assertEqual(doc['pages'][0]['method'], method)
                self.assertEqual(doc['errors'], errors)

    def test_actual_recursive_form_drawing_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, 'pdf_xobject_cycle'):
            extract_pdf(image_pdf(execute_cycle=True), allow_ocr=False)

    def test_reusing_a_form_in_separate_draws_is_not_a_cycle(self):
        text = 'This page has readable native source text and two separate Form draws.'
        doc = extract_pdf(image_pdf(cycle=True, form_calls=2, native_text=text), allow_ocr=False)
        self.assertEqual(doc['pages'][0]['text'], text)
        self.assertEqual(doc['pages'][0]['method'], 'native_pdf_text')
        self.assertEqual(doc['errors'], [])

    def test_excessive_form_draws_fail_instead_of_accepting_truncated_native_text(self):
        with self.assertRaisesRegex(ValueError, 'pdf_xobject_invocation_limit'):
            extract_pdf(image_pdf(form_calls=5_001), allow_ocr=False)

    def test_deep_form_resources_fail_without_silently_losing_images(self):
        with self.assertRaisesRegex(ValueError, 'pdf_xobject_depth_limit'):
            extract_pdf(image_pdf(form_depth=33), allow_ocr=False)

    def test_resource_reference_limit_cannot_be_evaded_by_image_aliases(self):
        with self.assertRaisesRegex(ValueError, 'pdf_xobject_reference_limit'):
            extract_pdf(image_pdf(image_count=10_001, shared_image=True), allow_ocr=False)

    def test_oversized_form_content_has_the_same_limit_as_page_content(self):
        with self.assertRaisesRegex(ValueError, 'pdf_content_stream_limit'):
            extract_pdf(image_pdf(form_padding=4_000_001), allow_ocr=False)


if __name__ == '__main__':
    unittest.main()
