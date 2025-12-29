import pandas as pd

# Path to the input text file containing the addresses
input_file = "nomination-address.txt"  # updated file name

# List to hold the parsed addresses
addresses = []
current_address_lines = []

# Read the file and group lines until a phone number line is found.
with open(input_file, "r", encoding="utf-8") as file:
    for line in file:
        stripped_line = line.strip()
        # Skip empty lines
        if not stripped_line:
            continue
        current_address_lines.append(stripped_line)
        # Check if the line starts with "ph:" (case-insensitive)
        if stripped_line.lower().startswith("ph:"):
            # Join collected lines for one complete address
            address = "\n".join(current_address_lines)
            addresses.append(address)
            current_address_lines = []  # Reset for the next address

# In case there are leftover lines that did not end with a phone number line
if current_address_lines:
    addresses.append("\n".join(current_address_lines))

# Prepare the data for Excel: pair addresses side by side (two columns per row)
rows = []
for i in range(0, len(addresses), 2):
    first_address = addresses[i]
    second_address = addresses[i+1] if i+1 < len(addresses) else ""
    rows.append([first_address, second_address])

# Create a DataFrame with two columns
df = pd.DataFrame(rows, columns=["Address 1", "Address 2"])

# Write the DataFrame to an Excel file
output_file = "addresses.xlsx"
df.to_excel(output_file, index=False)

print(f"Excel file '{output_file}' created successfully!")
