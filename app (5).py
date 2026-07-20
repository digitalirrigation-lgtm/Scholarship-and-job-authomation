# ============================================================
# FINAL AI-POWERED SCHOLARSHIP & JOB APPLICATION DASHBOARD
# ============================================================
import streamlit as st
import pandas as pd
import sqlite3
import re
from datetime import datetime, timedelta
import os
import plotly.express as px
import plotly.graph_objects as go

# ---------- Local AI (transformers) ----------
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

# ---------- Configuration ----------
USE_LOCAL_AI = True          # Set False to disable AI and use templates
DB_PATH = "pipeline_vault.db"
MODEL_NAME = "microsoft/phi-2"  # ~2.7GB, runs on CPU

# ---------- Database with automatic schema migration ----------
def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def ensure_table_schema():
    """Add any missing columns to Opportunities without dropping data."""
    conn = get_db()
    c = conn.cursor()
    c.execute("PRAGMA table_info(Opportunities)")
    existing = [col[1] for col in c.fetchall()]
    needed = {
        "GeneratedCV": "TEXT",
        "GeneratedCL": "TEXT",
        "GeneratedML": "TEXT",
        "AppliedDate": "TEXT"
    }
    for col, typ in needed.items():
        if col not in existing:
            c.execute(f"ALTER TABLE Opportunities ADD COLUMN {col} {typ}")
    conn.commit()
    conn.close()

def reset_db():
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
        Link TEXT,
        GeneratedCV TEXT,
        GeneratedCL TEXT,
        GeneratedML TEXT,
        AppliedDate TEXT
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
    # Insert default profile (your details)
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

# Run migration on every startup
if not os.path.exists(DB_PATH):
    reset_db()
else:
    ensure_table_schema()  # add missing columns if any

# ---------- Database helper functions ----------
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
        (Title, Organization, Category, Deadline, Status, CreatedAt, Saved, UserDescription, Link,
         GeneratedCV, GeneratedCL, GeneratedML, AppliedDate)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        data["title"], data["organization"], data["category"],
        data["deadline"].strftime("%Y-%m-%d"), data["status"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 0,
        data["description"], data["link"],
        "", "", "", ""
    ))
    conn.commit()
    conn.close()

def update_generated_docs(opp_id, cv, cl, ml):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE Opportunities SET GeneratedCV=?, GeneratedCL=?, GeneratedML=? WHERE Id=?",
              (cv, cl, ml, opp_id))
    conn.commit()
    conn.close()

def update_status(opp_id, new_status):
    conn = get_db()
    c = conn.cursor()
    applied_date = datetime.now().strftime("%Y-%m-%d") if new_status == "Applied" else ""
    c.execute("UPDATE Opportunities SET Status=?, AppliedDate=? WHERE Id=?",
              (new_status, applied_date, opp_id))
    conn.commit()
    conn.close()

def delete_opportunity(opp_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM Opportunities WHERE Id = ?", (opp_id,))
    conn.commit()
    conn.close()

# ---------- Keyword extraction ----------
def extract_keywords(text):
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    stopwords = {"the","and","for","with","from","into","about","without","etc","this","that","have","are"}
    return set(w for w in words if w not in stopwords)

# ---------- Local AI model (lazy loading) ----------
_model = None
_tokenizer = None

def load_model():
    global _model, _tokenizer
    if _model is None and USE_LOCAL_AI and AI_AVAILABLE:
        with st.spinner("🧠 Loading AI model (first run may take 5-10 min)... please wait."):
            _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
            _model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, trust_remote_code=True)
    return _model, _tokenizer

def generate_text(prompt, max_length=512):
    if not USE_LOCAL_AI or not AI_AVAILABLE:
        return None
    model, tokenizer = load_model()
    if model is None:
        return None
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
    outputs = model.generate(**inputs, max_new_tokens=max_length, do_sample=True, temperature=0.7)
    generated = tokenizer.decode(outputs[0], skip_special_tokens=True)
    if generated.startswith(prompt):
        generated = generated[len(prompt):].strip()
    return generated

