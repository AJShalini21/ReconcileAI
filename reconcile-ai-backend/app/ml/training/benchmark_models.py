
import time
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)
from sklearn.pipeline import Pipeline
from scipy.sparse import hstack

DATA_DIR = Path("app/ml/data")

TRAIN_FILE = DATA_DIR / "company_pairs_train_clean.csv"
VALIDATION_FILE = DATA_DIR / "company_pairs_validation_no_overlap.csv"

RESULTS_FILE = DATA_DIR / "benchmark_results.csv"

# Initial decision threshold for similarity-based approaches.
# This will be tuned more carefully after the baseline experiment.
SIMILARITY_THRESHOLD = 0.80


def load_data():
    """Load and validate the prepared train and validation datasets."""
    train = pd.read_csv(TRAIN_FILE)
    validation = pd.read_csv(VALIDATION_FILE)

    required_columns = {"name_1", "name_2", "label"}

    for filename, df in [
        (TRAIN_FILE, train),
        (VALIDATION_FILE, validation),
    ]:
        missing_columns = required_columns - set(df.columns)

        if missing_columns:
            raise ValueError(
                f"{filename} is missing columns: {missing_columns}"
            )

        df.dropna(
            subset=["name_1", "name_2", "label"],
            inplace=True,
        )

        for column in ["name_1", "name_2"]:
            df[column] = df[column].astype(str).str.strip()

        df = df[
            df["name_1"].ne("") & df["name_2"].ne("")
        ].copy()

        df["label"] = df["label"].astype(int)

        if not df["label"].isin([0, 1]).all():
            raise ValueError(
                f"{filename} contains labels other than 0 and 1."
            )

        if filename == TRAIN_FILE:
            train = df
        else:
            validation = df

    print(f"Training rows: {len(train)}")
    print(f"Validation rows: {len(validation)}")
    print("\nValidation label distribution:")
    print(validation["label"].value_counts().sort_index())

    return train, validation


def evaluate_predictions(name, y_true, predictions, elapsed_seconds):
    """Calculate classification metrics for one approach."""
    return {
        "model": name,
        "accuracy": accuracy_score(y_true, predictions),
        "precision": precision_score(
            y_true, predictions, zero_division=0
        ),
        "recall": recall_score(
            y_true, predictions, zero_division=0
        ),
        "f1_score": f1_score(
            y_true, predictions, zero_division=0
        ),
        "inference_time_seconds": elapsed_seconds,
        "validation_rows_per_second": (
            len(y_true) / elapsed_seconds
            if elapsed_seconds > 0
            else None
        ),
    }



def benchmark_tfidf(train, validation):
    """Memory-efficient TF-IDF + Logistic Regression baseline."""
    print("\n[1/3] Training TF-IDF + Logistic Regression...")

    train_a = train["name_1"].tolist()
    train_b = train["name_2"].tolist()
    validation_a = validation["name_1"].tolist()
    validation_b = validation["name_2"].tolist()

    # Fit vocabulary on training names only.
    vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(2, 5),
        lowercase=True,
        sublinear_tf=True,
        min_df=2,
        max_features=50000,
        dtype=np.float32,
    )

    vectorizer.fit(train_a + train_b)
    print("TF-IDF vocabulary size:", len(vectorizer.vocabulary_))

    print("Building sparse training features...")
    train_vec_a = vectorizer.transform(train_a)
    train_vec_b = vectorizer.transform(train_b)

    train_features = hstack(
        [
            abs(train_vec_a - train_vec_b),
            train_vec_a.multiply(train_vec_b),
        ],
        format="csr",
        dtype=np.float32,
    )

    print(
        "Training feature matrix:",
        train_features.shape,
        "| non-zero values:",
        train_features.nnz,
    )

    model = LogisticRegression(
        solver="liblinear",
        max_iter=500,
        class_weight="balanced",
        random_state=42,
    )

    print("Fitting Logistic Regression...")
    model.fit(train_features, train["label"])

    # Release training features before creating validation features.
    del train_features, train_vec_a, train_vec_b

    print("Building sparse validation features...")
    validation_vec_a = vectorizer.transform(validation_a)
    validation_vec_b = vectorizer.transform(validation_b)

    validation_features = hstack(
        [
            abs(validation_vec_a - validation_vec_b),
            validation_vec_a.multiply(validation_vec_b),
        ],
        format="csr",
        dtype=np.float32,
    )

    print("Predicting validation labels...")
    start = time.perf_counter()
    predictions = model.predict(validation_features)
    elapsed = time.perf_counter() - start

    result = evaluate_predictions(
        "TF-IDF + Logistic Regression",
        validation["label"],
        predictions,
        elapsed,
    )

    print("TF-IDF benchmark completed.")
    return result


def benchmark_rapidfuzz(validation):
    """Model 2: RapidFuzz string similarity baseline."""
    print("\n[2/3] Evaluating RapidFuzz...")

    start = time.perf_counter()

    scores = [
        fuzz.ratio(a, b) / 100.0
        for a, b in zip(
            validation["name_1"],
            validation["name_2"],
        )
    ]

    predictions = [
        int(score >= SIMILARITY_THRESHOLD)
        for score in scores
    ]

    elapsed = time.perf_counter() - start

    return evaluate_predictions(
        f"RapidFuzz (threshold={SIMILARITY_THRESHOLD})",
        validation["label"],
        predictions,
        elapsed,
    )


def benchmark_sentence_transformer(validation):
    """Model 3: Sentence Transformer embeddings + cosine similarity."""
    print("\n[3/3] Evaluating Sentence Transformer...")

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")

    names_a = validation["name_1"].tolist()
    names_b = validation["name_2"].tolist()

    # Encode each distinct name once to avoid duplicate work.
    unique_names = list(dict.fromkeys(names_a + names_b))

    start = time.perf_counter()

    embeddings = model.encode(
        unique_names,
        normalize_embeddings=True,
        show_progress_bar=True,
        batch_size=64,
    )

    embedding_by_name = dict(zip(unique_names, embeddings))

    scores = [
        float(np.dot(embedding_by_name[a], embedding_by_name[b]))
        for a, b in zip(names_a, names_b)
    ]

    predictions = [
        int(score >= SIMILARITY_THRESHOLD)
        for score in scores
    ]

    elapsed = time.perf_counter() - start

    return evaluate_predictions(
        f"Sentence Transformer (threshold={SIMILARITY_THRESHOLD})",
        validation["label"],
        predictions,
        elapsed,
    )


def main():
    train, validation = load_data()
    results = []

    results.append(benchmark_tfidf(train, validation))
    results.append(benchmark_rapidfuzz(validation))

    try:
        results.append(benchmark_sentence_transformer(validation))
    except Exception as exc:
        print("\nSentence Transformer benchmark failed.")
        print(f"Reason: {exc}")
        print(
            "You can still compare the first two approaches. "
            "Check package installation or model download before retrying."
        )

    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values(
        by="f1_score",
        ascending=False,
    )

    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(RESULTS_FILE, index=False)

    print("\n=== Benchmark Results ===")
    print(
        results_df.round(4).to_string(index=False)
    )
    print(f"\nResults saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
