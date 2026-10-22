
from datasets import load_dataset
import pandas as pd
from pathlib import Path

DATASET_NAME = "jayshah5696/entity-resolution-ce-pairs-v2"
OUTPUT_DIR = Path("app/ml/data")


def main():
    print("Loading dataset...")
    dataset = load_dataset(DATASET_NAME)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for split_name, split_data in dataset.items():
        print(f"\nProcessing split: {split_name}")

        rows = []

        for row in split_data:
            record_a = row.get("record_a") or {}
            record_b = row.get("record_b") or {}

            name_1 = record_a.get("company")
            name_2 = record_b.get("company")
            label = row.get("label")

            if not isinstance(name_1, str) or not isinstance(name_2, str):
                continue

            name_1 = name_1.strip()
            name_2 = name_2.strip()

            if not name_1 or not name_2 or label is None:
                continue

            rows.append({
                "name_1": name_1,
                "name_2": name_2,
                "label": int(label),
            })

        df = pd.DataFrame(rows)

        if df.empty:
            print("No valid company-name pairs found.")
            continue

        output_file = OUTPUT_DIR / f"company_pairs_{split_name}.csv"
        df.to_csv(output_file, index=False)

        print("Total company-name pairs:", len(df))
        print("\nLabel distribution:")
        print(df["label"].value_counts().sort_index())
        print("\nSample pairs:")
        print(df.head(10).to_string(index=False))
        print(f"\nSaved to: {output_file}")

        # Exact-name agreement by ground-truth label
        exact_agreement = (
            df["name_1"].str.casefold()
            == df["name_2"].str.casefold()
        )

        print("\nExact-name agreement by label:")
        print(
            df.assign(exact_name=exact_agreement)
            .groupby("label")["exact_name"]
            .mean()
        )

    print("\nDataset preparation complete.")


if __name__ == "__main__":
    main()
