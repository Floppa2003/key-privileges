"""Run the real browser readiness predicate against published Unicode variants."""
import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))

class ArticlePredicateTests(unittest.TestCase):
 def evaluate(self,blocks):
  import subprocess
  from known_rules import ARTICLE_READY_JS
  # Execute the production predicate, with only its DOM boundary replaced.
  script="const f=eval('('+process.argv[1]+')');const nodes=JSON.parse(process.argv[2]);global.document={querySelectorAll:(s)=>{if(s!=='.article-content')throw Error('wrong scope');return nodes}};console.log(JSON.stringify(f({selector:'.article-content',text:'Дополнительно оплачивается замена SIM-карты'})));"
  r=subprocess.run(['node','-e',script,ARTICLE_READY_JS,json.dumps(blocks)],capture_output=True,text=True,check=True)
  return json.loads(r.stdout)
 def test_published_nonbreaking_hyphen_and_spaces_do_not_make_ready_article_timeout(self):
  self.assertTrue(self.evaluate([{'innerText':'Дополнительно\u00a0оплачивается замена SIM\u2011карты – 100\u00a0руб.'}]))
 def test_missing_or_ambiguous_article_still_does_not_pass(self):
  self.assertFalse(self.evaluate([]))
  self.assertFalse(self.evaluate([{'innerText':'Загрузка'}]))
  body={'innerText':'Дополнительно оплачивается замена SIM-карты'}
  self.assertFalse(self.evaluate([body,body]))
