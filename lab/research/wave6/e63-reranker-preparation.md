# E63 preparation: query/code cross-encoder

[SweRank+](https://arxiv.org/abs/2512.20482) combines retrieval with a
specialized reranker. The current E56–E58 candidates evaluate embedding
similarity; they do not test a model jointly attending to the issue and code.
The [official Qwen reranker](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B)
is available under Apache-2.0, pinned here at
`e61197ed45024b0ed8a2d74b80b4d909f1255473`. Its availability does not establish
that it will improve this benchmark or that its training excludes it.

`e63_rerank.py` implements native MLX inference over the original tied-head
weights, in float16, comparing final yes/no logits in float32. The prompt
format follows the official model card. The issue and document are separately
limited to 768 and 1024 model tokens so long issues cannot erase the code;
the complete sequence must fit 2048 tokens. Batches contain at most eight
pairs. Cache keys include both texts, prompt, model revision, implementation
settings, and package versions.

`e63_probe.py` checks a synthetic relevant/irrelevant pair against PyTorch
MPS, cache replay, and preservation of code with an oversized issue. It
uses no discovery or Verified labels and is only a backend integrity check.
Run it in the E58 MLX environment:

```sh
python lab/e63_probe.py --out /tmp/e63-probe.json
```

The backend probe preceded the registered [E63 retrieval protocol](e63-protocol.md).
That protocol freezes candidate-pool selection, ordering, packing, source-cache
provenance, and the expanded seven-candidate correction before benchmark runs.
It reuses completed source embeddings and reranks a bounded candidate pool,
then applies the unchanged exact token-budget scorer. The synthetic probe
remains implementation evidence, not a discovery result.
