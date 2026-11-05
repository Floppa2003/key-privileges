"""Real PDF resource graphs exercise the native-text/OCR boundary."""
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from pypdf.generic import (
    ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject,
)

sys.path.insert(0, str(Path(__file__).parents[1]))
from document_text import extract_pdf
from test_document_text import make_rows
from normalized import validate_offer


def image_pdf(*, form_depth=1, image_count=1, shared_image=False,
              native_text='Page 1', cycle=False, execute_cycle=False,
              form_calls=1, form_padding=0, inline_count=0):
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
    drawing += (b'q 400 0 0 400 0 0 cm '
                b'BI /W 2 /H 2 /CS /G /BPC 8 /F /AHx ID 00ffff00> EI Q\n') * inline_count
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


def form_resource_pdf(*, inherited=True, image=False, page_glyphs=('three',), nested=False, draw_asset=True):
    """One shared Form uses names resolved separately on each page."""
    writer = PdfWriter()
    plain_font = writer._add_object(DictionaryObject({
        NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Helvetica'),
    }))

    def form(data, resources=None):
        value = DecodedStreamObject()
        value.set_data(data)
        value.update({
            NameObject('/Type'): NameObject('/XObject'),
            NameObject('/Subtype'): NameObject('/Form'),
            NameObject('/BBox'): ArrayObject([NumberObject(n) for n in (0, 0, 600, 800)]),
        })
        if resources is not None:
            value[NameObject('/Resources')] = resources
        return value

    drawing = (b'q 200 0 0 200 40 200 cm /Asset Do Q\n' if image else
               b'BT /F1 24 Tf 40 500 Td (Discount A percent for members.) Tj ET\n')
    if not image and draw_asset:
        drawing += b'/Asset Do\n'
    shared = form(drawing)
    shared_reference = writer._add_object(shared)
    for number, glyph in enumerate(page_glyphs, 1):
        page = writer.add_blank_page(width=600, height=800)
        font = DictionaryObject({
            NameObject('/Type'): NameObject('/Font'),
            NameObject('/Subtype'): NameObject('/Type1'),
            NameObject('/BaseFont'): NameObject('/Helvetica'),
            NameObject('/Encoding'): DictionaryObject({
                NameObject('/Type'): NameObject('/Encoding'),
                NameObject('/BaseEncoding'): NameObject('/WinAnsiEncoding'),
                NameObject('/Differences'): ArrayObject([NumberObject(65), NameObject('/' + glyph)]),
            }),
        })
        fonts = DictionaryObject({NameObject('/F0'): plain_font, NameObject('/F1'): writer._add_object(font)})
        if image:
            asset = DecodedStreamObject()
            asset.set_data(bytes([0, 255, 255, 0]))
            asset.update({
                NameObject('/Type'): NameObject('/XObject'),
                NameObject('/Subtype'): NameObject('/Image'),
                NameObject('/Width'): NumberObject(2),
                NameObject('/Height'): NumberObject(2),
                NameObject('/ColorSpace'): NameObject('/DeviceGray'),
                NameObject('/BitsPerComponent'): NumberObject(8),
            })
        else:
            asset = form(('BT /F0 12 Tf 40 420 Td (Page ' + str(number) + ' supplementary terms.) Tj ET').encode('ascii'),
                         DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F0'): plain_font})}))
        asset_reference = writer._add_object(asset)
        if not inherited:
            shared[NameObject('/Resources')] = DictionaryObject({
                NameObject('/Font'): fonts,
                NameObject('/XObject'): DictionaryObject({NameObject('/Asset'): asset_reference}),
            })
        root_reference = shared_reference
        if nested:
            outer = form(b'/Inner Do', DictionaryObject({
                NameObject('/Font'): DictionaryObject({NameObject('/FOuter'): plain_font}),
                NameObject('/XObject'): DictionaryObject({NameObject('/Inner'): shared_reference}),
            }))
            root_reference = writer._add_object(outer)
        page[NameObject('/Resources')] = DictionaryObject({
            NameObject('/Font'): fonts,
            NameObject('/XObject'): DictionaryObject({NameObject('/Shared'): root_reference, NameObject('/Asset'): asset_reference}),
        })
        content = DecodedStreamObject()
        content.set_data(('/Shared Do\nBT /F0 12 Tf 20 20 Td (Page ' + str(number) + ') Tj ET').encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(content)
    result = io.BytesIO()
    writer.write(result)
    return result.getvalue()


class ImageResourceTests(unittest.TestCase):
    def test_inline_images_with_native_footer_require_ocr_on_pages_and_in_forms(self):
        for depth in (0, 1, 3):
            with self.subTest(depth=depth):
                doc = extract_pdf(image_pdf(form_depth=depth, image_count=0, inline_count=1), allow_ocr=False)
                self.assertEqual(doc['pages'][0]['method'], 'missing_text')
                self.assertEqual(doc['pages'][0]['native_text'], 'Page 1')
                self.assertEqual(doc['errors'], [{'page': 1, 'reason': 'ocr_disabled'}])
                record = make_rows(doc)[0]
                validate_offer(record)
                self.assertIn('document_text_extraction_partial', record['warnings'])

    def test_inline_images_use_ocr_and_preserve_uncertainty_in_records(self):
        for depth in (0, 2):
            with self.subTest(depth=depth):
                with patch('document_text.ocr_pages', return_value={
                    1: ('Scanned source terms 735', {'minimum_numeric_confidence': 77}),
                }) as ocr:
                    doc = extract_pdf(image_pdf(form_depth=depth, image_count=0, inline_count=1))
                self.assertEqual(ocr.call_count, 1)
                self.assertEqual(ocr.call_args.args[1], [1])
                self.assertEqual(doc['pages'][0]['text'], 'Scanned source terms 735')
                self.assertEqual(doc['pages'][0]['native_text'], 'Page 1')
                self.assertEqual(doc['pages'][0]['method'], 'ocr_unverified')
                self.assertEqual(doc['ocr_pages'], 1)
                self.assertEqual(doc['errors'], [])
                record = make_rows(doc)[0]
                validate_offer(record)
                self.assertEqual(record['source_status'], 'public_rules_ocr_unverified')
                self.assertIn('Scanned source terms 735', record['conditions_text'])
                self.assertIn('ocr_text_unverified_no_manual_corrections', record['warnings'])

    def test_repeated_inline_form_does_not_inflate_the_image_heavy_heuristic(self):
        text = 'Public contact information with a detailed reference for this document.'
        doc = extract_pdf(image_pdf(image_count=0, inline_count=1, form_calls=10, native_text=text), allow_ocr=False)
        self.assertEqual(doc['pages'][0]['text'], text)
        self.assertEqual(doc['pages'][0]['method'], 'native_pdf_text')
        self.assertEqual(doc['errors'], [])

    def test_distinct_inline_images_can_require_ocr_despite_a_longer_footer(self):
        text = 'Public contact information with a detailed reference for this document.'
        for depth in (0, 2):
            with self.subTest(depth=depth):
                doc = extract_pdf(image_pdf(form_depth=depth, image_count=0, inline_count=10, native_text=text), allow_ocr=False)
                self.assertEqual(doc['pages'][0]['method'], 'missing_text')
                self.assertEqual(doc['errors'], [{'page': 1, 'reason': 'ocr_disabled'}])

    def test_unterminated_inline_image_fails_instead_of_accepting_the_footer(self):
        reader = PdfReader(io.BytesIO(image_pdf(form_depth=0, image_count=0, inline_count=1)))
        page = reader.pages[0]
        content = DecodedStreamObject()
        content.set_data(page.get_contents().get_data().replace(b'> EI Q\n', b'> Q\n'))
        writer = PdfWriter()
        page[NameObject('/Contents')] = writer._add_object(content)
        writer.add_page(page)
        result = io.BytesIO()
        writer.write(result)
        with self.assertRaisesRegex(PdfReadError, 'EI stream not found'):
            extract_pdf(result.getvalue(), allow_ocr=False)

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


class FormResourceInheritanceTests(unittest.TestCase):
    def test_form_without_own_resources_preserves_native_text(self):
        expected = 'Discount 3 percent for members.\nPage 1'
        for inherited in (False, True):
            with self.subTest(inherited=inherited):
                doc = extract_pdf(form_resource_pdf(inherited=inherited, draw_asset=False), allow_ocr=False)
                self.assertEqual(doc['pages'][0]['text'], expected)
                self.assertEqual(doc['pages'][0]['method'], 'native_pdf_text')
                self.assertEqual(doc['errors'], [])
                record = make_rows(doc)[0]
                validate_offer(record)
                self.assertIn(expected, record['conditions_text'])

    def test_form_without_own_resources_resolves_page_image(self):
        for inherited in (False, True):
            with self.subTest(inherited=inherited):
                doc = extract_pdf(form_resource_pdf(inherited=inherited, image=True), allow_ocr=False)
                self.assertEqual(doc['pages'][0]['method'], 'missing_text')
                self.assertEqual(doc['pages'][0]['native_text'], 'Page 1')
                self.assertEqual(doc['errors'], [{'page': 1, 'reason': 'ocr_disabled'}])

    def test_shared_form_uses_each_pages_own_fonts_and_xobjects(self):
        doc = extract_pdf(form_resource_pdf(page_glyphs=('three', 'seven')), allow_ocr=False)
        self.assertEqual([page['text'] for page in doc['pages']], [
            'Discount 3 percent for members.\nPage 1 supplementary terms.\nPage 1',
            'Discount 7 percent for members.\nPage 2 supplementary terms.\nPage 2',
        ])
        self.assertEqual([page['method'] for page in doc['pages']], ['native_pdf_text', 'native_pdf_text'])
        self.assertEqual(doc['errors'], [])
        record = make_rows(doc)[0]
        validate_offer(record)
        self.assertIn('Discount 3 percent', record['conditions_text'])
        self.assertIn('Discount 7 percent', record['conditions_text'])

    def test_nested_resource_less_form_resolves_page_resources(self):
        doc = extract_pdf(form_resource_pdf(nested=True), allow_ocr=False)
        self.assertEqual(doc['pages'][0]['text'], 'Discount 3 percent for members.\nPage 1 supplementary terms.\nPage 1')
        self.assertEqual(doc['pages'][0]['method'], 'native_pdf_text')
        self.assertEqual(doc['errors'], [])


class NativePdfLiteralTests(unittest.TestCase):
    def test_markup_like_native_text_remains_literal_in_validated_record(self):
        value = 'Literal terms <b>remain text</b>; &lt; 50 percent &amp; conditions.'
        doc = extract_pdf(image_pdf(form_depth=0, image_count=0, native_text=value), allow_ocr=False)
        self.assertEqual(doc['pages'][0]['text'], value)
        record = make_rows(doc)[0]
        self.assertEqual(record['conditions_text'], '[Страница 1; позиция 0]\n' + value)
        validate_offer(record)


if __name__ == '__main__':
    unittest.main()
