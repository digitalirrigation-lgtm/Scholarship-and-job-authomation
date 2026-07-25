import streamlit as st
import pandas as pd
import requests
import base64
import io
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import openpyxl  # FIXED: Removed the ==3.1.2

# ---------- PAGE CONFIG ----------
st.set_page_config(layout="wide", page_title="AI Scholarship Dashboard")

# ---------- GITHUB CONFIG ----------
def get_github_config():
    # Ensure you have set these in "Secrets" on Streamlit Cloud!
    return {
        "token": st.secrets["github"]["token"],
        "username": "digitalirrigation-lgtm",
        "repo": "Scholarship-and-job-authomation",
        "file_path": "data/opportunities.xlsx",
        "branch": "main"
    }

# ---------- LOAD DATA ----------
def load_data():
    try:
        config = get_github_config()
        url = f"https://api.github.com/repos/{config['username']}/{config['repo']}/contents/{config['file_path']}"
        headers = {"Authorization": f"token {config['token']}"}
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            content = base64.b64decode(res.json()["content"])
            return pd.read_excel(io.BytesIO(content)), res.json()["sha"]
    except:
        pass
    return pd.DataFrame(columns=["Id", "Title", "Organization", "Status"]), None

# ---------- UI ----------
st.title("🎓 Scholarship & Job Tracker")

if "df" not in st.session_state:
    df, sha = load_data()
    st.session_state.df = df
    st.session_state.sha = sha

st.write("### Current Opportunities")
if not st.session_state.df.empty:
    st.dataframe(st.session_state.df, use_container_width=True)
else:
    st.info("No data found. Add your first opportunity below.")

with st.form("add_form"):
    t = st.text_input("Title")
    o = st.text_input("Organization")
    if st.form_submit_button("Add"):
        new_row = pd.DataFrame([{"Id": len(st.session_state.df)+1, "Title": t, "Organization": o, "Status": "Pending"}])
        st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
        st.success(f"Added {t}! (Refresh to see update)")
