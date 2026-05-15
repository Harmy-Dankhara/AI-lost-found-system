"""
image_matcher.py — Perceptual image similarity for AI Lost & Found
=================================================================
Uses perceptual hashing (pHash) via the imagehash library.

pHash works by:
  1. Resizing image to a small fixed size (32×32)
  2. Applying a DCT (Discrete Cosine Transform)
  3. Producing a 64-bit fingerprint
  4. Comparing fingerprints via Hamming distance

Similarity score: 0 (completely different) → 100 (identical)
"""

import os
from functools import lru_cache

IMAGE_MATCH_AVAILABLE = False

try:
    from PIL import Image
    import imagehash
    IMAGE_MATCH_AVAILABLE = True
except ImportError:
    pass   # Graceful degradation — text matching still works


def _load_hash(image_path: str):
    """
    Load an image from `image_path` and return its perceptual hash.
    Returns None if the file doesn't exist or cannot be opened.
    """
    if not IMAGE_MATCH_AVAILABLE:
        return None

    # Normalize path — strip leading slash if present
    path = image_path.lstrip("/")
    if not os.path.isfile(path):
        return None

    try:
        with Image.open(path) as img:
            img = img.convert("RGB").resize((128, 128), Image.LANCZOS)
            return imagehash.phash(img, hash_size=8)   # 64-bit hash
    except Exception:
        return None


def image_similarity(path_a: str, path_b: str) -> float:
    """
    Compare two image files and return a similarity score from 0 to 100.

    Args:
        path_a: Filesystem path to image A (lost item)
        path_b: Filesystem path to image B (found item)

    Returns:
        float: 0.0 (no similarity) – 100.0 (identical images)
               Returns -1.0 if either image cannot be loaded (caller ignores image signal).
    """
    if not IMAGE_MATCH_AVAILABLE:
        return -1.0

    hash_a = _load_hash(path_a)
    hash_b = _load_hash(path_b)

    if hash_a is None or hash_b is None:
        return -1.0   # signal: no image available

    # Hamming distance: 0 = identical, 64 = completely different
    hamming = hash_a - hash_b
    score = max(0.0, round((1 - hamming / 64) * 100, 1))
    return score


def find_visually_similar(query_path: str, candidate_items: list,
                           threshold: float = 55.0) -> list:
    """
    Reverse image search: given a query image path, rank all candidate
    items by visual similarity and return those above `threshold`.

    Args:
        query_path:       Path to the query image file
        candidate_items:  List of item dicts (must have 'image' key)
        threshold:        Minimum score (0–100) to include in results

    Returns:
        List of (item_dict, score) tuples, sorted highest-score-first.
    """
    results = []
    for item in candidate_items:
        item_img = item.get("image")
        if not item_img:
            continue
        score = image_similarity(query_path, item_img)
        if score >= threshold:
            results.append((item, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results
