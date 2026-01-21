"""Embedding pipeline for the Evidence Workbench."""

from .embedder import Embedder, embed_extractions
from .similarity import cosine_similarity, find_similar

__all__ = ["Embedder", "embed_extractions", "cosine_similarity", "find_similar"]
