"""The collector must parse the hydrated catalogue, not its server-rendered shell."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from backit_catalog import collect
from backit_source import ROOT

FIX = Path(__file__).parent / 'fixtures_live' / 'affordable'
NOW = '2026-09-22T10:42:11+00:00'
# A minimal DOM using the selectors from the captured catalogue. Pagination is
# client-rendered; the initial HTTP document intentionally lacks that element.
CARDS = '<div class="offers"><div class="offer-cards"><a class="mu-store__wrapper" href="/ru/cashback/shops/kuper"><span class="mu-store__title">Купер (бывший СберМаркет)</span></a></div></div>'
READY = CARDS + '<div class="mu-pagination" total="1" pagesize="40" currentpage="1"></div>'

class Page:
    def __init__(self, fail=False):
        self.raw = CARDS
        self.url = ROOT
        self.fail = fail
        self.waits = []
    async def wait_for_function(self, expression, *, arg, timeout):
        self.waits.append((arg, timeout))
        if self.fail:
            raise TimeoutError('catalogue remained unhydrated')
        self.raw = READY
    async def content(self):
        return self.raw

class Client:
    request_interval = .25
    def __init__(self, fail=False):
        self.page = Page(fail)
        self.reads = []
    async def read(self, url, *, render=False):
        self.reads.append((url, render))
        if url == ROOT:
            return CARDS
        return (FIX / 'backit-kuper.html').read_text()
    def check_url(self, url):
        if url != ROOT:
            raise RuntimeError('unexpected_redirect')

class BackitReadinessTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_collector_waits_for_hydrated_inventory(self):
        client = Client(); report = {'errors': []}
        rows = await collect(client, {'id': 'backit_public', 'url': ROOT}, report, NOW, 500)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['partner_name'], 'Купер (бывший СберМаркет)')
        self.assertEqual(client.page.waits, [(1, 15000)])
        self.assertEqual(report['errors'], [])
    async def test_unready_inventory_never_creates_or_fetches_card(self):
        client = Client(fail=True)
        with self.assertRaisesRegex(RuntimeError, 'backit_catalogue_not_ready'):
            await collect(client, {'id': 'backit_public', 'url': ROOT}, {'errors': []}, NOW, 500)
        self.assertEqual(client.reads, [(ROOT, True)])

if __name__ == '__main__': unittest.main()
