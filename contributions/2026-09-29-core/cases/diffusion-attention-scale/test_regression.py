"""Compare the complete Attend module against an independent attention formula."""
import importlib.util
import os
from pathlib import Path
import pytest
import torch

torch.set_num_threads(1)
SOURCE = Path(__file__).parent / os.getenv('VARIANT', 'after') / 'denoising_diffusion_pytorch/attend.py'
spec = importlib.util.spec_from_file_location('tested_attend', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

@pytest.mark.parametrize('head_dim', [1, 4, 16, 32])
@pytest.mark.parametrize('scale', [None, 0.0, 0.125, 0.7, 2.0])
def test_attention_outputs_and_input_gradients_match_formula(head_dim, scale):
    generator = torch.Generator().manual_seed(113)
    q = torch.randn(2, 2, 3, head_dim, generator=generator, dtype=torch.float64, requires_grad=True)
    k = torch.randn(2, 2, 5, head_dim, generator=generator, dtype=torch.float64, requires_grad=True)
    v = torch.randn(2, 2, 5, head_dim, generator=generator, dtype=torch.float64, requires_grad=True)
    effective_scale = head_dim ** -0.5 if scale is None else scale
    expected = ((q @ k.transpose(-1, -2)) * effective_scale).softmax(-1) @ v
    slow = module.Attend(flash=False, scale=scale).eval()(q, k, v)
    fast = module.Attend(flash=True, scale=scale).eval()(q, k, v)
    torch.testing.assert_close(slow, expected, rtol=1e-10, atol=1e-10)
    torch.testing.assert_close(fast, expected, rtol=1e-10, atol=1e-10)
    weight = torch.randn(expected.shape, generator=generator, dtype=torch.float64)
    expected_grads = torch.autograd.grad((expected * weight).sum(), (q, k, v), retain_graph=True)
    fast_grads = torch.autograd.grad((fast * weight).sum(), (q, k, v))
    for actual, wanted in zip(fast_grads, expected_grads):
        torch.testing.assert_close(actual, wanted, rtol=1e-9, atol=1e-9)

@pytest.mark.parametrize('scale', [None, 0.125, 0.7])
def test_eval_disables_dropout_and_handles_noncontiguous_inputs(scale):
    torch.manual_seed(55)
    tensors = [torch.randn(2, 3, 2, 8).transpose(1, 2) for _ in range(3)]
    expected = module.Attend(flash=False, scale=scale, dropout=0.6).eval()(*tensors)
    fast = module.Attend(flash=True, scale=scale, dropout=0.6).eval()
    torch.testing.assert_close(fast(*tensors), expected)
    torch.testing.assert_close(fast(*tensors), expected)
