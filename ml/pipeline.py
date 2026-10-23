"""Offline acquisition, leakage auditing, splitting, training and held-out evaluation.

Run from the repository root. Raw data and model binaries never belong in Git.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import unicodedata
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from scipy.sparse import hstack

LABELS = ["Good Fit", "Potential Fit", "No Fit"]
DATASET = "med2425/resume-job-fit-merged-v1"


def normalize(text):
    return " ".join(unicodedata.normalize("NFKC", text).split())


def fingerprint(text):
    return hashlib.sha256(normalize(text).casefold().encode()).hexdigest()


def read_rows(path):
    rows = []
    with Path(path).open(encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            if not all(isinstance(row.get(k), str) and row[k].strip() for k in ["resume", "jd", "label", "source"]):
                raise ValueError("Missing resume, jd, label or source")
            if row["label"] not in LABELS:
                raise ValueError("Unknown label")
            row = {**row, "resume": normalize(row["resume"]), "jd": normalize(row["jd"])}
            row["resume_hash"], row["jd_hash"] = fingerprint(row["resume"]), fingerprint(row["jd"])
            row["pair_hash"] = fingerprint(row["resume_hash"] + row["jd_hash"])
            rows.append(row)
    if not rows:
        raise ValueError("Dataset is empty")
    return rows


def save_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def fetch(args):
    if (
        not args.accept_terms
        or not args.revision
        or len(args.revision) != 40
        or any(c not in "0123456789abcdef" for c in args.revision)
    ):
        raise ValueError("Review dataset/upstream terms, pass --accept-terms and a 40-character --revision SHA")
    from datasets import load_dataset

    dataset = load_dataset(DATASET, revision=args.revision)
    path = Path(args.data)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for split, records in dataset.items():
            for row in records:
                output.write(json.dumps({**row, "benchmark_split": split}, ensure_ascii=False) + "\n")
    save_json(
        path.with_suffix(".provenance.json"),
        {
            "dataset": DATASET,
            "revision": args.revision,
            "terms_reviewed_by_operator": True,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "labels": "Qwen2.5-32B proxy labels; not human hiring ground truth",
        },
    )


def audit(rows):
    pairs = Counter(r["pair_hash"] for r in rows)
    labels = {}
    for r in rows:
        labels.setdefault(r["pair_hash"], set()).add(r["label"])
    train = [r for r in rows if r.get("benchmark_split") == "train"]
    test = [r for r in rows if r.get("benchmark_split") == "test"]
    return {
        "rows": len(rows),
        "labels": dict(Counter(r["label"] for r in rows)),
        "sources": dict(Counter(r["source"] for r in rows)),
        "resume_domains": dict(Counter(r.get("resume_domain", "unknown") for r in rows)),
        "jd_domains": dict(Counter(r.get("jd_domain", "unknown") for r in rows)),
        "source_labels": {
            source: dict(Counter(r["label"] for r in rows if r["source"] == source))
            for source in sorted({r["source"] for r in rows})
        },
        "duplicate_pairs": sum(n - 1 for n in pairs.values()),
        "conflicting_pairs": sum(len(v) > 1 for v in labels.values()),
        "benchmark_overlap": {
            field: len({r[field] for r in train} & {r[field] for r in test})
            for field in ["resume_hash", "jd_hash", "pair_hash"]
        },
    }


def partition(value, seed):
    number = int(hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()[:8], 16) % 100
    return "train" if number < 70 else "validation" if number < 85 else "test"


def split_rows(rows, mode="strict", seed=42):
    output = {"train": [], "validation": [], "test": [], "excluded": []}
    seen = set()
    conflicting = {}
    for r in rows:
        conflicting.setdefault(r["pair_hash"], set()).add(r["label"])
    for i, r in enumerate(rows):
        if r["pair_hash"] in seen or len(conflicting[r["pair_hash"]]) > 1:
            output["excluded"].append(i)
            continue
        seen.add(r["pair_hash"])
        j = partition(r["jd_hash"], seed)
        rr = partition(r["resume_hash"], seed)
        if mode == "benchmark":
            target = r.get("benchmark_split", "excluded")
            if target == "train":
                target = "validation" if j == "validation" else "train"
        elif mode == "unseen-job":
            target = j
        else:
            target = j if rr == j else "excluded"
        output.get(target, output["excluded"]).append(i)
    return output


def pair_features(vectorizer, rows):
    resume = vectorizer.transform([r["resume"] for r in rows])
    job = vectorizer.transform([r["jd"] for r in rows])
    return hstack([abs(resume - job), resume.multiply(job)]).tocsr()


def embedding_features(rows, path):
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(path, local_files_only=True)

    # Mean pooling over bounded passages avoids silently truncating entire CVs.
    def pooled(text):
        chunks = [text[i : i + 900] for i in range(0, len(text), 900)]
        vector = model.encode(chunks, normalize_embeddings=True).mean(axis=0)
        return vector / max(float(np.linalg.norm(vector)), 1e-12)

    output = []
    for row in rows:
        r, j = pooled(row["resume"]), pooled(row["jd"])
        output.append(np.concatenate([np.abs(r - j), r * j]))
    return np.asarray(output)


def train(args, rows):
    import joblib

    splits = split_rows(rows, args.split, args.seed)
    train_rows, validation_rows, test_rows = [[rows[i] for i in splits[s]] for s in ["train", "validation", "test"]]
    if not all([train_rows, validation_rows, test_rows]) or len({r["label"] for r in train_rows}) < 2:
        raise ValueError("Split needs nonempty train/validation/test and multiple training classes")
    vectorizer = None
    if args.model == "tfidf":
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=30000, sublinear_tf=True)
        vectorizer.fit([text for r in train_rows for text in [r["resume"], r["jd"]]])
        features = [pair_features(vectorizer, group) for group in [train_rows, validation_rows, test_rows]]
    else:
        if not args.embedding_path:
            raise ValueError("--embedding-path must reference a prepared local model")
        features = [
            embedding_features(group, args.embedding_path) for group in [train_rows, validation_rows, test_rows]
        ]
    best, best_f1, best_c = None, -1, None
    for c in [0.1, 1, 10]:
        classifier = LogisticRegression(C=c, max_iter=1000, random_state=args.seed, class_weight="balanced")
        classifier.fit(features[0], [r["label"] for r in train_rows])
        score = classification_report(
            [r["label"] for r in validation_rows], classifier.predict(features[1]), output_dict=True, zero_division=0
        )["macro avg"]["f1-score"]
        if score > best_f1:
            best, best_f1, best_c = classifier, score, c
    predictions = best.predict(features[2])
    truth = [r["label"] for r in test_rows]
    report = {
        "model": args.model,
        "selected_C": best_c,
        "split": args.split,
        "seed": args.seed,
        "counts": {s: len(v) for s, v in splits.items()},
        "validation_macro_f1": best_f1,
        "test_accuracy": accuracy_score(truth, predictions),
        "test_classification": classification_report(
            truth, predictions, labels=LABELS, output_dict=True, zero_division=0
        ),
        "confusion_matrix": confusion_matrix(truth, predictions, labels=LABELS).tolist(),
        "label_order": LABELS,
        "data_sha256": hashlib.sha256(Path(args.data).read_bytes()).hexdigest(),
        "limitation": "Agreement with dataset proxy labels only. No hiring-validity claim.",
        "retrieval_metrics": None,
        "human_grounding_metrics": None,
        "embedding_revision": args.embedding_revision if args.model == "embeddings" else None,
    }
    folder = Path(args.output)
    folder.mkdir(parents=True, exist_ok=True)
    model_file = folder / "model.joblib"
    joblib.dump({"classifier": best, "vectorizer": vectorizer, "model": args.model}, model_file)
    report["artifact_sha256"] = hashlib.sha256(model_file.read_bytes()).hexdigest()
    save_json(folder / "evaluation.json", report)
    save_json(
        folder / "split_manifest.json", {s: [rows[i]["pair_hash"] for i in values] for s, values in splits.items()}
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch", "audit", "split", "train"])
    parser.add_argument("--data", default="data/pairs.jsonl")
    parser.add_argument("--output", default="artifacts/baseline-v1")
    parser.add_argument("--revision")
    parser.add_argument("--accept-terms", action="store_true")
    parser.add_argument("--split", choices=["benchmark", "unseen-job", "strict"], default="strict")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", choices=["tfidf", "embeddings"], default="tfidf")
    parser.add_argument("--embedding-path")
    parser.add_argument("--embedding-revision")
    args = parser.parse_args()
    if args.command == "fetch":
        fetch(args)
    else:
        rows = read_rows(args.data)
        if args.command == "audit":
            save_json(Path(args.output) / "audit.json", audit(rows))
        elif args.command == "split":
            splits = split_rows(rows, args.split, args.seed)
            save_json(
                Path(args.output) / f"split-{args.split}.json",
                {s: [rows[i]["pair_hash"] for i in ids] for s, ids in splits.items()},
            )
        else:
            train(args, rows)


if __name__ == "__main__":
    main()
