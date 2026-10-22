import pandas as pd
from pathlib import Path

DATA_DIR = Path("app/ml/data")


def load_and_clean(filename):
    path = DATA_DIR / filename
    df = pd.read_csv(path)

    original_count = len(df)

    # Remove rows with missing or blank names
    df = df.dropna(subset=["name_1", "name_2", "label"]).copy()

    for col in ["name_1", "name_2"]:
        df[col] = df[col].astype(str).str.strip()

    df = df[
        df["name_1"].ne("") & df["name_2"].ne("")
    ].copy()

    df["label"] = df["label"].astype(int)

    # Create order-independent pair keys for duplicate checks
    a = df["name_1"].str.casefold()
    b = df["name_2"].str.casefold()

    df["pair_key"] = [
        tuple(sorted((x, y))) for x, y in zip(a, b)
    ]

    # Find pairs assigned contradictory labels
    label_counts = df.groupby("pair_key")["label"].nunique()
    conflicting_keys = label_counts[label_counts > 1].index

    print(f"\n{filename}")
    print("Original rows:", original_count)
    print("Rows after removing missing/blank names:", len(df))
    print("Pairs with conflicting labels:", len(conflicting_keys))

    if len(conflicting_keys):
        print("Inspect these pairs before deduplicating.")

    # Deduplicate only pairs with a single consistent label
    df = df[~df["pair_key"].isin(conflicting_keys)].copy()
    df = df.drop_duplicates(subset=["pair_key"], keep="first")

    df = df.drop(columns="pair_key")

    output_path = DATA_DIR / filename.replace(
        ".csv", "_clean.csv"
    )
    df.to_csv(output_path, index=False)

    print("Clean rows:", len(df))
    print("Saved:", output_path)
    print("Labels:\n", df["label"].value_counts().sort_index())

    return df


def main():
    train = load_and_clean("company_pairs_train.csv")
    validation = load_and_clean("company_pairs_validation.csv")

    def canonical_pairs(df):
        a = df["name_1"].str.casefold()
        b = df["name_2"].str.casefold()
        return {
            tuple(sorted(pair))
            for pair in zip(a, b)
        }

    overlap = canonical_pairs(train) & canonical_pairs(validation)

    print("\nTrain/validation pair overlap:", len(overlap))
    print("Cleaning complete.")


if __name__ == "__main__":
    main()
