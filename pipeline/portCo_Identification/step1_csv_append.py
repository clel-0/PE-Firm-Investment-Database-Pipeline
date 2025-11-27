import pandas as pd
import csv
import os 

def append_to_csv(file_path: str, data: list[dict]) -> None:
    
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
    else:
        df = pd.DataFrame()

    new_row = pd.DataFrame(data)
    combined_df = pd.concat([df, new_row], ignore_index=True)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    combined_df.to_csv(file_path, index=False)
    print(f"Appended {len(data)} rows to {file_path}.")

