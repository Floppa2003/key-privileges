"""Every writer sharing the same lock must retain pending refreshes."""
import re,unittest
from pathlib import Path
GROUP='group: loyalty-catalog-'+'$'+'{{ github.ref }}'
class SharedQueueTests(unittest.TestCase):
    def test_all_shared_catalogue_workflows_queue_without_parallel_writes(self):
        root=Path(__file__).resolve().parents[2]/'.github/workflows'
        found=[]
        for path in root.glob('*.yml'):
            raw=path.read_text()
            if GROUP not in raw:continue
            found.append(path.name)
            block=re.search(r'^concurrency:\n((?:  .*\n)+)',raw,re.M)
            self.assertIsNotNone(block,path.name)
            with self.subTest(workflow=path.name):
                self.assertIn('  queue: max\n',block[1])
                self.assertIn('  cancel-in-progress: false\n',block[1])
                self.assertEqual(block[1].count('  group:'),1)
        self.assertTrue(found,'No shared workflows checked')
