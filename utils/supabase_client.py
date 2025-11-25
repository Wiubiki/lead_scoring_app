import streamlit as st
from supabase import create_client, Client

SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_SERVICE_KEY = st.secrets["supabase"]["service_key"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
