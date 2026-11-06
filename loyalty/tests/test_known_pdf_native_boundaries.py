"""Reviewed native-only PDFs must retain Form text or reject incomplete pages."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
from known_pdf import pdf_pages
from test_document_images import form_resource_pdf, image_pdf
from test_document_text import pdf


class ReviewedNativePdfBoundaries(unittest.TestCase):
    def test_shared_form_uses_each_pages_native_resources(self):
        pages = pdf_pages(form_resource_pdf(page_glyphs=('three', 'seven')))

        self.assertEqual(pages, [
            'Discount 3 percent for members.\nPage 1 supplementary terms.\nPage 1',
            'Discount 7 percent for members.\nPage 2 supplementary terms.\nPage 2',
        ])

    def test_nested_form_without_resources_retains_its_native_rules(self):
        pages = pdf_pages(form_resource_pdf(nested=True))

        self.assertEqual(pages, [
            'Discount 3 percent for members.\nPage 1 supplementary terms.\nPage 1',
        ])

    def test_image_pages_with_native_footer_require_review_without_ocr(self):
        cases = [
            {'form_depth': 0, 'image_count': 1},
            {'form_depth': 2, 'image_count': 1},
            {'form_depth': 0, 'image_count': 0, 'inline_count': 1},
            {'form_depth': 2, 'image_count': 0, 'inline_count': 1},
        ]
        with patch('document_text.ocr_pages', side_effect=AssertionError('Native-only route cannot invoke OCR')):
            for case in cases:
                with self.subTest(case=case):
                    with self.assertRaisesRegex(ValueError, 'pdf_missing_text_layer_review_required'):
                        pdf_pages(image_pdf(**case))

    def test_many_distinct_images_do_not_make_a_long_footer_complete_rules(self):
        footer = 'Public contact information with a detailed reference for this document.'
        for inline in (False, True):
            with self.subTest(inline=inline):
                data = image_pdf(image_count=0 if inline else 10,
                                 inline_count=10 if inline else 0, native_text=footer)
                with self.assertRaisesRegex(ValueError, 'pdf_missing_text_layer_review_required'):
                    pdf_pages(data)

    def test_sparse_native_pages_retain_original_text_without_ocr(self):
        values = ['22 24 26', '  Native terms remain source text.  ']
        with patch('document_text.ocr_pages', side_effect=AssertionError('Native text cannot invoke OCR')):
            self.assertEqual(pdf_pages(pdf(values)), values)

    def test_image_aliases_do_not_turn_native_rules_into_an_image_heavy_page(self):
        value = 'Public contact information with a detailed reference for this document.'
        self.assertEqual(pdf_pages(image_pdf(image_count=10, shared_image=True, native_text=value)), [value])


if __name__ == '__main__':
    unittest.main()
