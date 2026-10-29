"""BM25 over the playbook's clauses, filtered by the phase a clause applies from (plan section 4):
30 clauses need no vector store, and BM25 is deterministic and explainable."""

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.playbook.clauses import Clause

PHASE = re.compile(r"\(from T-(\d+)\)")
TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


@dataclass(frozen=True)
class ClauseIndex:
    clauses: list[Clause]
    bm25: BM25Okapi

    @classmethod
    def build(cls, clauses: list[Clause]) -> "ClauseIndex":
        corpus = [_tokens(f"{c.title} {c.text}") for c in clauses]
        return cls(clauses, BM25Okapi(corpus))

    def in_force(self, clause: Clause, hours_to_landfall: float) -> bool:
        """A clause tagged "(from T-n)" applies from n hours out; untagged clauses always do."""
        phase = PHASE.search(clause.title)
        return phase is None or hours_to_landfall <= int(phase.group(1))

    def search(
        self, queries: list[str], hours_to_landfall: float, per_query: int, max_clauses: int
    ) -> list[Clause]:
        """The best clauses per query, in force at this lead time, deduplicated and capped."""
        found: list[Clause] = []
        for query in queries:
            scores = self.bm25.get_scores(_tokens(query))
            ranked = sorted(
                (i for i, c in enumerate(self.clauses) if self.in_force(c, hours_to_landfall)),
                key=lambda i: (-scores[i], self.clauses[i].id),
            )
            for i in ranked[:per_query]:
                if self.clauses[i] not in found and scores[i] > 0:
                    found.append(self.clauses[i])
        return found[:max_clauses]
