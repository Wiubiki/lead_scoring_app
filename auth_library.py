import bcrypt
import streamlit as st

# Load hashed credentials from secrets.toml
credentials = st.secrets["credentials"]

# Admin usernames
ADMIN_USERS = {"admin"}   # <-- add more usernames if needed


def authenticate(username: str, password: str) -> bool:
    """
    Check username/password against stored bcrypt hashes.
    """
    if username in credentials:
        stored_hash = credentials[username]
        if bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
            return True
    return False


def require_auth():
    """
    Unified authentication gate.
    Shows styled login form until authenticated.
    Sets session state:
       - authenticated: bool
       - username: string
       - is_admin: bool
    """

    # Already logged in? Skip form entirely
    if st.session_state.get("authenticated"):
        return

    # ------------------------------------------
    # Styled login header
    # ------------------------------------------
    st.title("DreamClass Lead Scoring App")
    st.subheader("Please log in to continue")

    # ------------------------------------------
    # 🎨 Styled Login Box (your original styling hook)
    # ------------------------------------------
    login_container = st.container(key="login-box")  # <--- styling key retained

    with login_container:
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", key="login-username")
            password = st.text_input("Password", type="password", key="login-password")
            submitted = st.form_submit_button("Log In", type="primary")

    # ------------------------------------------
    # Authentication check
    # ------------------------------------------
    if submitted:
        try:
            authed = authenticate(username, password)
        except Exception as e:
            st.error(f"Authentication error: {e}")
            st.stop()

        if authed:
            # Write session flags
            st.session_state["authenticated"] = True
            st.session_state["username"] = username
            st.session_state["is_admin"] = username in ADMIN_USERS

            st.success(f"Logged in as **{username}**")
            st.rerun()
        else:
            st.error("Invalid credentials.")
            # stay on page
            return

    # ------------------------------------------
    # Halt execution until login completes
    # ------------------------------------------
    st.stop()
