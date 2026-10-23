import re
from functools import lru_cache
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from app.config import settings
from app.documents import has_term, skills

VERSION = "evidence-v1/taxonomy-v1/chunks-900"


def feature_vector(resume, job):
    r, j = np.asarray(resume), np.asarray(job)
    if r.shape != j.shape or r.ndim != 1:
        raise ValueError("Embeddings must have the same one-dimensional shape")
    return np.concatenate([np.abs(r - j), r * j])


@lru_cache(maxsize=1)
def embedder():
    if not settings.embedding_path:
        return None
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_path, local_files_only=True)


def passage_embeddings(texts):
    model = embedder()
    if model is None:
        return [None] * len(texts)
    vectors = model.encode(texts, normalize_embeddings=True)
    if vectors.shape != (len(texts), 384):
        raise ValueError("Configured embedder must produce 384-dimensional vectors")
    return vectors.tolist()


def match(requirements: list, sections: list):
    texts = [s.text for s in sections]
    req_texts = [r["text"] for r in requirements]
    tfidf = np.zeros((len(requirements), len(sections)))
    if texts and req_texts:
        try:
            # Per-comparison retrieval baseline. This is not a trained fit classifier.
            matrix = TfidfVectorizer(ngram_range=(1, 2)).fit_transform(texts + req_texts)
            tfidf = cosine_similarity(matrix[len(texts) :], matrix[: len(texts)])
        except ValueError:
            pass
    semantic = None
    model = embedder()
    if model is not None and texts and requirements:
        vectors = (
            np.asarray([s.embedding for s in sections])
            if all(s.embedding is not None for s in sections)
            else np.asarray(passage_embeddings(texts))
        )
        semantic = model.encode(req_texts, normalize_embeddings=True) @ vectors.T
    evidence = []
    credit = 0.0
    for i, req in enumerate(requirements):
        terms = skills(req["text"])
        if req.get("canonical_skill"):
            terms = list(set(terms + [req["canonical_skill"]]))
        explicit = []
        for s in sections:
            # Skill mentions alone do not establish degrees, licenses or experience duration.
            if req["kind"] == "skill" and terms and all(has_term(s.text, term) for term in terms):
                if not re.search(r"\b(no|not|without|lack|learning|beginner)\b", s.text, re.I):
                    explicit.append(s)
        decision = "supported" if explicit else "not_evidenced"
        scores = semantic[i] if semantic is not None else tfidf[i]
        top = int(np.argmax(scores)) if len(scores) else None
        chosen = explicit[0] if explicit else (sections[top] if top is not None and scores[top] > 0.10 else None)
        if not explicit and chosen is not None:
            decision = "uncertain"
            if (
                req["kind"] == "skill"
                and len(terms) > 1
                and any(has_term(chosen.text, term) for term in terms)
                and not re.search(r"\b(no|not|without|lack|learning|beginner)\b", chosen.text, re.I)
            ):
                decision = "partial"
        credit += req["weight"] * ({"supported": 1, "partial": 0.5}.get(decision, 0))
        evidence.append(
            {
                "requirement_id": req["id"],
                "requirement_text": req["text"],
                "required": req["required"],
                "weight": req["weight"],
                "decision": decision,
                "explanation": "Explicit skill mentions; recruiter must verify context."
                if explicit
                else "Related text does not establish this requirement."
                if chosen
                else "No supporting passage found.",
                "supporting_evidence": [
                    {
                        "section_id": chosen.id,
                        "page": chosen.page,
                        "start": chosen.start,
                        "end": chosen.end,
                        "excerpt": chosen.text,
                    }
                ]
                if chosen
                else [],
            }
        )
    total = sum(r["weight"] for r in requirements)
    return {
        "requirement_evidence_coverage": round(100 * credit / total, 2) if total else 0,
        "semantic_similarity": float(np.max(semantic, axis=1).mean()) if semantic is not None else None,
        "tfidf_similarity": float(np.max(tfidf, axis=1).mean()) if tfidf.size else 0,
        "dataset_fit_prediction": None,
        "experimental_model": False,
        "needs_human_review": True,
        "model_version": VERSION,
        "embedding_model": settings.embedding_revision or None,
        "requirements": evidence,
        "limitations": "Missing evidence does not mean missing ability. Similarity is not a hiring probability. "
        "Partial evidence receives half credit; uncertain evidence receives none. "
        "Skill mentions may be ambiguous; human review is required.",
    }
