# Model card

Default runtime: `evidence-v1/taxonomy-v1/chunks-900`. Deterministic canonical skill mentions support only skill requirements; negation/learning language conservatively prevents full support. Experience, education and license requirements remain uncertain unless independently reviewed. TF-IDF retrieves related bounded passages; it is fitted per comparison and is not a frozen benchmark classifier. The separate offline TF-IDF experiment fits training data only.

Coverage: weighted supported=1, partial=0.5, uncertain/not_evidenced=0; denominator includes required and preferred requirements at their explicit weights. Required does not create an automatic disqualification. Quotes come directly from persisted passages. Human correction invalidates prior outputs.

Optional semantic model: `sentence-transformers/all-MiniLM-L6-v2`, expected 384 dimensions. Load a reviewed local directory via `EMBEDDING_PATH`, record its exact source commit in `EMBEDDING_REVISION`. Nothing downloads on startup. Semantic inference is implemented but has not been exercised with downloaded weights on the initial host. No experimental fit classifier is loaded into runtime; output is null.

Offline experiments support TF-IDF pair features and pooled embedding features `concat(abs(r-j),r*j)`, LogisticRegression, validation selection and held-out reporting. Artifacts/checksums are saved locally. They are not automatically promoted into the serving application. Labels represent an LLM-generated dataset task and must never be interpreted as probability of hiring success.

Limitations: dictionary coverage, conservative passage-level negation, text extraction quality, chunk boundaries, lexical false positives, ambiguous context and model bias. No protected attributes are intentional matching features. General text may still contain demographic proxies; controlled fairness/sensitivity evaluation is pending. No independent hiring-validity, fairness or legal-compliance claim is made.
