import pandas as pd

def remove_duplicate_rows(input_file, output_file):
    
    df = pd.read_excel(input_file)
    df_cleaned = df.drop_duplicates(subset=[df.columns[0]], keep='first')
    df_cleaned.to_excel(output_file, index=False)

    print("Duplicate rows removed successfully.")
    print(f"Input Row total     : {len(df)}")
    print(f"Output Row total    : {len(df_cleaned)}")


if __name__ == "__main__":
    input_file = "DatasetLanguage.xlsx"      
    output_file = "output.xlsx"  

    remove_duplicate_rows(input_file, output_file)
