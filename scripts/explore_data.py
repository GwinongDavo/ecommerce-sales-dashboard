import pandas as pd

df = pd.read_csv("data/Amazon Sale Report.csv")
print("Shape:", df.shape)
print()
print("Columns:", list(df.columns))
print()
print(df.head())