# ---------- AI-based generation (with fallback to templates) ----------
def align_profile(profile, description):
    achievements = [a.strip() for a in profile['Achievements'].split(';') if a.strip()]
    skills = [s.strip() for s in profile['Skills'].split(',') if s.strip()]
    desc_tokens = extract_keywords(description or "")
    matched_ach = [ach for ach in achievements if any(tok in ach.lower() for tok in desc_tokens)]
    matched_skills = [sk for sk in skills if any(tok in sk.lower() for tok in desc_tokens)]
    return matched_ach or achievements[:3], matched_skills or skills[:5]

def generate_cv(profile, description):
    if USE_LOCAL_AI and AI_AVAILABLE:
        prompt = f"""You are an expert CV writer. Based on the profile below and the job description, write a professional CV in plain text (no markdown). Use clear sections: Contact, Education, Experience, Achievements, Skills, Certifications. Tailor it to the job.

Profile:
Name: {profile['Name']}
Email: {profile['Email']}
Phone: {profile['Phone']}
Location: {profile['Location']}
Education: {profile['Education']}
Experience: {profile['Experience']}
Achievements: {profile['Achievements']}
Skills: {profile['Skills']}
Certifications: {profile['Certifications']}

Job Description: {description}

CV:"""
        result = generate_text(prompt, max_length=500)
        if result:
            return result
    # Fallback template (smart keyword alignment)
    matched_ach, matched_skills = align_profile(profile, description)
    return f"""Name: {profile['Name']}
Email: {profile['Email']}
Phone: {profile['Phone']}
Location: {profile['Location']}

Education:
{profile['Education']}

Experience:
{profile['Experience']}

Achievements (aligned to opportunity):
{'; '.join(matched_ach)}

Skills (aligned to opportunity):
{', '.join(matched_skills)}

Certifications:
{profile['Certifications']}"""

def generate_cover_letter(profile, description):
    if USE_LOCAL_AI and AI_AVAILABLE:
        prompt = f"""Write a compelling cover letter (3 paragraphs) for the following opportunity. The applicant is {profile['Name']}. Use the job description to highlight relevant achievements and skills.

Profile: {profile['Name']}, {profile['Education']}
Experience: {profile['Experience']}
Achievements: {profile['Achievements']}
Skills: {profile['Skills']}

Job Description: {description}

Cover Letter:"""
        result = generate_text(prompt, max_length=600)
        if result:
            return result
    return f"""Dear Hiring Committee,

I am writing to apply for the position described. My name is {profile['Name']}, and I hold a {profile['Education']}. With a strong background in {profile['Experience']}, I am confident I can contribute effectively to your team.

My key achievements include {profile['Achievements']}, and my skills in {profile['Skills']} are directly aligned with the requirements of this role.

Thank you for considering my application. I look forward to the opportunity to discuss how I can contribute to your organization.

Sincerely,
{profile['Name']}"""

def generate_motivation_letter(profile, description):
    if USE_LOCAL_AI and AI_AVAILABLE:
        prompt = f"""Write a motivation letter for a scholarship/fellowship program. The applicant is {profile['Name']} from Ethiopia, with a mission to use GeoAI for water resource management. Explain why they are a perfect fit and how they will contribute.

Profile: {profile['Name']}, {profile['Education']}
Narrative Context: {profile['NarrativeContext']}
Narrative Solution: {profile['NarrativeSolution']}
Achievements: {profile['Achievements']}
Skills: {profile['Skills']}

Program Description: {description}

Motivation Letter:"""
        result = generate_text(prompt, max_length=700)
        if result:
            return result
    return f"""Dear Selection Committee,

My name is {profile['Name']} from Ethiopia. My journey in water resource engineering and GeoAI has been driven by a desire to solve real-world problems. {profile['NarrativeContext']}

I have developed {profile['Achievements']} and possess strong skills in {profile['Skills']}. This opportunity would allow me to further my mission of {profile['NarrativeSolution']} while contributing to your program's goals.

I am excited about the possibility of joining your community and look forward to the chance to learn and grow.

Sincerely,
{profile['Name']}"""

# ---------- Selenium helper (optional) ----------
def open_browser(link):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service
        options = Options()
        options.add_argument("--start-maximized")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(link)
        st.success("🌐 Browser opened. Complete the application manually.")
        return driver
    except Exception as e:
        st.error(f"Browser error: {e}. Please open the link manually.")
        return None

