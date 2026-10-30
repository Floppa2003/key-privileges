"""Conservative cost bounds for one text/image completion; unknown fees fail closed."""
from decimal import Decimal, InvalidOperation


def number(value):
    if isinstance(value, bool):
        raise ValueError('invalid_numeric_price')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValueError('invalid_numeric_price') from None
    if not result.is_finite() or result < 0:
        raise ValueError('invalid_numeric_price')
    return result


def price_rates(pricing, *, endpoint=False):
    if not isinstance(pricing, dict):
        raise ValueError('pricing_shape')
    inp, out = ('prompt', 'completion') if endpoint else ('input', 'output')
    rates = {inp, out, 'input_cache_read', 'input_cache_write'}
    tiers = {field + '_tiers' for field in rates}
    extras = {'request', 'image', 'image_output', 'web_search', 'internal_reasoning'} if endpoint else set()
    metadata = {'discount'} if endpoint else {'varies_by_provider', 'regional'}
    if set(pricing) - rates - tiers - extras - metadata:
        raise ValueError('unaccounted_pricing_dimension')
    # We invoke no search/tools, and image tokens are covered by the input context.
    # A newly nonzero per-image/per-request fee must not silently pass this bound.
    if any(number(pricing[field]) != 0 for field in extras if field in pricing):
        raise ValueError('nonzero_unbounded_auxiliary_fee')
    if 'discount' in pricing:
        number(pricing['discount'])  # Ignore reductions; never reduce the reserve.
    if 'varies_by_provider' in pricing and type(pricing['varies_by_provider']) is not bool:
        raise ValueError('invalid_provider_pricing_flag')

    def maximum(field, required=False):
        values = [number(pricing[field])] if required or field in pricing else [Decimal(0)]
        rows = pricing.get(field + '_tiers', [])
        if not isinstance(rows, list):
            raise ValueError('pricing_tiers_shape')
        for row in rows:
            if not isinstance(row, dict) or 'cost' not in row:
                raise ValueError('pricing_tier_missing_cost')
            values.append(number(row['cost']))
        return max(values)

    # Charging both ordinary input and a cache-write surcharge can only increase
    # this bound. A cheaper cached read must never lower the ordinary input price.
    input_rate = max(maximum(inp, True), maximum('input_cache_read')) + maximum('input_cache_write')
    return input_rate, maximum(out, True)


def reservation(model, max_output, endpoint_data=None):
    context = model.get('context_window')
    if type(context) is not int or not 1 <= context <= 2_000_000:
        raise ValueError('model_cost_bound_unavailable')
    if type(max_output) is not int or not 1 <= max_output <= 16384:
        raise ValueError('model_cost_bound_unavailable')
    pricing = model.get('pricing', {})
    books = [(pricing, False)]
    regional = pricing.get('regional', {})
    if not isinstance(regional, dict):
        raise ValueError('regional_pricing_shape')
    books.extend((book, False) for book in regional.values())
    if pricing.get('varies_by_provider'):
        if not isinstance(endpoint_data, dict) or endpoint_data.get('id') != model.get('id'):
            raise ValueError('provider_specific_prices_unverified')
        endpoints = endpoint_data.get('endpoints')
        if not isinstance(endpoints, list) or not endpoints:
            raise ValueError('provider_specific_prices_unverified')
        # Include inactive and fallback endpoints too; their future selection must
        # not use a cheaper default rate or an unexamined price book.
        for route in endpoints:
            if not isinstance(route, dict) or not route.get('provider_name'):
                raise ValueError('provider_specific_prices_unverified')
            length = route.get('context_length')
            if type(length) is not int or not 1 <= length <= 2_000_000:
                raise ValueError('provider_context_bound_unavailable')
            context = max(context, length)
            books.append((route['pricing'], True))
            regions = route.get('inference_regions', [])
            if not isinstance(regions, list):
                raise ValueError('endpoint_regions_shape')
            for region in regions:
                books.append((region['pricing'], True))
    rates = [price_rates(book, endpoint=is_endpoint) for book, is_endpoint in books]
    input_rate = max(pair[0] for pair in rates)
    output_rate = max(pair[1] for pair in rates)
    return (Decimal(context) * input_rate + Decimal(max_output) * output_rate) * Decimal('1.10') + Decimal('0.001')
