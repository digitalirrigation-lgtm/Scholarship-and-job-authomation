import streamlit as st
import pandas as pd
import requests
import base64
import io
import re
import json
import time
from datetime import datetime, timedelta
import os
import altair as alt
from bs4 import BeautifulSoup
import openpyxl

# ---------- PAGE CONFIG ----------
st.set_page_config(
    layout="wide", 
    page_title="🎓 AI Scholarship Dashboard", 
    page_icon="🎓",
    initial_sidebar_state="expanded"
)

# ---------- CUSTOM CSS THEME ----------
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        color: #1a1a2e;
    }
    .css-1y4p8pa, .element-container, .stMarkdown {
        background: rgba(255,255,255,0.7) !important;
        backdrop-filter: blur(10px);
        border-radius: 20px !important;
        padding: 20px !important;
        border: 1px solid rgba(255,255,255,0.3) !important;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1) !important;
    }
    .stButton button {
        background: linear-gradient(145deg, #FFD700, #B8860B) !important;
        color: #1a1a2e !important;
        border-radius: 50px !important;
        border: none !important;
        font-weight: bold !important;
        padding: 12px 28px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(184, 134, 11, 0.3) !important;
    }
    h1, h2, h3 { color: #1a1a2e !important; font-weight: 700 !important; }
</style>
""", unsafe_allow_html=True)

# ---------- GITHUB CONFIGURATION ----------
def get_github_config():
    # Make sure to set these in Streamlit Cloud Secrets!
    return {
        "token": st.secrets["github"]["token"],
        "username": "digitalirrigation-lgtm",
        "repo": "Scholarship-and-job-authomation",
        "file_path": "data/opportunities.xlsx",
        "branch": "main"
    }

# ---------- GITHUB STORAGE FUNCTIONS ----------
def load_data_from_github():
    try:
        config = get_github_config()
        url = f"https://api.github.com/repos/{config['username']}/{config['repo']}/contents/{config['file_path']}"
        headers = {"Authorization": f"token {config['token']}"}
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            content = base64.b64decode(data["content"])
            df = pd.read_excel(io.BytesIO(content))
            return df, data["sha"]
        else:
            df = pd.DataFrame(columns=["Id", "Title", "Organization", "Category", "Deadline", "Status", "Link", "Description", "Country", "CreatedAt"])
            return df, None
    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        return pd.DataFrame(), None

def save_data_to_github(df, sha):
    try:
        config = get_github_config()
        content = io.BytesIO()
        df.to_excel(content, index=False, engine='openpyxl')
        encoded = base64.b64encode(content.getvalue()).decode()
        
        url = f"https://api.github.com/repos/{config['username']}/{config['repo']}/contents/{config['file_path']}"
        headers = {"Authorization": f"token {config['token']}"}
        payload = {
            "message": f"Update - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "content": encoded,
            "branch": config['branch'],
            "sha": sha
        }
        response = requests.put(url, headers=headers, json=payload)
        return response.status_code in [200, 201], response.json().get('content', {}).get('sha', sha)
    except Exception as e:
        return False, sha

# ---------- APP LOGIC ----------
def main():
    st.title("🎓 AI Scholarship Dashboard")
    
    if "df" not in st.session_state:
        df, sha = load_data_from_github()
        st.session_state.df = df
        st.session_state.sha = sha

    # Display basic stats
    if not st.session_state.df.empty:
        st.metric("Total Opportunities", len(st.session_state.df))
        st.dataframe(st.session_state.df, use_container_width=True)
    else:
        st.write("No data found in GitHub. Add an entry to begin.")

    # Simple Add Form
    with st.form("add_new"):
        t = st.text_input("Title")
        o = st.text_input("Organization")
        submit = st.form_submit_button("Add Opportunity")
        
        if submit and t and o:
            new_data = {
                "Id": len(st.session_state.df) + 1,
                "Title": t,
                "Organization": o,
                "Category": "Scholarship",
                "Deadline": str(datetime.now().date()),
                "Status": "Not Applied",
                "CreatedAt": str(datetime.now())
            }
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_data])], ignore_index=True)
            success, new_sha = save_data_to_github(st.session_state.df, st.session_state.sha)
            if success:
                st.session_state.sha = new_sha
                st.success("Saved to GitHub!")
                st.rerun()

if __name__ == "__main__":
    main()
