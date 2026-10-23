# Offline research

Install optional dependencies: `python -m pip install -r ml/requirements.in`.
Run all commands from the repository root with the backend environment active.

```sh
python -m ml.pipeline fetch --revision <40-character-dataset-commit> --accept-terms
python -m ml.pipeline audit
python -m ml.pipeline split --split benchmark
python -m ml.pipeline split --split unseen-job
python -m ml.pipeline split --split strict
python -m ml.pipeline train --model tfidf --split strict --output artifacts/tfidf-v1
python -m ml.fetch_embedding --revision <40-character-model-commit> --output artifacts/minilm
python -m ml.pipeline train --model embeddings --embedding-path artifacts/minilm --embedding-revision <commit> --output artifacts/pair-v1
```

The dataset card does not declare a license. Resolve upstream permissions before accepting terms. Fetch is never part of startup, builds or requests. TF-IDF fits training text only. Logistic regression selects C on validation macro-F1, then evaluates the test split once per invocation. Do not tune using repeated test runs. Strict splits discard crossing resume/job pairs; exact duplicates/conflicting labels are excluded. Exact-text identity fingerprints cannot detect every paraphrase or person identity.

Metrics measure agreement with LLM-generated labels, not hiring outcomes. Retrieval/grounding/fairness benchmarks need independently annotated data and are not fabricated. Synthetic pipeline tests are software checks, not model performance evidence. Full dataset training has not been run on the initial host.