# ---------- Streamlit UI ----------
st.set_page_config(layout="wide", page_title="🎓 AI Application Dashboard", page_icon="🎓")

# --- Sidebar: Deadline Monitor ---
st.sidebar.title("📅 Deadline Monitor")
df_all = fetch_all()
if not df_all.empty:
    today = pd.Timestamp.today().normalize()
    df_all['DeadlineDate'] = pd.to_datetime(df_all['Deadline']).dt.normalize()
    df_all['DaysLeft'] = (df_all['DeadlineDate'] - today).dt.days
    urgent = df_all[df_all['DaysLeft'] <= 10]
    upcoming = df_all[(df_all['DaysLeft'] > 10) & (df_all['DaysLeft'] <= 30)]
    safe = df_all[df_all['DaysLeft'] > 30]

    st.sidebar.markdown("### 🔴 Urgent (≤10 days)")
    for _, row in urgent.iterrows():
        st.sidebar.write(f"• {row['Title']} ({row['DaysLeft']} days left)")
    st.sidebar.markdown("### 🟡 Upcoming (11–30 days)")
    for _, row in upcoming.iterrows():
        st.sidebar.write(f"• {row['Title']} ({row['DaysLeft']} days left)")
    st.sidebar.markdown("### 🟢 Safe (>30 days)")
    for _, row in safe.iterrows():
        st.sidebar.write(f"• {row['Title']} ({row['DaysLeft']} days left)")
else:
    st.sidebar.info("No opportunities yet.")

# --- Main Dashboard ---
st.title("🎓 Scholarship & Job AI Application Dashboard")

# ------------------- METRICS ROW -------------------
col1, col2, col3, col4 = st.columns(4)
df = fetch_all()
if not df.empty:
    total = len(df)
    applied = len(df[df['Status'] == 'Applied'])
    pending = len(df[df['Status'] == 'Not Applied'])
    urgent_count = len(df[pd.to_datetime(df['Deadline']) <= datetime.today() + timedelta(days=10)])
    col1.metric("📌 Total", total)
    col2.metric("✅ Applied", applied)
    col3.metric("⏳ Pending", pending)
    col4.metric("🔴 Urgent", urgent_count, delta="action needed" if urgent_count>0 else None)
else:
    col1.metric("📌 Total", 0)
    col2.metric("✅ Applied", 0)
    col3.metric("⏳ Pending", 0)
    col4.metric("🔴 Urgent", 0)

# ------------------- CHARTS -------------------
if not df.empty:
    # Deadline urgency bar chart
    today = pd.Timestamp.today().normalize()
    df['DeadlineDate'] = pd.to_datetime(df['Deadline']).dt.normalize()
    df['Urgency'] = df['DeadlineDate'].apply(lambda x: 'Urgent' if (x - today).days <= 10 else ('Upcoming' if (x - today).days <= 30 else 'Safe'))
    urgency_counts = df['Urgency'].value_counts().reset_index()
    urgency_counts.columns = ['Urgency', 'Count']
    fig_bar = px.bar(urgency_counts, x='Urgency', y='Count', color='Urgency',
                     color_discrete_map={'Urgent':'red','Upcoming':'orange','Safe':'green'},
                     title='Opportunities by Deadline Urgency')
    st.plotly_chart(fig_bar, use_container_width=True)

    # Applications over time (if any AppliedDate)
    applied_df = df[df['Status'] == 'Applied'].copy()
    if not applied_df.empty:
        applied_df['AppliedDate'] = pd.to_datetime(applied_df['AppliedDate'])
        daily_apps = applied_df.groupby(applied_df['AppliedDate'].dt.date).size().reset_index(name='count')
        daily_apps.columns = ['Date', 'Applications']
        fig_line = px.line(daily_apps, x='Date', y='Applications', title='Applications Submitted Over Time',
                           markers=True)
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("No applications submitted yet. Start applying!")

# ------------------- OPPORTUNITIES TABLE -------------------
st.subheader("📋 All Opportunities")
if df.empty:
    st.info("No opportunities yet. Add one below.")
