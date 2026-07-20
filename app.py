# ============================================================
# ULTIMATE AI-POWERED DASHBOARD – ALTAIR CHARTS (NO PLOTLY)
# ============================================================
import streamlit as st
import pandas as pd
import sqlite3
import re
from datetime import datetime, timedelta
import os
import altair as alt   # altair is already installed with Streamlit!

# ---------- Local AI ----------
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

# ---------- Configuration ----------
USE_LOCAL_AI = True          # Set False to skip AI download
DB_PATH = "pipeline_vault.db"
MODEL_NAME = "microsoft/phi-2"

# ---------- Database with schema migration ----------
def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def ensure_table_schema():
    conn = get_db()
    c = conn.cursor()
    c.execute("PRAGMA table_info(Opportunities)")
    existing = [col[1] for col in c.fetchall()]
    needed = {
        "GeneratedCV": "TEXT",
        "GeneratedCL": "TEXT",
        "GeneratedML": "TEXT",
        "AppliedTimestamp": "TEXT"
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
        AppliedTimestamp TEXT
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

if not os.path.exists(DB_PATH):
    reset_db()
else:
    ensure_table_schema()

# ---------- Database helpers ----------
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
         GeneratedCV, GeneratedCL, GeneratedML, AppliedTimestamp)
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
    applied_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if new_status == "Applied" else ""
    c.execute("UPDATE Opportunities SET Status=?, AppliedTimestamp=? WHERE Id=?",
              (new_status, applied_ts, opp_id))
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

# ---------- Local AI ----------
_model = None
_tokenizer = None

def load_model():
    global _model, _tokenizer
    if _model is None and USE_LOCAL_AI and AI_AVAILABLE:
        with st.spinner("🧠 Loading AI model (first run may take 5-10 min)..."):
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

# ---------- AI generation functions ----------
def align_profile(profile, description):
    achievements = [a.strip() for a in profile['Achievements'].split(';') if a.strip()]
    skills = [s.strip() for s in profile['Skills'].split(',') if s.strip()]
    desc_tokens = extract_keywords(description or "")
    matched_ach = [ach for ach in achievements if any(tok in ach.lower() for tok in desc_tokens)]
    matched_skills = [sk for sk in skills if any(tok in sk.lower() for tok in desc_tokens)]
    return matched_ach or achievements[:3], matched_skills or skills[:5]

def generate_cv(profile, description):
    if USE_LOCAL_AI and AI_AVAILABLE:
        prompt = f"""Write a concise CV in plain text with sections: Contact, Education, Experience, Achievements, Skills, Certifications. Tailor it to the job.

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
    matched_ach, matched_skills = align_profile(profile, description)
    return f"""Name: {profile['Name']}
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
{profile['Certifications']}"""

def generate_cover_letter(profile, description):
    if USE_LOCAL_AI and AI_AVAILABLE:
        prompt = f"""Write a cover letter (3 paragraphs) for this job/scholarship. Applicant: {profile['Name']}, {profile['Education']}.
Experience: {profile['Experience']}
Achievements: {profile['Achievements']}
Skills: {profile['Skills']}
Description: {description}
Cover Letter:"""
        result = generate_text(prompt, max_length=600)
        if result:
            return result
    return f"""Dear Hiring Committee,

I am writing to apply for the position described. My name is {profile['Name']}, and I hold a {profile['Education']}. With a background in {profile['Experience']}, I am confident I can contribute effectively.

My achievements include {profile['Achievements']}, and my skills in {profile['Skills']} are directly relevant.

Thank you for your consideration.

Sincerely,
{profile['Name']}"""

def generate_motivation_letter(profile, description):
    if USE_LOCAL_AI and AI_AVAILABLE:
        prompt = f"""Write a motivation letter for a scholarship/fellowship. Applicant: {profile['Name']} from Ethiopia, background in water engineering and GeoAI.
