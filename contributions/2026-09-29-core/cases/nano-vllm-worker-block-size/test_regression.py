"""Spawn real fresh Python workers and exercise Sequence + prepare_decode.
No CUDA or model weights: runner initialization stops at the first NCCL call;
only tensor placement is redirected to CPU for the unchanged address-building code.
"""
import importlib.util
import multiprocessing
import os
from pathlib import Path
import pickle
import sys
import types
from unittest.mock import patch
import pytest
import torch

def _load(variant):
    root=Path(__file__).parent/variant
    for name in ['nanovllm','nanovllm.engine','nanovllm.layers','nanovllm.models','nanovllm.utils']:
        m=types.ModuleType(name);m.__path__=[];sys.modules[name]=m
    def source(name, path):
        spec=importlib.util.spec_from_file_location(name,root/path)
        m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
    source('nanovllm.sampling_params','nanovllm/sampling_params.py')
    seq=source('nanovllm.engine.sequence','nanovllm/engine/sequence.py')
    context=source('nanovllm.utils.context','nanovllm/utils/context.py')
    for name,attrs in {
        'nanovllm.config':{'Config':object},
        'nanovllm.models.qwen3':{'Qwen3ForCausalLM':object},
        'nanovllm.layers.sampler':{'Sampler':object},
        'nanovllm.utils.loader':{'load_model':None},
    }.items():
        m=types.ModuleType(name);m.__dict__.update(attrs);sys.modules[name]=m
    runner=source('nanovllm.engine.model_runner','nanovllm/engine/model_runner.py')
    return seq.Sequence,runner.ModelRunner,context

class StopBeforeNCCL(Exception):
    pass

def _probe_worker(variant,block_size,payloads,connection):
    try:
        torch.set_num_threads(1)
        Sequence,ModelRunner,context=_load(variant)
        default_before=Sequence.block_size
        config=types.SimpleNamespace(kvcache_block_size=block_size,hf_config=None,enforce_eager=True,tensor_parallel_size=2)
        runner=ModelRunner.__new__(ModelRunner)
        with patch('torch.distributed.init_process_group',side_effect=StopBeforeNCCL):
            try:
                runner.__init__(config,rank=1,event=None)
            except StopBeforeNCCL:
                pass
            else:
                raise AssertionError('NCCL boundary was not reached')
        tensor=torch.tensor
        def cpu_tensor(*args,**kwargs):
            kwargs.pop('pin_memory',None)
            return tensor(*args,**kwargs)
        results=[]
        for payload in payloads:
            seq=pickle.loads(payload)
            with patch('torch.tensor',side_effect=cpu_tensor), patch.object(torch.Tensor,'cuda',lambda self,*a,**k:self):
                ids,positions=runner.prepare_decode([seq])
            results.append({'last_block_tokens':seq.last_block_num_tokens,'slot':context.get_context().slot_mapping.item(),'position':positions.item(),'token':ids.item()})
        connection.send({'initial_default':default_before,'worker_block_size':Sequence.block_size,'results':results})
    except Exception as e:
        import traceback
        connection.send({'error':repr(e),'traceback':traceback.format_exc()})
    finally:
        connection.close()

@pytest.mark.parametrize('block_size,lengths',[
    (256,[1,255,256,257,511,513]),
    (512,[1,255,256,257,511,512,513,769]),
    (1024,[257,511,512,513,769,1023,1024,1025]),
    (1536,[257,769,1025,1281,1535,1536,1537]),
])
def test_spawned_rank_uses_configured_block_size_for_real_decode_slots(block_size,lengths):
    variant=os.getenv('VARIANT','after')
    Sequence,_,_=_load(variant)
    Sequence.block_size=block_size
    payloads=[];expected=[]
    for length in lengths:
        seq=Sequence([9]*length)
        seq.is_prefill=False
        seq.block_table=list(range(5,5+seq.num_blocks))
        payloads.append(pickle.dumps(seq))
        expected.append({'last_block_tokens':(length-1)%block_size+1,'slot':seq.block_table[-1]*block_size+(length-1)%block_size,'position':length-1,'token':9})
    parent,child=multiprocessing.get_context('spawn').Pipe(duplex=False)
    process=multiprocessing.get_context('spawn').Process(target=_probe_worker,args=(variant,block_size,payloads,child))
    process.start();child.close()
    try:
        assert parent.poll(25),'worker timed out'
        observed=parent.recv()
    finally:
        process.join(5)
        if process.is_alive():process.terminate();process.join()
        parent.close()
    assert process.exitcode==0
    assert 'error' not in observed,observed
    assert observed['initial_default']==256, 'worker must be a fresh interpreter'
    assert observed['results']==expected
    assert observed['worker_block_size']==block_size
