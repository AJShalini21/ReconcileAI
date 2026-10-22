
import pandas as pd
from pathlib import Path

DATA_DIR = Path("app/ml/data")


def audit_dataset(filename: str) -> None:
    path = DATA_DIR / filename
    df = pd.read_csv(path)

    # Basic integrity checks
    print(f"\n=== {filename} ===")
    print("Rows:", len(df))
    print("Missing values:\n", df.isna().sum())
    print("Duplicate pairs:", df.duplicated(
        subset=["name_1", "name_2", "label"]
    ).sum())

    # Normalize only for this audit; preserve original columns
    a = df["name_1"].str.strip().str.casefold()
    b = df["name_2"].str.strip().str.casefold()

    df["exact_match"] = a.eq(b)
    df["label"] = df["label"].astype(int)

    print("\nLabel distribution:")
    print(df["label"].value_counts().sort_index())

    print("\nExact string match rate by label:")
    print(df.groupby("label")["exact_match"].mean())

    print("\nLabel distribution for exact and different names:")
    print(pd.crosstab(
        df["exact_match"],
        df["label"],
        normalize="index"
    ).round(3))

    print("\nPositive examples with different names:")
    print(
        df[(df["label"] == 1) & (~df["exact_match"])]
        [["name_1", "name_2", "label"]]
        .head(15)
        .to_string(index=False)
    )


if __name__ == "__main__":
    audit_dataset("company_pairs_train.csv")
    audit_dataset("company_pairs_validation.csv")
