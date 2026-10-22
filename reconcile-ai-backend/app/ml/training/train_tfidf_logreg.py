import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from scipy.sparse import hstack
import time

DATA_DIR = Path("app/ml/data")
TRAIN_FILE = DATA_DIR / "company_pairs_train_clean.csv"
VALIDATION_FILE = DATA_DIR / "company_pairs_validation_no_overlap.csv"
MODEL_PATH = Path(__file__).parent.parent / "models" / "tfidf_logreg.pkl"

SIMILARITY_THRESHOLD = 0.80  # used later by engine for decision

def load_data():
    train = pd.read_csv(TRAIN_FILE)
    validation = pd.read_csv(VALIDATION_FILE)
    required = {"name_1", "name_2", "label"}
    for df, fname in [(train, TRAIN_FILE), (validation, VALIDATION_FILE)]:
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"{fname} missing columns: {missing}")
        df.dropna(subset=["name_1", "name_2", "label"], inplace=True)
        for col in ["name_1", "name_2"]:
            df[col] = df[col].astype(str).str.strip()
        df = df[(df["name_1"].ne("") & df["name_2"].ne(""))].copy()
        df["label"] = df["label"].astype(int)
        if fname == TRAIN_FILE:
            train = df
        else:
            validation = df
    return train, validation

def train_and_save():
    train, validation = load_data()

    # TF‑IDF vectorizer on character n‑grams (same as benchmark)
    vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(2, 5),
        lowercase=True,
        sublinear_tf=True,
        min_df=2,
        max_features=50000,
        dtype=np.float32,
    )
    vectorizer.fit(pd.concat([train["name_1"], train["name_2"]]))

    # Build sparse feature matrix (absolute diff + element‑wise product)
    def build_features(a_series, b_series):
        vec_a = vectorizer.transform(a_series)
        vec_b = vectorizer.transform(b_series)
        return hstack([
            abs(vec_a - vec_b),
            vec_a.multiply(vec_b),
        ], format="csr", dtype=np.float32)

    train_features = build_features(train["name_1"], train["name_2"])
    model = LogisticRegression(
        solver="liblinear",
        max_iter=500,
        class_weight="balanced",
        random_state=42,
    )
    start = time.perf_counter()
    model.fit(train_features, train["label"])
    train_time = time.perf_counter() - start
    print(f"Training completed in {train_time:.2f}s")

    # Save both vectorizer and model together
    joblib.dump({"vectorizer": vectorizer, "model": model}, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")

    # Optional quick validation metric
    val_features = build_features(validation["name_1"], validation["name_2"])
    preds = model.predict(val_features)
    from sklearn.metrics import f1_score
    print("Validation F1:", f1_score(validation["label"], preds))

if __name__ == "__main__":
    train_and_save()
