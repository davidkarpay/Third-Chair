"""Vector similarity functions for the Evidence Workbench."""

import struct
from typing import Optional


def _bytes_to_floats(data: bytes) -> list[float]:
    """Convert bytes to list of floats (assumes float32 little-endian)."""
    n_floats = len(data) // 4
    return list(struct.unpack(f"<{n_floats}f", data))


def _floats_to_bytes(floats: list[float]) -> bytes:
    """Convert list of floats to bytes (float32 little-endian)."""
    return struct.pack(f"<{len(floats)}f", *floats)


def cosine_similarity(vec_a: list[float] | bytes, vec_b: list[float] | bytes) -> float:
    """Calculate cosine similarity between two vectors.

    Args:
        vec_a: First vector (list of floats or bytes)
        vec_b: Second vector (list of floats or bytes)

    Returns:
        Cosine similarity score between -1 and 1
    """
    # Convert bytes to floats if needed
    if isinstance(vec_a, bytes):
        vec_a = _bytes_to_floats(vec_a)
    if isinstance(vec_b, bytes):
        vec_b = _bytes_to_floats(vec_b)

    if len(vec_a) != len(vec_b):
        raise ValueError(f"Vector dimensions don't match: {len(vec_a)} vs {len(vec_b)}")

    # Calculate dot product and magnitudes
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    magnitude_a = sum(a * a for a in vec_a) ** 0.5
    magnitude_b = sum(b * b for b in vec_b) ** 0.5

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)


def cosine_similarity_numpy(
    vec_a: list[float] | bytes, vec_b: list[float] | bytes
) -> float:
    """Calculate cosine similarity using numpy (faster for large vectors).

    Falls back to pure Python if numpy is not available.
    """
    try:
        import numpy as np

        # Convert bytes to numpy arrays if needed
        if isinstance(vec_a, bytes):
            vec_a = np.frombuffer(vec_a, dtype=np.float32)
        else:
            vec_a = np.array(vec_a, dtype=np.float32)

        if isinstance(vec_b, bytes):
            vec_b = np.frombuffer(vec_b, dtype=np.float32)
        else:
            vec_b = np.array(vec_b, dtype=np.float32)

        dot_product = np.dot(vec_a, vec_b)
        magnitude_a = np.linalg.norm(vec_a)
        magnitude_b = np.linalg.norm(vec_b)

        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0

        return float(dot_product / (magnitude_a * magnitude_b))

    except ImportError:
        # Fall back to pure Python
        return cosine_similarity(vec_a, vec_b)


def find_similar(
    query_vector: list[float] | bytes,
    candidates: list[tuple[str, bytes]],
    threshold: float = 0.7,
    top_k: Optional[int] = None,
) -> list[tuple[str, float]]:
    """Find similar vectors from a list of candidates.

    Args:
        query_vector: The vector to search for
        candidates: List of (id, vector_bytes) tuples
        threshold: Minimum similarity score to include
        top_k: Optional limit on number of results

    Returns:
        List of (id, similarity_score) tuples, sorted by similarity descending
    """
    results: list[tuple[str, float]] = []

    for candidate_id, candidate_vector in candidates:
        similarity = cosine_similarity_numpy(query_vector, candidate_vector)
        if similarity >= threshold:
            results.append((candidate_id, similarity))

    # Sort by similarity descending
    results.sort(key=lambda x: x[1], reverse=True)

    if top_k:
        results = results[:top_k]

    return results


def find_similar_pairs(
    embeddings: list[tuple[str, bytes]],
    threshold: float = 0.7,
) -> list[tuple[str, str, float]]:
    """Find all pairs of similar vectors.

    Args:
        embeddings: List of (id, vector_bytes) tuples
        threshold: Minimum similarity score to include

    Returns:
        List of (id_a, id_b, similarity_score) tuples
    """
    pairs: list[tuple[str, str, float]] = []
    n = len(embeddings)

    for i in range(n):
        for j in range(i + 1, n):
            id_a, vec_a = embeddings[i]
            id_b, vec_b = embeddings[j]

            similarity = cosine_similarity_numpy(vec_a, vec_b)
            if similarity >= threshold:
                pairs.append((id_a, id_b, similarity))

    # Sort by similarity descending
    pairs.sort(key=lambda x: x[2], reverse=True)

    return pairs


def cluster_by_similarity(
    embeddings: list[tuple[str, bytes]],
    threshold: float = 0.8,
) -> list[list[str]]:
    """Group embeddings into clusters based on similarity.

    Uses a simple greedy clustering approach: each embedding joins
    the first cluster where it's similar enough to the centroid,
    or starts a new cluster.

    Args:
        embeddings: List of (id, vector_bytes) tuples
        threshold: Similarity threshold for cluster membership

    Returns:
        List of clusters, where each cluster is a list of IDs
    """
    if not embeddings:
        return []

    clusters: list[list[str]] = []
    cluster_vectors: list[list[float]] = []

    for emb_id, emb_vec in embeddings:
        vec = _bytes_to_floats(emb_vec)
        best_cluster = -1
        best_similarity = threshold

        # Find best matching cluster
        for i, centroid in enumerate(cluster_vectors):
            similarity = cosine_similarity(vec, centroid)
            if similarity >= best_similarity:
                best_cluster = i
                best_similarity = similarity

        if best_cluster >= 0:
            # Add to existing cluster
            clusters[best_cluster].append(emb_id)
            # Update centroid (simple average)
            old_centroid = cluster_vectors[best_cluster]
            n = len(clusters[best_cluster])
            new_centroid = [
                (old_centroid[j] * (n - 1) + vec[j]) / n for j in range(len(vec))
            ]
            cluster_vectors[best_cluster] = new_centroid
        else:
            # Start new cluster
            clusters.append([emb_id])
            cluster_vectors.append(vec)

    return clusters
