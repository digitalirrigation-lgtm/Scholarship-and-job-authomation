# app.py
import streamlit as st
import pandas as pd
import sqlite3
import re
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="🎓 Scholarship & Job AI Dashboard", page_icon="🎓")

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
        Saved INTEGER DEFAULT 0,
        UserDescription TEXT,
        Link TEXT
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
    conn.commit()
    conn.close()

init_db()

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
        (Title, Organization, Category, Deadline, Status, CreatedAt, Saved, UserDescription, Link)
        VALUES (?,?,?,?,?,?,?,?,?)""", (
        data["title"], data["organization"], data["category"],
        data["deadline"].strftime("%Y-%m-%d"), data["status"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 0,
        data["description"], data["link"]
    ))
    conn.commit()
    conn.close()

def delete_opportunity(opp_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM Opportunities WHERE Id = ?", (opp_id,))
    conn.commit()
    conn.close()

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

def generate_cover_letter(profile, opportunity, description):
    matched_ach, matched_skills = align_profile(profile, description)
    return f"""
Dear {opportunity['Organization']},

I am applying for {opportunity['Title']} ({opportunity['Category']}).

Your requirements emphasize: {description[:300]}...

I bring aligned achievements:
- {'\n- '.join(matched_ach)}

My technical skills in {', '.join(matched_skills)} have been honed through real-world projects.

{profile['NarrativeContext']}
{profile['NarrativeSolution']}

Sincerely,
{profile['Name']}
"""

def generate_motivation_letter(profile, opportunity, description):
    matched_ach, matched_skills = align_profile(profile, description)
    return f"""
Motivation Letter for {opportunity['Title']}:

Aligned Achievements:
{'; '.join(matched_ach)}

Aligned Skills:
{', '.join(matched_skills)}

{profile['NarrativeContext']}
{profile['NarrativeSolution']}
{profile['NarrativeCTA']}
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
            description = st.text_area("Paste Job/Scholarship Description Here", value=row["UserDescription"] or "")
            if st.button("⚡ Generate CV + Cover Letter + Motivation Letter"):
                cv = generate_cv(profile, description)
                cover = generate_cover_letter(profile, row, description)
                mot = generate_motivation_letter(profile, row, description)
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.text_area("CV Preview", cv, height=200)
                    st.download_button("⬇️ Download CV", data=cv, file_name="cv.txt")
                with col2:
                    st.text_area("Cover Letter Preview", cover, height=200)
                    st.download_button("⬇️ Download Cover Letter", data=cover, file_name="cover_letter.txt")
                with col3:
                    st.text_area("Motivation Letter Preview", mot, height=200)
                    st.download_button("⬇️ Download Motivation Letter", data=mot, file_name="motivation_letter.txt")
            if st.button("🗑️ Delete Opportunity"):
                delete_opportunity(selected_id)
                st.rerun()

with st.expander("➕ Add New Opportunity"):
    with st.form("add"):
        title = st.text_input("Title")
        org = st.text_input("Organization")
        cat = st.selectbox("Category", ["Scholarship","Job"])
        deadline = st.date_input("Deadline", value=datetime.today().date()+timedelta(days=30))
        link = st.text_input("Link (optional)")
        description_input = st.text_area("Description (optional)", height=100)
        if st.form_submit_button("Add Opportunity"):
            if title and org:
                data = {
                    "title": title,
                    "organization": org,
                    "category": cat,
                    "deadline": deadline,
                    "status": "Not Applied",
                    "description": description_input,
                    "link": link
                }
                add_opportunity(data)
                st.success("Opportunity added!")
                st.rerun()
            else:
                st.warning("Title and Organization are required.")
