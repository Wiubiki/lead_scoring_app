import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

df = pd.read_csv("summary_gaps_template.csv")


for _, row in df.iterrows():
    start = row["start"]
    end = row["end"]
    
    output_path = f"{start}__{end}.parquet"
    
    summary_df = pd.DataFrame([{
        "period_start": start,
        "period_end": end,
        "class_1_count": int(row["c1"]),
        "class_2_count": int(row["c2"]),
        "class_3_count": int(row["c3"]),
        "class_4_count": int(row["c4"]),
        "total_leads": int(row["total"]),
        "data_type": "summary",
    }])

    table = pa.Table.from_pandas(summary_df)
    pq.write_table(table, output_path)

    print("Created:", output_path)

print("All summary parquet files generated successfully.")
