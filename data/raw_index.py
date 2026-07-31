import pandas as pd

df = pd.read_parquet("data/images/raw_index.parquet")
row = df[df["id"] == "wm811k_929"]
print(row.T)