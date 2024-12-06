import pandas as pd
import ast  # For safely parsing JSON-like strings

# Load the DreamClass data
file_path = "output_files/dreamclass_data.csv"
dc_data = pd.read_csv(file_path)

# Drop the unnecessary columns, including 'schooltype'
columns_to_drop = ["schemaName", "zohoLeadId", "zohoContactId", "zohoAccountId", "schooltype"]
dc_data = dc_data.drop(columns=columns_to_drop)

# Parse `dcSubscription` to extract `status` and `dcPlan.name`
def parse_subscription(value):
    try:
        parsed = ast.literal_eval(value)
        return pd.Series({
            "status": parsed.get("status"),
            "plan_name": parsed.get("dcPlan", {}).get("name")  # Optional
        })
    except:
        return pd.Series({"status": None, "plan_name": None})

subscription_parsed = dc_data["dcSubscription"].apply(parse_subscription)
dc_data = pd.concat([dc_data, subscription_parsed], axis=1).drop(columns=["dcSubscription"])

# Convert `createdAt` to dd/mm/yyyy format
dc_data["createdAt"] = pd.to_datetime(dc_data["createdAt"], errors="coerce").dt.strftime("%d/%m/%Y")

# Ensure `id` is a string and `adminLogins` is an integer
dc_data["id"] = dc_data["id"].astype(str)
dc_data["adminLogins"] = pd.to_numeric(dc_data["adminLogins"], errors="coerce").fillna(0).astype(int)

"""
# Save cleaned data
output_file = "output_files/cleaned_dreamclass_data.csv"
dc_data.to_csv(output_file, index=False)
print(f"Cleaned data saved to {output_file}")
"""
