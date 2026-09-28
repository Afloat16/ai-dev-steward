# AI project repair investigations — 2026-09-28

## Actual outcome / 实际状态

**15 local candidate repairs are NOT 15 merged upstream contributions.**

This session produced three upstream issue reports and one supplemental PR conversation comment under Afloat16. It created **zero upstream pull requests and zero merged changes**. The earlier smolagents #2861 is not counted here.

The candidate variants passed **167 isolated regression/control tests**. The unmodified variants produced **81 failures and 86 passes**. These are newly written source-excerpt harness tests, not the projects' full existing suites. No model inference, paid APIs, GPU training or repository-wide CI was run.

| Project | Candidate change | Baseline failed/passed | Candidate passed | Actual upstream outcome |
|---|---|---:|---:|---|
| mem0ai/mem0 | Remove reasoning prefix before JSON fence | 4/8 | 12 | Issue creation denied: 403 |
| unclecode/crawl4ai | Validate non-progressing/invalid chunk windows | 7/6 | 13 | [Supplemental tests on existing PR #2012](https://github.com/unclecode/crawl4ai/pull/2012#issuecomment-5870441734) |
| crewAIInc/crewAI | Preserve token boundary at JSONC block comments | 4/7 | 11 | [Issue #7797](https://github.com/crewAIInc/crewAI/issues/7797) |
| agno-agi/agno | Avoid extending a scalar during JSON merging | 5/6 | 11 | [Issue #10649](https://github.com/agno-agi/agno/issues/10649) |
| FoundationAgents/MetaGPT | Preserve escaped quotes and URLs during comment removal | 6/5 | 11 | [Issue #2165](https://github.com/FoundationAgents/MetaGPT/issues/2165) |
| run-llama/llama_index | Use LinearRegression.predict | 5/3 | 8 | Held for required human oversight |
| huggingface/accelerate | Count bool tensor storage as one byte | 4/9 | 13 | [Existing PR #4236](https://github.com/huggingface/accelerate/pull/4236); no duplicate submission |
| huggingface/diffusers | Squeeze grayscale channel, not spatial dimensions | 4/5 | 9 | Issue creation denied: 403 |
| microsoft/autogen | Accept CRLF and horizontal padding in JSON fences | 6/5 | 11 | [Existing PR #8081](https://github.com/microsoft/autogen/pull/8081); supplemental comment denied: 403 |
| openai/whisper | Keep embedded line endings out of TSV rows | 4/6 | 10 | [Existing PR #2846](https://github.com/openai/whisper/pull/2846); no duplicate submission |
| huggingface/sentence-transformers | Convert bfloat16 before NumPy quantization | 16/4 | 20 | [Existing PR #4089](https://github.com/huggingface/sentence-transformers/pull/4089); no duplicate submission |
| karpathy/micrograd | Zero derivative for exponent zero without evaluating zero to negative power | 3/7 | 10 | Issue creation denied: 403 |
| huggingface/datasets | Read format fields by their named regex groups | 5/5 | 10 | Issue creation denied: 403 |
| microsoft/markitdown | Normalize string/list notebook sources for title extraction | 3/6 | 9 | [Existing issue #2115 / PR #2113](https://github.com/microsoft/markitdown/issues/2115); no duplicate submission |
| gradio-app/gradio | Widen 8-bit and float16 arithmetic before audio conversion | 5/4 | 9 | External PRs paused; issue creation denied: 403 |

## How to read the patch files

`patches/` contains review diffs generated from isolated helper/class excerpts. **Their hunk offsets and context are NOT certified against a full upstream checkout.** Some harnesses omit docstrings or simplify imports/formatting; Sentence Transformers' diff, for example, contains a harness-only docstring comment. Do not apply these blindly or treat them as merge-ready PR patches. Rebase the logical change onto the exact source, add tests in that repository's layout, and run its checks first.

Source Git blob identifiers are in `sources.json`. Only the complete small micrograd engine and AutoGen JSON helper were additionally byte-verified as full modules. Other tests execute inspected helper logic with explicitly limited scaffolding for logger, result objects or types; they do not establish package integration correctness.

The full reproducible source-excerpt harnesses, before/after logs, manifests and local runner are supplied in the accompanying evidence archive delivered in the ChatGPT conversation. This branch publishes the review diffs and outcome register, not that complete archive. It does not modify this repository's main branch or existing application files.

## Review and attribution notes

- Existing upstream PRs belong to their actual authors. They are linked for deduplication, not claimed as Afloat16's work.
- CrewAI's requested `llm-generated` label was not applied, and adding it returned 403. The issue body explicitly discloses AI use; a maintainer still needs to handle the label.
- LlamaIndex's contribution policy requires human oversight. No human-review checkbox was checked on the user's behalf.
- The Diffusers candidate covers the utility helper only. Similar image-processor paths were located but not executed or repaired in this bundle.
- Crawl4AI's proposed rejection of overlap >= window is an API choice awaiting maintainers, not an accepted contract.
- All investigation, candidate changes, tests and posts were performed by an AI assistant on the user's behalf. No personal human reproduction/review or production incident is claimed.
- Original source/context remains owned by its upstream authors and subject to each upstream license. This repository's root license does not relicense upstream excerpts.

Environment: Python 3.13.5/Linux x86_64; pytest 9.0.2; NumPy 2.3.5; PyTorch 2.10.0+cpu; Pydantic 2.13.4; scikit-learn 1.8.0; Pillow 12.3.0; regex 2026.5.9.
