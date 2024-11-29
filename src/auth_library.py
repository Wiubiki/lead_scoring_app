import bcrypt
import streamlit as st

credentials = {
    "admin": b"$2b$12$stKOH.ZarvtSMIhzd9miVuYExQYmrzqyP7TB0y3BRbkihAwLXuC.y",  # "bouboulis"
    "lids": b"$2b$12$n5cdt2fT6.Az6k.6r4UaBef81NCPEwf9hp6KNFHvHv.fEutchfapK",
    "letrim": b"$2b$12$i/9kpIpakVxJN9v5EpJcdejG9DdWaQid7IG5gzODPRCN5G47qk8Z2",
    "guest": b"$2b$12$/Opf7JIp7qvgI0SNcVVA/uTFIxMRDJpH5sJ/uxi/k6B92XgN19u.e"  # User_anonym#$
}

def authenticate(username, password):
    """
    Authenticate user against the credentials dictionary.
    :param username: str
    :param password: str
    :return: bool
    """
    if username in credentials:
        stored_hash = credentials[username]
        if bcrypt.checkpw(password.encode("utf-8"), stored_hash):
            return True
    return False
