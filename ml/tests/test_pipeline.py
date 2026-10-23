import json
from types import SimpleNamespace
import numpy as np
import pytest
from ml.pipeline import audit, normalize, read_rows, split_rows, train


def make_rows(tmp_path, n=500):
    path = tmp_path / "pairs.jsonl"
    with path.open("w", encoding="utf-8") as out:
        for i in range(n):
            word = ["Python backend SQL", "React design frontend", "Java enterprise services"][i % 3]
            out.write(
                json.dumps(
                    {
                        "resume": f"{word} project {i}",
                        "jd": f"{word} role {i}",
                        "label": ["Good Fit", "Potential Fit", "No Fit"][i % 3],
                        "source": "synthetic-pipeline-test",
                    }
                )
                + "\n"
            )
    return path, read_rows(path)


def test_strict_split_has_no_identity_leakage(tmp_path):
    _, rows = make_rows(tmp_path)
    splits = split_rows(rows)
    for feature in ["resume_hash", "jd_hash", "pair_hash"]:
        sets = [{rows[i][feature] for i in splits[s]} for s in ["train", "validation", "test"]]
        assert not sets[0] & sets[1] and not sets[0] & sets[2] and not sets[1] & sets[2]
    assert len(splits["excluded"]) > 0


def test_audit_flags_conflicting_duplicates(tmp_path):
    _, rows = make_rows(tmp_path, 3)
    rows.append({**rows[0], "label": "No Fit"})
    assert audit(rows)["conflicting_pairs"] == 1
    assert 0 not in sum([v for k, v in split_rows(rows).items() if k != "excluded"], [])
    assert normalize("C++  C#\nNode.js") == "C++ C# Node.js"


def test_offline_training_creates_actual_evaluation(tmp_path):
    path, _ = make_rows(tmp_path)
    args = SimpleNamespace(data=str(path), split="strict", seed=42, model="tfidf", output=str(tmp_path / "model"))
    report = train(args, read_rows(path))
    assert len(report["confusion_matrix"]) == 3
    assert 0 <= report["test_accuracy"] <= 1
    assert len(report["artifact_sha256"]) == 64
    assert report["human_grounding_metrics"] is None


def test_pair_embedding_features():
    from app.matching import feature_vector

    assert feature_vector(np.zeros(384), np.ones(384)).shape == (768,)
    with pytest.raises(ValueError):
        feature_vector([1], [1, 2])