Narrative: {profile['NarrativeContext']}
Achievements: {profile['Achievements']}
Skills: {profile['Skills']}
Program Description: {description}
Motivation Letter:"""
        result = generate_text(prompt, max_length=700)
        if result:
            return result
    return f"""Dear Selection Committee,

My name is {profile['Name']} from Ethiopia. My journey in water resource engineering and GeoAI has been driven by a desire to solve real-world problems. {profile['NarrativeContext']}

I have developed {profile['Achievements']} and possess skills in {profile['Skills']}. This opportunity would allow me to further my mission of {profile['NarrativeSolution']}.

I look forward to contributing to your program.

Sincerely,
{profile['Name']}"""

# ---------- Selenium helper ----------
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
        st.success("🌐 Browser opened.")
        return driver
    except Exception as e:
        st.error(f"Browser error: {e}")
        return None

# ---------- Streamlit UI ----------
st.set_page_config(layout="wide", page_title="🎓 AI Application Dashboard", page_icon="🎓")

# Golden theme CSS
st.markdown("""
<style>
.stApp {
    background: linear-gradient(180deg, #1a1a2e 0%, #16213e 30%, #0f3460 60%, #533483 100%);
}
.golden-text {
    color: #FFD700;
    text-shadow: 0 0 10px rgba(255, 215, 0, 0.5);
}
.stButton button {
    background: linear-gradient(145deg, #FFD700, #B8860B) !important;
    color: #1a1a2e !important;
    border-radius: 30px !important;
    border: none !important;
    font-weight: bold !important;
    box-shadow: 0 4px 15px rgba(255, 215, 0, 0.4) !important;
}
.stButton button:hover {
    transform: scale(1.05);
}
</style>
""", unsafe_allow_html=True)

st.title("🎓 Scholarship & Job AI Dashboard")
st.markdown("<p class='golden-text' style='font-size:1.2rem;'>Powered by your own local AI</p>", unsafe_allow_html=True)

# Sidebar deadline monitor
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

# Metrics
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

# ---------- Combined Chart (Bar + Line) using Altair ----------
st.subheader("📈 Application Progress Over Time")
if not df.empty:
    applied_df = df[df['Status'] == 'Applied'].copy()
    if not applied_df.empty:
        applied_df['AppliedTS'] = pd.to_datetime(applied_df['AppliedTimestamp'])
        daily = applied_df.groupby(applied_df['AppliedTS'].dt.date).size().reset_index(name='Daily')
        daily.columns = ['Date', 'Daily']
        daily = daily.sort_values('Date')
        daily['Cumulative'] = daily['Daily'].cumsum()

        # Create a combined chart: bar for daily, line for cumulative
        # We'll use a layered chart with dual axis (but Altair doesn't support dual axis easily)
        # Instead, we'll make two separate charts side by side or stacked.
        # Or we can use a single chart with a line for cumulative and bar for daily (dual axis possible with resolve_scale)
        # For simplicity, we'll show two charts: daily bar and cumulative line (in two columns or stacked)
        col_left, col_right = st.columns(2)
        with col_left:
            bar = alt.Chart(daily).mark_bar(color='gold', opacity=0.7).encode(
                x='Date:T',
                y='Daily:Q',
                tooltip=['Date', 'Daily']
            ).properties(title='Daily Applications', height=300)
            st.altair_chart(bar, use_container_width=True)
        with col_right:
            line = alt.Chart(daily).mark_line(point=True, color='silver').encode(
                x='Date:T',
                y='Cumulative:Q',
                tooltip=['Date', 'Cumulative']
            ).properties(title='Cumulative Total', height=300)
            st.altair_chart(line, use_container_width=True)

        # Hour analysis
        st.subheader("⏰ Applications by Hour (Productivity Analysis)")
        applied_df['Hour'] = applied_df['AppliedTS'].dt.hour
        hour_counts = applied_df['Hour'].value_counts().sort_index().reset_index()
        hour_counts.columns = ['Hour', 'Count']
        hour_chart = alt.Chart(hour_counts).mark_bar(color='gold', opacity=0.8).encode(
            x='Hour:O',
            y='Count:Q',
            tooltip=['Hour', 'Count']
        ).properties(title='Applications by Hour of Day', height=300)
        st.altair_chart(hour_chart, use_container_width=True)
    else:
        st.info("No applications submitted yet.")
else:
    st.info("No opportunities yet.")

# Opportunities table
st.subheader("📋 All Opportunities")
if df.empty:
    st.info("No opportunities yet. Add one below.")
else:
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

    selected_id = st.selectbox("Select Opportunity ID for detailed actions", df["Id"].tolist())
    if selected_id:
        row = df[df["Id"] == selected_id].iloc[0]
        profile_df = fetch_profile()
        if profile_df.empty:
            st.error("MasterProfile is empty.")
        else:
            profile = profile_df.iloc[0].to_dict()
            with st.expander(f"📄 {row['Title']} – {row['Organization']}", expanded=True):
                st.write(f"**Deadline:** {row['Deadline']} {deadline_color(row['Deadline'])}")
                st.write(f"**Status:** {row['Status']}")
                st.write(f"**Link:** {row['Link']}")
                description = st.text_area("Paste full job description", value=row["UserDescription"] or "", height=150)

                col_gen, col_status, col_del, col_browser = st.columns(4)
                with col_gen:
                    if st.button("⚡ Generate Documents (AI)"):
                        with st.spinner("Generating..."):
                            cv = generate_cv(profile, description)
                            cl = generate_cover_letter(profile, description)
                            ml = generate_motivation_letter(profile, description)
                            update_generated_docs(selected_id, cv, cl, ml)
                            st.success("✅ Generated and saved!")
                            st.rerun()
                with col_status:
                    if st.button("✅ Mark as Applied"):
                        update_status(selected_id, "Applied")
                        st.rerun()
                with col_del:
                    if st.button("🗑️ Delete"):
                        delete_opportunity(selected_id)
                        st.rerun()
                with col_browser:
                    if st.button("🌐 Open Link"):
                        if row['Link'] and row['Link'].startswith("http"):
                            open_browser(row['Link'])
                        else:
                            st.warning("No link")

                if row['GeneratedCV']:
                    st.subheader("📄 CV")
                    st.text_area("CV", row['GeneratedCV'], height=200)
                    st.download_button("⬇️ Download CV", data=row['GeneratedCV'], file_name=f"CV_{row['Title']}.txt")
                if row['GeneratedCL']:
                    st.subheader("✉️ Cover Letter")
                    st.text_area("Cover Letter", row['GeneratedCL'], height=200)
                    st.download_button("⬇️ Download Cover Letter", data=row['GeneratedCL'], file_name=f"CL_{row['Title']}.txt")
                if row['GeneratedML']:
                    st.subheader("📨 Motivation Letter")
                    st.text_area("Motivation Letter", row['GeneratedML'], height=200)
                    st.download_button("⬇️ Download Motivation Letter", data=row['GeneratedML'], file_name=f"ML_{row['Title']}.txt")

# Add new opportunity
with st.expander("➕ Add New Opportunity"):
    with st.form("add_form"):
        title = st.text_input("Title *")
        org = st.text_input("Organization *")
        cat = st.selectbox("Category", ["Scholarship", "Job"])
        deadline = st.date_input("Deadline", value=datetime.today().date() + timedelta(days=30))
        link = st.text_input("Link (optional)")
        desc = st.text_area("Description", height=100)
        if st.form_submit_button("Add Opportunity"):
            if title and org:
                add_opportunity({
                    "title": title, "organization": org, "category": cat,
                    "deadline": deadline, "status": "Not Applied",
                    "description": desc, "link": link
                })
                st.success("✅ Added!")
                st.rerun()
            else:
                st.warning("Title and Organization required.")

st.caption("⚡ Powered by local AI (Phi-2) | Golden Theme | Altair Charts")
