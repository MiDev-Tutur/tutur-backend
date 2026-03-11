import pandas as pd

# nama file excel
file_path = "DatasetLanguage.xlsx"

# baca file excel
df = pd.read_excel(file_path)

print("Total baris:", len(df))
print("Total kolom:", len(df.columns))
print("=====================================")

missing_found = False

# iterasi setiap baris
for index, row in df.iterrows():
    
    # iterasi setiap kolom
    for col in df.columns:
        
        value = row[col]
        
        # cek jika NaN atau kosong
        if pd.isna(value) or str(value).strip() == "":
            
            missing_found = True
            
            print("Data kosong ditemukan:")
            print(f"Baris Excel  : {index + 2}")  # +2 karena header excel
            print(f"Kolom        : {col}")
            print(f"Kolom Ke     : {df.columns.get_loc(col)+1}")
            print("-------------------------------------")

if not missing_found:
    print("Tidak ada data kosong pada dataset")

print("=====================================")

# ringkasan jumlah NaN per kolom
print("\nRingkasan jumlah data kosong per kolom:\n")
print(df.isna().sum())