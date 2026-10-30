import copy
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import merchant_channels as channels
import merchant_credit_prices as prices
from test_merchant_channels import HTTP, Response, KEY, NOW


def fixture():
    model = {'id': channels.SUPER_VL, 'context_window': 1048576,
        'pricing': {'input': '0.0000002', 'output': '0.0000005',
            'input_cache_read': '0.00000004', 'varies_by_provider': True,
            'regional': {'us': {'input': '0.0000002', 'output': '0.0000005', 'input_cache_read': '0.00000004'}}}}
    endpoint = {'provider_name': 'baseten', 'context_length': 1048576,
        'pricing': {'prompt': '0.0000002', 'completion': '0.0000005', 'input_cache_read': '0.00000004',
            'request': '0', 'image': '0', 'image_output': '0', 'web_search': '0', 'internal_reasoning': '0', 'discount': 0},
        'inference_regions': [{'scope': 'zone', 'geo_region': 'us',
            'pricing': {'prompt': '0.0000002', 'completion': '0.0000005', 'input_cache_read': '0.00000004'}}]}
    return model, {'id': channels.SUPER_VL, 'endpoints': [endpoint]}


class PricesTests(unittest.TestCase):
    def test_openrouter_is_not_in_automatic_queue(self):
        self.assertNotIn('openrouter', channels.DEFAULT_PROVIDERS)
        self.assertIn('openrouter', channels.NEW_PROVIDERS)
        self.assertEqual(channels.DEFAULT_PROVIDERS,
            ('orcarouter', 'experiential', 'kilo', 'vercel', 'gemini', 'tokenharbor'))

    def test_actual_observed_regional_catalog_price(self):
        model, data = fixture()
        self.assertEqual(prices.reservation(model, 16384, data), Decimal('0.24069792'))

    def test_varies_by_provider_requires_exact_nonempty_endpoint_view(self):
        model, _ = fixture()
        for data in (None, {}, {'id': 'other', 'endpoints': [{}]}, {'id': channels.SUPER_VL, 'endpoints': []}):
            with self.assertRaises(ValueError):
                prices.reservation(model, 16384, data)

    def test_expensive_fallback_and_regional_rate_not_default_are_bounded(self):
        model, data = fixture()
        expensive = copy.deepcopy(data['endpoints'][0])
        expensive['provider_name'] = 'other'
        expensive['pricing']['prompt'] = '0.0000003'
        expensive['inference_regions'][0]['pricing']['completion'] = '0.000002'
        data['endpoints'].append(expensive)
        self.assertEqual(prices.reservation(model, 16384, data),
            (Decimal(1048576) * Decimal('0.0000003') + Decimal(16384) * Decimal('0.000002')) * Decimal('1.10') + Decimal('0.001'))

    def test_unknown_endpoint_fee_and_nonzero_auxiliary_charge_are_blocked(self):
        for field, value in (('request', '1'), ('image', '0.01'), ('internal_reasoning', '0.01'), ('unknown_fee', '0')):
            model, data = fixture()
            data['endpoints'][0]['pricing'][field] = value
            with self.assertRaises(ValueError):
                prices.reservation(model, 16384, data)

    def test_all_price_tiers_and_cache_write_surcharge_are_reserved(self):
        model, data = fixture()
        pricing = data['endpoints'][0]['pricing']
        pricing['prompt_tiers'] = [{'cost': '0.000001'}]
        pricing['input_cache_write'] = '0.0000001'
        reserve = prices.reservation(model, 16384, data)
        self.assertGreater(reserve, Decimal(1048576) * Decimal('0.0000011'))

    def test_invalid_provider_context_and_nonfinite_price_fail(self):
        for variant in ('context', 'price'):
            model, data = fixture()
            if variant == 'context':
                data['endpoints'][0]['context_length'] = None
            else:
                data['endpoints'][0]['pricing']['prompt'] = 'NaN'
            with self.assertRaises(ValueError):
                prices.reservation(model, 16384, data)

    def test_admission_fetches_endpoint_view_and_counts_it(self):
        model, data = fixture()
        class EndpointHTTP(HTTP):
            def get(self, url, **kwargs):
                if url.endswith('/endpoints'):
                    self.gets.append((url, kwargs))
                    return Response({'data': data})
                return super().get(url, **kwargs)
        client = EndpointHTTP(model=model)
        check = channels.admission('vercel', {'max_tokens': 16384}, KEY, {}, NOW, client)
        self.assertTrue(check['allowed'], check)
        self.assertEqual(check['pricing_endpoints_checked'], 1)
        self.assertEqual(Decimal(check['reservation_usd']), Decimal('0.24069792'))
        self.assertEqual(client.calls, [])

    def test_endpoint_failure_is_fail_closed_without_generation(self):
        model, _ = fixture()
        class FailingHTTP(HTTP):
            def get(self, url, **kwargs):
                if url.endswith('/endpoints'):
                    return Response({'error': 'unavailable'}, 503)
                return super().get(url, **kwargs)
        client = FailingHTTP(model=model)
        check = channels.admission('vercel', {'max_tokens': 16384}, KEY, {}, NOW, client)
        self.assertFalse(check['allowed'])
        self.assertEqual(check['reason'], 'allowance_read_failed')
        self.assertEqual(client.calls, [])

if __name__ == '__main__':
    unittest.main()
