
import pandas as pd
from pathlib import Path

DATA_DIR = Path("app/ml/data")


def canonical_pair(row):
    name_a = str(row["name_1"]).strip().casefold()
    name_b = str(row["name_2"]).strip().casefold()
    return tuple(sorted((name_a, name_b)))


def main():
    train_path = DATA_DIR / "company_pairs_train_clean.csv"
    validation_path = DATA_DIR / "company_pairs_validation_clean.csv"

    train = pd.read_csv(train_path)
    validation = pd.read_csv(validation_path)

    train_pairs = set(train.apply(canonical_pair, axis=1))
    validation["pair_key"] = validation.apply(canonical_pair, axis=1)

    overlap_mask = validation["pair_key"].isin(train_pairs)
    overlap_count = int(overlap_mask.sum())

    validation = validation.loc[~overlap_mask].drop(
        columns=["pair_key"]
    )

    output_path = DATA_DIR / "company_pairs_validation_no_overlap.csv"
    validation.to_csv(output_path, index=False)

    print("Overlapping validation rows removed:", overlap_count)
    print("Remaining validation rows:", len(validation))
    print("Validation label distribution:")
    print(validation["label"].value_counts().sort_index())
    print("Saved:", output_path)


if __name__ == "__main__":
    main()
