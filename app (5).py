# app.py
import streamlit as st
import pandas as pd
import sqlite3
import re
from datetime import datetime, timedelta

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(layout="wide", page_title="Scholarship & Job AI Dashboard", page_icon="🎓")

# ==========================================
# DATABASE (SQLite)
# ==========================================
DB_PATH = "pipeline_vault.db"

def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS Opportunities (
        Id INTEGER PRIMARY KEY AUTOINCREMENT,
        Title TEXT,
        Organization TEXT,
        Category TEXT,
        Deadline TEXT,
        Status TEXT,
        CreatedAt TEXT,
        Saved INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS MasterProfile (
        Id INTEGER PRIMARY KEY AUTOINCREMENT,
        Name TEXT,
        Email TEXT,
        Phone TEXT,
        Location TEXT,
        Education TEXT,
        Experience TEXT,
        Achievements TEXT,
        Skills TEXT,
        Certifications TEXT,
        NarrativeContext TEXT,
        NarrativeSolution TEXT,
        NarrativeCTA TEXT
    )''')
    # Insert default profile if empty
    c.execute("SELECT COUNT(*) FROM MasterProfile")
    if c.fetchone()[0] == 0:
        c.execute("""INSERT INTO MasterProfile
            (Name, Email, Phone, Location, Education, Experience, Achievements, Skills, Certifications,
             NarrativeContext, NarrativeSolution, NarrativeCTA)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (
            "ZEDAGIM TESFAYE TANTU",
            "zedagim100@gmail.com",
            "+251-924-700-390",
            "Jigjiga, Ethiopia",
            "Bachelor of Engineering in Water Resource & Irrigation Engineering (GPA: 3.87/4.00)",
            "Water resource engineering, irrigation systems, satellite data analysis, climate prediction.",
            "Developed Hydro-Agritech prototypes; Digitized FAO-56 Penman-Monteith; Prevented 456+ trafficking cases.",
            "Python, GIS, Remote Sensing, Machine Learning, Data Analysis, Project Management",
            "Certified in GeoAI, Digital Irrigation Systems",
            "Developing regions rely heavily on traditional agricultural systems without enough data arrays.",
            "Deploy spaceborne remote sensing arrays and validated Earth Observation data.",
            "I am ready to discuss my potential alignment with your goals."
        ))
    conn.commit()
    conn.close()

init_db()

# ==========================================
# HELPERS
# ==========================================
def fetch_all():
    conn = get_db()
    df = pd.read_sql("SELECT * FROM Opportunities ORDER BY Id DESC", conn)
    conn.close()
    return df

def fetch_profile():
    conn = get_db()
    df = pd.read_sql("SELECT * FROM MasterProfile LIMIT 1", conn)
    conn.close()
    return df

def add_opportunity(data):
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO Opportunities
        (Title, Organization, Category, Deadline, Status, CreatedAt, Saved)
        VALUES (?,?,?,?,?,?,?)""", (
        data["title"], data["organization"], data["category"],
        data["deadline"].strftime("%Y-%m-%d"), data["status"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 0
    ))
    conn.commit()
    conn.close()

def delete_opportunity(opp_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM Opportunities WHERE Id = ?", (opp_id,))
    conn.commit()
    conn.close()

# ==========================================
# AI ALIGNMENT ENGINE
# ==========================================
def extract_keywords(text):
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    stopwords = {"the","and","for","with","from","into","about","without","etc"}
    return set(w for w in words if w not in stopwords)

def align_profile(profile, description):
    achievements = [a.strip() for a in profile['Achievements'].split(';') if a.strip()]
    skills = [s.strip() for s in profile['Skills'].split(',') if s.strip()]
    desc_tokens = extract_keywords(description or "")
    matched_ach = [ach for ach in achievements if any(tok in ach.lower() for tok in desc_tokens)]
    matched_skills = [sk for sk in skills if any(tok in sk.lower() for tok in desc_tokens)]
    return matched_ach or achievements[:3], matched_skills or skills[:5]

def generate_cv(profile, description):
    matched_ach, matched_skills = align_profile(profile, description)
    return f"""
Name: {profile['Name']}
Email: {profile['Email']}
Phone: {profile['Phone']}
Location: {profile['Location']}

Education:
{profile['Education']}

Experience:
{profile['Experience']}

Achievements (aligned):
{'; '.join(matched_ach)}

Skills (aligned):
{', '.join(matched_skills)}

Certifications:
{profile['Certifications']}
"""

# ==========================================
# MAIN UI
# ==========================================
st.title("🎓 Scholarship & Job AI Dashboard")

df = fetch_all()

if df.empty:
    st.info("No opportunities yet. Add one below.")
else:
    def deadline_color(deadline):
        try:
            days_left = (pd.to_datetime(deadline).date() - datetime.today().date()).days
        except:
            days_left = 999
        if days_left <= 10: return "🔴"
        elif days_left <= 30: return "🟡"
        return "🟢"

    df["deadline_alert"] = df["Deadline"].apply(deadline_color)
    st.dataframe(df[["Id","Title","Organization","Deadline","deadline_alert","Status","Saved"]],
                 use_container_width=True)

    selected_id = st.selectbox("Select Opportunity ID", df["Id"].tolist())
    if selected_id:
        row = df[df["Id"] == selected_id].iloc[0]
        profile_df = fetch_profile()
        if profile_df.empty:
            st.error("MasterProfile table is empty.")
        else:
            profile = profile_df.iloc[0].to_dict()
            description = st.text_area("Paste Job/Scholarship Description Here")
            if st.button("Generate CV"):
                cv = generate_cv(profile, description)
                st.download_button("Download CV", data=cv, file_name="cv.txt")
            if st.button("Delete Opportunity"):
                delete_opportunity(selected_id)
                st.rerun()

with st.expander("➕ Add New Opportunity"):
    with st.form("add"):
        title = st.text_input("Title")
        org = st.text_input("Organization")
        cat = st.selectbox("Category", ["Scholarship","Job"])
        deadline = st.date_input("Deadline", value=datetime.today().date()+timedelta(days=30))
        if st.form_submit_button("Add"):
            if title and org:
                data = {"title": title, "organization": org, "category": cat,
                        "deadline": deadline, "status": "Not Applied"}
                add_opportunity(data)
                st.success("Opportunity added!")
                st.rerun()

with st.expander("👤 Master Profile"):
    st.dataframe(fetch_profile())
