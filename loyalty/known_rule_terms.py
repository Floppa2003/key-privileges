"""Literal terms shared by known-rule collection and stored-data projection."""
import re
from decimal import Decimal
from normalized import NUMERIC_TOKEN, literal_number


def retail_redemption_terms(text: str) -> dict:
    """Read the whole owned percentage expression at each reviewed label."""
    def percentage(label, reason):
        labels=list(re.finditer(r'\b'+label+r'\b',text,re.I))
        if len(labels)!=1:raise ValueError(reason)
        suffix=text[labels[0].end():]
        found=re.match(r'\s*('+NUMERIC_TOKEN+r')\s*%',suffix,re.I)
        value=literal_number(found[1]) if found else None
        if value is None or not 0<=Decimal(value)<=100:raise ValueError(reason)
        # Reject numeric continuations before accepting the complete percentage,
        # while retaining normal wording such as "% заказа" / "% необходимо".
        if re.match(r'\s*(?:%|(?:[.,/+−–—-]\s*)+\d|'
                    r'(?:[–—-]\s*)?(?:до|или|либо|и)\b\s*[+−-]?\d|\d)',suffix[found.end():],re.I):
            raise ValueError(reason)
        return value
    return {'max_order_percent':percentage(r'не\s+более','retail_redemption_percent_invalid'),
            'minimum_cash_percent':percentage(r'При\s+этом','retail_cash_percent_invalid'),
            'basis':retail_redemption_basis(text),'evidence':text}


def retail_redemption_basis(text: str) -> str | None:
    """A full order basis needs unambiguous discount and delivery treatment."""
    def treatment(noun):
        pattern = (r'\b(?P<mode>без|с)\s+уч[её]т(?:ом|а)\s+'
                   + noun + r'\b')
        modes = set()
        for found in re.finditer(pattern, text, re.I):
            if re.search(r'\bне\s*$', text[:found.start()], re.I):
                return None
            modes.add(found['mode'].casefold())
        return next(iter(modes)) if len(modes) == 1 else None

    discounts = treatment(r'(?:всех\s+)?скидок')
    delivery = treatment(r'(?:стоимости\s+)?доставки')
    if discounts is None or delivery is None:
        return None
    stage = 'after' if discounts == 'с' else 'before'
    inclusion = 'including' if delivery == 'с' else 'excluding'
    return f'order_{stage}_discounts_{inclusion}_delivery_as_published'