else:
    # Add color column for deadline
    def deadline_color(deadline):
        try:
            days = (pd.to_datetime(deadline).date() - datetime.today().date()).days
        except:
            days = 999
        if days <= 10: return "🔴"
        elif days <= 30: return "🟡"
        return "🟢"
    df['Deadline Alert'] = df['Deadline'].apply(deadline_color)
    display_cols = ["Id", "Title", "Organization", "Deadline", "Deadline Alert", "Status", "Saved"]
    st.dataframe(df[display_cols], use_container_width=True)

    # Select opportunity for detailed actions
    selected_id = st.selectbox("Select Opportunity ID for detailed actions", df["Id"].tolist())
    if selected_id:
        row = df[df["Id"] == selected_id].iloc[0]
        profile_df = fetch_profile()
        if profile_df.empty:
            st.error("MasterProfile is empty. Please add your profile data.")
        else:
            profile = profile_df.iloc[0].to_dict()
            with st.expander(f"📄 {row['Title']} – {row['Organization']}", expanded=True):
                st.write(f"**Deadline:** {row['Deadline']} {deadline_color(row['Deadline'])}")
                st.write(f"**Status:** {row['Status']}")
                st.write(f"**Link:** {row['Link']}")
                st.write("**Job Description:**")
                description = st.text_area("Paste full job description here (AI will use it to tailor docs)",
                                           value=row["UserDescription"] or "", height=200)

                # Action buttons
                col_gen, col_status, col_del, col_browser = st.columns(4)
                with col_gen:
                    if st.button("⚡ Generate Documents (AI)", key="gen_docs"):
                        with st.spinner("🤖 AI is writing your tailored documents..."):
                            cv = generate_cv(profile, description)
                            cl = generate_cover_letter(profile, description)
                            ml = generate_motivation_letter(profile, description)
                            update_generated_docs(selected_id, cv, cl, ml)
                            st.success("✅ Documents generated and saved!")
                            st.rerun()
                with col_status:
                    if st.button("✅ Mark as Applied", key="mark_applied"):
                        update_status(selected_id, "Applied")
                        st.rerun()
                with col_del:
                    if st.button("🗑️ Delete", key="del_opp"):
                        delete_opportunity(selected_id)
                        st.rerun()
                with col_browser:
                    if st.button("🌐 Open Link", key="open_link"):
                        if row['Link'] and row['Link'].startswith("http"):
                            open_browser(row['Link'])
                        else:
                            st.warning("No valid link provided.")

                # Display generated documents if any
                if row['GeneratedCV']:
                    st.subheader("📄 Generated CV")
                    st.text_area("CV", row['GeneratedCV'], height=200)
                    st.download_button("⬇️ Download CV", data=row['GeneratedCV'], file_name=f"CV_{row['Title']}.txt", key="dl_cv")
                if row['GeneratedCL']:
                    st.subheader("✉️ Cover Letter")
                    st.text_area("Cover Letter", row['GeneratedCL'], height=200)
                    st.download_button("⬇️ Download Cover Letter", data=row['GeneratedCL'], file_name=f"CL_{row['Title']}.txt", key="dl_cl")
                if row['GeneratedML']:
                    st.subheader("📨 Motivation Letter")
                    st.text_area("Motivation Letter", row['GeneratedML'], height=200)
                    st.download_button("⬇️ Download Motivation Letter", data=row['GeneratedML'], file_name=f"ML_{row['Title']}.txt", key="dl_ml")

# ------------------- ADD NEW OPPORTUNITY -------------------
with st.expander("➕ Add New Opportunity", expanded=False):
    with st.form("add_form"):
        title = st.text_input("Title *")
        org = st.text_input("Organization *")
        cat = st.selectbox("Category", ["Scholarship", "Job", "Fellowship", "Other"])
        deadline = st.date_input("Deadline", value=datetime.today().date() + timedelta(days=30))
        link = st.text_input("Link (optional)")
        description_input = st.text_area("Description (paste full details here)", height=150)
        submitted = st.form_submit_button("Add Opportunity")
        if submitted:
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
                st.success("✅ Opportunity added! Scroll up to see it.")
                st.rerun()
            else:
                st.warning("Title and Organization are required.")

# ------------------- FOOTER -------------------
st.markdown("---")
st.caption("⚡ Powered by local AI (Phi-2) | All data stored locally in SQLite | Dashboard updates in real time")
