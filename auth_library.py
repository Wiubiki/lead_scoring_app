import bcrypt
import streamlit as st

# Load hashed credentials from Streamlit secrets
credentials = st.secrets["credentials"]

def authenticate(username, password):
    if username in credentials:
        stored_hash = credentials[username]
        if bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
            return True
    return False
