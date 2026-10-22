import joblib
from pathlib import Path
import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer

# Path to the serialized artefact created by the training script
MODEL_FILE = Path(__file__).parent / "models" / "tfidf_logreg.pkl"

# Load once at import time
_loaded = joblib.load(MODEL_FILE)
_vectorizer: TfidfVectorizer = _loaded["vectorizer"]
_model = _loaded["model"]

def _build_features(name_a_series, name_b_series):
    """Construct the same feature matrix used during training.
    Parameters
    ----------
    name_a_series, name_b_series : array‑like of str
        The two columns of names to compare.
    Returns
    -------
    scipy.sparse.csr_matrix
        Sparse matrix with shape (n_samples, 2 * n_features).
    """
    vec_a = _vectorizer.transform(name_a_series)
    vec_b = _vectorizer.transform(name_b_series)
    return hstack([
        abs(vec_a - vec_b),
        vec_a.multiply(vec_b),
    ], format="csr", dtype=np.float32)

def compute_entity_similarity(name_a: str | None, name_b: str | None) -> float | None:
    """Return the probability that *name_a* and *name_b* refer to the same entity.
    If either name is missing or empty, ``None`` is returned so the engine can fall back
    to rule‑based scoring.

    The function first performs a fast direct comparison (case‑insensitive, trimmed).
    If the names match exactly, a probability of ``1.0`` is returned without invoking the
    machine‑learning model, avoiding unnecessary computation.  If they differ, the
    feature vector is built and the trained ``LogisticRegression`` model is used to
    estimate the match probability.
    """
    if not name_a or not name_b:
        return None
    # Fast direct comparison – normalize whitespace and case
    a_norm = name_a.strip().lower()
    b_norm = name_b.strip().lower()
    if a_norm == b_norm:
        return 1.0
    # Build a one‑row feature matrix – the training script expects two columns
    features = _build_features([name_a], [name_b])
    # LogisticRegression.predict_proba returns [[prob_0, prob_1]]; column 1 is the match probability
    prob = _model.predict_proba(features)[0, 1]
    return float(prob)