# E56: local semantic file selection

Research-only, default-off. No gold or patch enters retrieval. The candidate
is [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B),
Apache-2.0, pinned to `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`.
This is the released initialization family used by SweRank+, not its
unavailable multilingual fine-tuned retriever. Pretraining contamination of
benchmark repositories is unknown; these are exploratory benchmark results,
not a claim of unseen-repository generalization.

Index only the shipped engine's actual corpus at the instance's base commit.
Split each file into 384 model-token chunks at stride 320, prefix each with
its path, and embed with last-token pooling and unit normalization. Bound model
inputs to 512 tokens. Rank files by maximum chunk cosine similarity. Query
instruction: "Given a software issue, retrieve source code relevant to fixing
the issue." Cache document embeddings by content, pinned model, device,
dtype, and pooling configuration; query text remains the full problem statement
before tokenizer truncation. Report cold indexing and query costs separately.

Two predeclared file-selection treatments: top 10 dense files, and top 26
files from equal reciprocal-rank fusion (constant 60) of dense and the existing
engine's selected-file ordering. Both use E55's unchanged lexical packer,
scores, anchors, and 8192-token requested budget. The second list tests whether
a complementary signal preserves lexical strengths. Neither uses oracle files.

Start with two wiring/performance instances, then full Rust and C++ discovery
if the implementation works. Apply original exact FILE/FUNCTION/LINE scoring,
strict error-zero fractions, and paired analysis across both treatments and
languages. Record model/binary/input/output hashes, runtime versions, embedding
cache reuse, and actual tokens. Improvements must survive other discovery
languages and Python Lite before default consideration; Verified remains held
out. No production model dependency is introduced by the lab experiment.
