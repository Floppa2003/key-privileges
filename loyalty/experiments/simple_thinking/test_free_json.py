"""A decoder-format probe must preserve model-visible instructions and evidence."""
import copy
import unittest
import free_json

class FreeJSONTests(unittest.TestCase):
    def test_only_decoder_constraint_is_removed(self):
        request={'model':'local', 'think':True, 'format':{'type':'object'},
                 'messages':[{'role':'user','content':'literal schema and unchanged description'}],
                 'options':{'num_predict':4096,'temperature':0}}
        before=copy.deepcopy(request)
        candidate=free_json.without_decoder_constraint(request)
        self.assertEqual(request,before)
        self.assertEqual(candidate,{k:v for k,v in before.items() if k!='format'})

    def test_non_thinking_request_is_not_a_thinking_probe(self):
        with self.assertRaises(ValueError):
            free_json.without_decoder_constraint({'think':False,'format':{'type':'object'}})

    def test_missing_constraint_is_rejected(self):
        with self.assertRaises(ValueError):
            free_json.without_decoder_constraint({'think':True})

if __name__=='__main__':unittest.main()
