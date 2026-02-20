import pandas as pd

def generate_unique_words(input_file, output_file):
    df = pd.read_excel(input_file)

    first_column = df.iloc[:, 0]

    all_words = []
    seen_words = set()

    for cell in first_column.dropna():
        sentence = str(cell)
        words = sentence.split()

        for word in words:
            if word not in seen_words:
                all_words.append(word)
                seen_words.add(word)

    all_words_sorted = sorted(all_words)

    output_df = pd.DataFrame(all_words_sorted, columns=["word"])

    output_df.to_excel(output_file, index=False)

    print("Process completed successfully.")
    print(f"Word generated : {len(all_words_sorted)}")


if __name__ == "__main__":
    input_file = "DatasetLanguage.xlsx"
    output_file = "output.xlsx"

    generate_unique_words(input_file, output_file)
