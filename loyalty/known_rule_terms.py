"""Literal terms shared by known-rule collection and stored-data projection."""
import re


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
