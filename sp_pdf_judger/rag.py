from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from .config import UCUM_JSON_CANDIDATES
from .utils import clean_text


@dataclass
class RagDoc:
    idx: int
    text: str
    meta: dict


class UcumRagStore:
    def __init__(self) -> None:
        self.docs: list[RagDoc] = []
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None
        self._load()

    def _resolve_ucum_path(self) -> Path:
        for candidate in UCUM_JSON_CANDIDATES:
            if candidate.exists():
                return candidate
        raise FileNotFoundError("ucum_rag_docs.json 파일을 찾을 수 없습니다.")

    def _load(self) -> None:
        path = self._resolve_ucum_path()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        docs: list[RagDoc] = []
        for idx, item in enumerate(data):
            text = clean_text(item.get("text"))
            if not text:
                continue
            docs.append(RagDoc(idx=idx, text=text, meta=item))

        self.docs = docs
        corpus = [d.text for d in docs] or [""]
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2))
        self.matrix = self.vectorizer.fit_transform(corpus)

    def search(self, query: str, top_k: int = 5) -> list[RagDoc]:
        query = clean_text(query)
        if not query or not self.docs or self.vectorizer is None or self.matrix is None:
            return []

        qv = self.vectorizer.transform([query])
        scores = linear_kernel(qv, self.matrix).flatten()
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        out: list[RagDoc] = []
        for i in ranked[:top_k]:
            if scores[i] <= 0:
                continue
            out.append(self.docs[i])
        return out
