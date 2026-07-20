# ============================================================
# FINAL AI-POWERED JOB/SCHOLARSHIP DASHBOARD
# ============================================================
import streamlit as st
import pandas as pd
import sqlite3
import re
from datetime import datetime, timedelta
import os
import altair as alt
import requests
from bs4 import BeautifulSoup

# ---------- Local AI (transformers) ----------
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

# ---------- CONFIGURATION ----------
USE_LOCAL_AI = True          # Set False to skip AI download (uses templates)
DB_PATH = "pipeline_vault.db"
MODEL_NAME = "microsoft/phi-2"

# ---------- DATABASE (with auto-migration) ----------
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
        "AppliedTimestamp": "TEXT",
        "LastNotificationCheck": "TEXT"  # for 5-hour reminder
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
        AppliedTimestamp TEXT,
        LastNotificationCheck TEXT
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

# ---------- DATABASE HELPERS ----------
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
         GeneratedCV, GeneratedCL, GeneratedML, AppliedTimestamp, LastNotificationCheck)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        data["title"], data["organization"], data["category"],
        data["deadline"].strftime("%Y-%m-%d"), data["status"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 0,
        data["description"], data["link"],
        "", "", "", "", ""
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

def update_notification_check(opp_id):
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE Opportunities SET LastNotificationCheck=? WHERE Id=?", (now, opp_id))
    conn.commit()
    conn.close()

# ---------- TEXT EXTRACTION FROM URL ----------
def extract_description_from_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        # Remove script and style tags
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text(separator='\n')
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        # Try to find the job description section – we'll just return the first 2000 chars
        full_text = '\n'.join(lines)
        # If too long, truncate
        if len(full_text) > 3000:
            full_text = full_text[:3000] + "..."
        return full_text
    except Exception as e:
        return f"Error fetching description: {e}"

# ---------- KEYWORD EXTRACTION ----------
def extract_keywords(text):
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    stopwords = {"the","and","for","with","from","into","about","without","etc","this","that","have","are"}
    return set(w for w in words if w not in stopwords)

# ---------- LOCAL AI ----------
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

# ---------- AI GENERATION (with fallback) ----------
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

# ---------- BROWSER HELPER ----------
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

# ---------- NOTIFICATION SYSTEM ----------
def check_notifications(df):
    today = datetime.today().date()
    urgent = df[pd.to_datetime(df['Deadline']).dt.date <= today + timedelta(days=10)]
    within_24h = df[pd.to_datetime(df['Deadline']).dt.date <= today + timedelta(days=1)]
    # Check last notification time (using first row's LastNotificationCheck)
    if not df.empty and 'LastNotificationCheck' in df.columns:
        last_check_str = df.iloc[0]['LastNotificationCheck']
        if last_check_str:
            last_check = datetime.strptime(last_check_str, "%Y-%m-%d %H:%M:%S")
            hours_since = (datetime.now() - last_check).total_seconds() / 3600
        else:
            hours_since = 999
    else:
        hours_since = 999

    messages = []
    if not urgent.empty:
        messages.append(f"🔴 {len(urgent)} urgent deadline(s) within 10 days!")
    if not within_24h.empty:
        messages.append(f"⚠️ {len(within_24h)} deadline(s) within 24 hours!")
    if hours_since > 5:
        messages.append(f"⏰ Last notification check was {int(hours_since)} hours ago. Please review urgent deadlines.")
    return messages

# ---------- STREAMLIT UI ----------
st.set_page_config(layout="wide", page_title="🎓 AI Dashboard", page_icon="🎓")

# ---- DARK THEME WITH GOLDEN ACCENTS ----
st.markdown("""
<style>
    /* Dark background, light text */
    .stApp {
        background-color: #0e1117;
        color: #f0f2f6;
    }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp p, .stApp label, .stApp .stMarkdown {
        color: #f0f2f6 !important;
    }
    .golden-text {
        color: #FFD700;
        text-shadow: 0 0 10px rgba(255, 215, 0, 0.3);
    }
    .stButton button {
        background: linear-gradient(145deg, #FFD700, #B8860B) !important;
        color: #0e1117 !important;
        border-radius: 30px !important;
        border: none !important;
        font-weight: bold !important;
        box-shadow: 0 4px 15px rgba(255, 215, 0, 0.3) !important;
    }
    .stButton button:hover {
        transform: scale(1.05);
        box-shadow: 0 6px 25px rgba(255, 215, 0, 0.5) !important;
    }
    .css-1y4p8pa { /* metrics */
        background: rgba(255,255,255,0.05) !important;
        border-radius: 15px !important;
        padding: 15px !important;
        border: 1px solid #FFD700 !important;
    }
    .dataframe {
        border: 1px solid #FFD700 !important;
        border-radius: 10px !important;
        background: #1e1e2a !important;
    }
    .dataframe th {
        background: #2a2a3a !important;
        color: #FFD700 !important;
    }
    .dataframe td {
        color: #f0f2f6 !important;
    }
    .streamlit-expanderHeader {
        background: rgba(255, 215, 0, 0.1) !important;
        border-left: 4px solid #FFD700 !important;
        color: #FFD700 !important;
    }
    .stAlert {
        background-color: rgba(255, 215, 0, 0.1) !important;
        color: #FFD700 !important;
        border: 1px solid #FFD700 !important;
    }
    /* Scrollbar */
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: #1e1e2a; }
    ::-webkit-scrollbar-thumb { background: #FFD700; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

st.title("🎓 Scholarship & Job AI Dashboard")
st.markdown("<p class='golden-text' style='font-size:1.2rem;'>Dark Theme • Golden Edition • Powered by Your Own Local AI</p>", unsafe_allow_html=True)

# ---- SIDEBAR: NOTIFICATIONS + DEADLINE MONITOR ----
st.sidebar.title("📅 Dashboard")
df_all = fetch_all()

# Notification Button
if st.sidebar.button("🔔 Check Notifications"):
    if not df_all.empty:
        msgs = check_notifications(df_all)
        if msgs:
            for msg in msgs:
                st.sidebar.warning(msg)
            # Update the last check time for the first opportunity (or create a global setting)
            if not df_all.empty:
                update_notification_check(df_all.iloc[0]['Id'])
        else:
            st.sidebar.success("✅ All deadlines are under control!")
    else:
        st.sidebar.info("No opportunities to check.")

# Deadline monitor
st.sidebar.markdown("---")
st.sidebar.markdown("### 📅 Deadline Summary")
if not df_all.empty:
    today = pd.Timestamp.today().normalize()
    df_all['DeadlineDate'] = pd.to_datetime(df_all['Deadline']).dt.normalize()
    df_all['DaysLeft'] = (df_all['DeadlineDate'] - today).dt.days
    urgent = df_all[df_all['DaysLeft'] <= 10]
    upcoming = df_all[(df_all['DaysLeft'] > 10) & (df_all['DaysLeft'] <= 30)]
    safe = df_all[df_all['DaysLeft'] > 30]
    st.sidebar.markdown("#### 🔴 Urgent (≤10 days)")
    for _, row in urgent.iterrows():
        st.sidebar.write(f"• {row['Title']} ({row['DaysLeft']} days left)")
    st.sidebar.markdown("#### 🟡 Upcoming (11–30 days)")
    for _, row in upcoming.iterrows():
        st.sidebar.write(f"• {row['Title']} ({row['DaysLeft']} days left)")
    st.sidebar.markdown("#### 🟢 Safe (>30 days)")
    for _, row in safe.iterrows():
        st.sidebar.write(f"• {row['Title']} ({row['DaysLeft']} days left)")
else:
    st.sidebar.info("No opportunities yet.")

# ---- MAIN CONTENT ----
df = fetch_all()

# Metrics row
col1, col2, col3, col4 = st.columns(4)
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

# ---- COMBINED CHART (Bar + Line) using Altair ----
st.subheader("📈 Application Progress (Daily Bars + Cumulative Line)")
if not df.empty:
    applied_df = df[df['Status'] == 'Applied'].copy()
    if not applied_df.empty:
        applied_df['AppliedTS'] = pd.to_datetime(applied_df['AppliedTimestamp'])
        daily = applied_df.groupby(applied_df['AppliedTS'].dt.date).size().reset_index(name='Daily')
        daily.columns = ['Date', 'Daily']
        daily = daily.sort_values('Date')
        daily['Cumulative'] = daily['Daily'].cumsum()

        # Create a layered chart with dual axis
        base = alt.Chart(daily).encode(x='Date:T')

        # Bar for daily
        bar = base.mark_bar(color='gold', opacity=0.7).encode(
            y=alt.Y('Daily:Q', axis=alt.Axis(title='Daily Applications', titleColor='gold', labelColor='gold'))
        )

        # Line for cumulative
        line = base.mark_line(point=True, color='silver', strokeWidth=3).encode(
            y=alt.Y('Cumulative:Q', axis=alt.Axis(title='Cumulative Total', titleColor='silver', labelColor='silver'))
        )

        # Combine both with independent y-axes
        combined = alt.layer(bar, line).resolve_scale(
            y='independent'
        ).properties(
            height=350,
            title='Daily Applications (bars) & Cumulative Total (line)'
        )

        st.altair_chart(combined, use_container_width=True)

        # Hour analysis
        st.subheader("⏰ Applications by Hour (Your Most Productive Times)")
        applied_df['Hour'] = applied_df['AppliedTS'].dt.hour
        hour_counts = applied_df['Hour'].value_counts().sort_index().reset_index()
        hour_counts.columns = ['Hour', 'Count']
        hour_chart = alt.Chart(hour_counts).mark_bar(color='gold', opacity=0.8).encode(
            x=alt.X('Hour:O', title='Hour of Day (0-23)'),
            y=alt.Y('Count:Q', title='Number of Applications')
        ).properties(height=300)
        st.altair_chart(hour_chart, use_container_width=True)
    else:
        st.info("No applications submitted yet. Start applying to see progress!")
else:
    st.info("Add your first opportunity to begin tracking.")

# ---- OPPORTUNITIES TABLE ----
st.subheader("📋 All Opportunities")
if df.empty:
    st.info("No opportunities yet. Add one below.")
else:
    # Color coding for deadlines
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

    # ---- DETAILED ACTIONS FOR SELECTED OPPORTUNITY ----
    selected_id = st.selectbox("Select Opportunity ID", df["Id"].tolist())
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

                # Description input with fetch from URL
                description = st.text_area(
                    "Paste job description (or enter URL and click Fetch)",
                    value=row["UserDescription"] or "",
                    height=150
                )

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔍 Fetch Description from URL"):
                        if row['Link'] and row['Link'].startswith("http"):
                            fetched = extract_description_from_url(row['Link'])
                            if fetched and not fetched.startswith("Error"):
                                # Update the description in the session and database
                                # We'll just set the text area value using session state
                                # Use st.session_state to update
                                st.session_state['desc_input'] = fetched
                                st.rerun()
                            else:
                                st.warning(f"Could not fetch: {fetched}")
                        else:
                            st.warning("Please provide a valid URL in the Link field above.")
                # Use session state to store description value
                if 'desc_input' not in st.session_state:
                    st.session_state['desc_input'] = description
                # Let the text area use the session state
                description = st.text_area(
                    "Job Description (editable)",
                    value=st.session_state.get('desc_input', row["UserDescription"] or ""),
                    height=150,
                    key="desc_editor"
                )

                # Action buttons
                col_gen, col_status, col_del, col_browser = st.columns(4)
                with col_gen:
                    if st.button("⚡ Generate Documents (AI)"):
                        with st.spinner("🤖 AI is writing your tailored documents..."):
                            cv = generate_cv(profile, description)
                            cl = generate_cover_letter(profile, description)
                            ml = generate_motivation_letter(profile, description)
                            update_generated_docs(selected_id, cv, cl, ml)
                            st.success("✅ Documents generated and saved!")
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
                            st.warning("No valid link provided.")

                # Show generated documents
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

# ---- ADD NEW OPPORTUNITY ----
with st.expander("➕ Add New Opportunity", expanded=False):
    with st.form("add_form"):
        title = st.text_input("Title *")
        org = st.text_input("Organization *")
        cat = st.selectbox("Category", ["Scholarship", "Job", "Fellowship", "Other"])
        deadline = st.date_input("Deadline", value=datetime.today().date() + timedelta(days=30))
        link = st.text_input("Link (optional) – paste URL to fetch description later")
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

st.markdown("---")
st.caption("⚡ Powered by local AI (Phi-2) | Data stored in SQLite | Dark Golden Theme")
