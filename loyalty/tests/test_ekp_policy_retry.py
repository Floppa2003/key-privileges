"""A single policy-route retry must not generalize into an access bypass."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).parents[1]))
import ekp_api_collect as c
from free_access_probe import ProbeError
from test_ekp_api import FakeReader,NOW

RULES='User-agent: *\nAllow: /'

class PolicyRetryTests(unittest.TestCase):
    def reader(self,values,halted=False):
        return SimpleNamespace(read=Mock(side_effect=values),sleep=Mock(),http=SimpleNamespace(halted=halted))









    def test_catalogue404_has_separate_bounded_query_retry(self):
        class ApiFailure(FakeReader):
            def __init__(self):super().__init__(total=1);self.sleep=Mock()
            def read(self,url,body=None):
                if url==c.API:
                    self.queries.append(body);self.calls+=1;self.reserved+=25
                    raise ProbeError('provider_http_404')
                return super().read(url,body)
        r=ApiFailure()
        with tempfile.TemporaryDirectory() as tmp:
            b=c.collect(r,tmp,run_id='fixture:1',observed_at=NOW,commit='test')
            self.assertFalse(b['records']);self.assertEqual(len(r.queries),2);r.sleep.assert_called_once_with(10)

if __name__=='__main__':unittest.main()
