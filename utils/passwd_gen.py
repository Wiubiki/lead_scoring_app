"""
Utility script for generating bcrypt password hashes.

Safe to run locally. Does not store or expose any sensitive data.
"""

import bcrypt

# Prompt the user for a plain-text password
plain_password = input("Enter the plain-text password to hash: ")

# Generate a hash
hashed_password = bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt())

# Print the hashed password
print("\nHashed Password:")
print(hashed_password.decode('utf-8'))  # Decode to a string for easy copying
