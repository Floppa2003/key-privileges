"""Correct Protego 0.6.2's empty-query rule only for queryless Magnit card paths.

Its _quote_pattern('/*?$') becomes '/*$'. A literal question mark cannot
match these strictly enumerated queryless paths. Other URLs, directives,
agent groups, delays and refusals keep the original parser's policy.
"""
import re
from urllib.parse import urlsplit
from protego import Protego

class QuerylessMagnitPolicy:
    def __init__(self,rules):
        self.original=Protego.parse(rules)
        # Keep the directive and its position, including groups containing only
        # query rules. Removing lines could accidentally join user-agent groups.
        escaped=re.sub(r'^([ \t]*(?:allow|disallow)[ \t]*:[ \t]*)([^#\n]*)',
            lambda m:m[1]+m[2].replace('?', '%3F'),rules,flags=re.I|re.M)
        self.queryless=Protego.parse(escaped)

    def can_fetch(self,url,agent):
        u=urlsplit(url)
        if (u.scheme=='https' and u.netloc=='magnit.ru'
            and re.fullmatch(r'/partners(?:/\d+)?/?',u.path)
            and '?' not in url.partition('#')[0]):
            return self.queryless.can_fetch(url,agent)
        return self.original.can_fetch(url,agent)

    def crawl_delay(self,agent):return self.original.crawl_delay(agent)
    def request_rate(self,agent):return self.original.request_rate(agent)
