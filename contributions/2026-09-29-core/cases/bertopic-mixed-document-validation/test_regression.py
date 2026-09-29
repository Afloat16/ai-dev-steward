"""The complete document validator must reject mixed-type iterables."""
import importlib.util
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

source=Path(__file__).parent/os.environ.get('VARIANT','after')/'bertopic/_utils.py'
spec=importlib.util.spec_from_file_location('tested_bertopic_utils',source)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

@pytest.mark.parametrize('bad',[None,42,3.5,True,b'bytes',{'text':'value'},['nested']])
def test_mixed_document_list_is_rejected(bad):
    with pytest.raises(TypeError,match='only contains strings'):
        module.check_documents_type(['valid document',bad])

@pytest.mark.parametrize('factory',[tuple,lambda v:np.array(v,dtype=object),lambda v:(x for x in v)])
def test_other_mixed_iterables_are_rejected(factory):
    with pytest.raises(TypeError,match='only contains strings'):
        module.check_documents_type(factory(['valid document',None]))

@pytest.mark.parametrize('documents',[[],[None],['text'],('first','second'),np.array(['a','b']),pd.DataFrame({'text':['a']}),'text'])
def test_existing_contract_is_preserved(documents):
    invalid=isinstance(documents,(str,pd.DataFrame)) or isinstance(documents,list) and (not documents or documents==[None])
    if invalid:
        with pytest.raises(TypeError): module.check_documents_type(documents)
    else:
        assert module.check_documents_type(documents) is None
