import pandas as pd

def count_type_and_category(input_file):
    df = pd.read_excel(input_file)
    required_columns = ["type", "category_topic"]
    for col in required_columns:
        if col not in df.columns:
            print(f'Kolom "{col}" tidak ditemukan dalam file.')
            return

    print("=== Data Counter ===\n")
    type_counts = df["type"].value_counts()

    for type_value, count in type_counts.items():
        print(f'Total data type "{type_value}" : {count}')

    print()
    category_counts = df["category_topic"].value_counts()

    for category_value, count in category_counts.items():
        print(f'Total data category_topic "{category_value}" : {count}')


if __name__ == "__main__":
    input_file = "DatasetLanguage.xlsx"
    count_type_and_category(input_file)
