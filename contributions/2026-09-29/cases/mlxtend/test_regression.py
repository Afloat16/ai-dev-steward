import importlib.util
import os
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("target", Path(__file__).with_name(os.environ.get("VARIANT", "after") + ".py"))
target = importlib.util.module_from_spec(spec)
spec.loader.exec_module(target)

@pytest.mark.parametrize('text, expected', [
 ('Hi :) world', ['hi','world',':)']),
 (':) happy',['happy',':)']),
 ('test :( sad',['test','sad',':(']),
 ('<b>:) hello</b>',['hello',':)']),
 ('A :) B :( C',['a','b','c',':)',':(']),
 ('x :-) y',['x','y',':-)']),
 ('Hello world',['hello','world']),
 ('Hello :)',['hello',':)']),
 ('',[]),
 ('</a>This :) is :( a test :-)!',['this','is','a','test',':)',':(',':-)']),
])
def test_tokenization(text,expected):
 assert target.tokenizer_words_and_emoticons(text)==expected

def test_emoticons_only_unchanged():
 assert target.tokenizer_emoticons('Hi :) world :(')==[':)',':(']
