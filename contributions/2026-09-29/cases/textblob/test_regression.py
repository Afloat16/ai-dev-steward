import importlib.util
import os
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("target", Path(__file__).with_name(os.environ.get("VARIANT", "after") + ".py"))
target = importlib.util.module_from_spec(spec)
spec.loader.exec_module(target)


@pytest.mark.parametrize("chunk", [
    [("the","DT"),("cat","NN"),("and","CC"),("dog","NN")],
    [("cat","NN"),("the","DT"),("dog","NN")],
    [("the","DT"),("the","DT"),("cat","NN")],
])
def test_suffix_generator(chunk):
    expected=[pair for pair in chunk if pair[1] not in {"DT","CC"}]
    assert target.filter_insignificant(chunk,(x for x in ["DT","CC"]))==expected

@pytest.mark.parametrize("suffixes", [["DT","CC"],("DT","CC")])
def test_reiterable_control(suffixes):
    assert target.filter_insignificant([("the","DT"),("cat","NN"),("and","CC")],suffixes)==[("cat","NN")]

def test_empty_inputs():
    assert target.filter_insignificant([],iter(["DT"]))==[]
    assert target.filter_insignificant([("the","DT")],iter([]))==[("the","DT")]

def test_suffix_not_exact_match():
    assert target.filter_insignificant([("a","TEST_DT"),("b","TEST_NN")],iter(["DT"]))==[("b","TEST_NN")]
