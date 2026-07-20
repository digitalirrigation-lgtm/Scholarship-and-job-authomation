# app.py
import streamlit as st
import pandas as pd
import sqlite3
import re
from datetime import datetime, timedelta
import os
import time

# Optional: local AI imports (will be loaded lazily)
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

# ------------------ CONFIGURATION ------------------
USE_LOCAL_AI = True  # Set to False to disable AI and use template-based generation
DB_PATH = "pipeline_vault.db"
MODEL_NAME = "microsoft/phi-2"  # Small, runs on CPU

# ------------------ DATABASE HELPERS ------------------
def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def reset_db():
    conn = get_db()
    c = conn.cursor()
    # Drop and recreate Opportunities with correct schema
    c.execute("DROP TABLE IF EXISTS Opportunities")
    c.execute('''CREATE TABLE Opportunities (
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
        GeneratedML TEXT
    )''')
    # Create Applications table for detailed tracking
    c.execute('''CREATE TABLE IF NOT EXISTS Applications (
        Id INTEGER PRIMARY KEY AUTOINCREMENT,
        OppId INTEGER,
        AppliedDate TEXT,
        SubmissionStatus TEXT,
        Notes TEXT,
        FOREIGN KEY(OppId) REFERENCES Opportunities(Id)
    )''')
    # Ensure MasterProfile exists
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

# Reset DB on first run (only once)
if not os.path.exists(DB_PATH):
    reset_db()

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
         GeneratedCV, GeneratedCL, GeneratedML)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (
        data["title"], data["organization"], data["category"],
        data["deadline"].strftime("%Y-%m-%d"), data["status"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 0,
        data["description"], data["link"],
        "", "", ""  # generated docs will be filled later
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

def delete_opportunity(opp_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM Opportunities WHERE Id = ?", (opp_id,))
    conn.commit()
    conn.close()

def update_status(opp_id, new_status):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE Opportunities SET Status=? WHERE Id=?", (new_status, opp_id))
    conn.commit()
    conn.close()

# ------------------ KEYWORD EXTRACTION ------------------
def extract_keywords(text):
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    stopwords = {"the","and","for","with","from","into","about","without","etc","this","that"}
    return set(w for w in words if w not in stopwords)

# ------------------ LOCAL AI MODEL (LAZY LOAD) ------------------
_model = None
_tokenizer = None

def load_model():
    global _model, _tokenizer
    if _model is None and USE_LOCAL_AI and AI_AVAILABLE:
        with st.spinner("Loading AI model (this may take a few minutes on first run)..."):
            _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
            _model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, trust_remote_code=True)
    return _model, _tokenizer

def generate_text(prompt, max_length=512):
    """Generate text using local model."""
    if not USE_LOCAL_AI or not AI_AVAILABLE:
        return None
    model, tokenizer = load_model()
    if model is None:
        return None
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
    outputs = model.generate(**inputs, max_new_tokens=max_length, do_sample=True, temperature=0.7)
    generated = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # Remove the prompt from the output
    if generated.startswith(prompt):
        generated = generated[len(prompt):].strip()
    return generated

# ------------------ AI-BASED GENERATION FUNCTIONS ------------------
def generate_cv_ai(profile, description):
    """Generate CV using AI if available, else fallback to template."""
    if USE_LOCAL_AI and AI_AVAILABLE:
        prompt = f"""You are an expert CV writer. Based on the following profile and job description, write a concise, professional CV in plain text. Use clear sections: Name, Contact, Education, Experience, Achievements, Skills, Certifications.

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

CV:
"""
        result = generate_text(prompt, max_length=400)
        if result:
            return result
    # Fallback to template
    return generate_cv_template(profile, description)

def generate_cover_letter_ai(profile, description):
    if USE_LOCAL_AI and AI_AVAILABLE:
        prompt = f"""Write a compelling cover letter for the following job/scholarship opportunity. The applicant is {profile['Name']}. Use the profile details and address the key points from the job description. Keep it to 3 paragraphs.

Profile: {profile['Name']}, {profile['Education']}, {profile['Experience']}
Achievements: {profile['Achievements']}
Skills: {profile['Skills']}

Job Description: {description}

Cover Letter:
"""
        result = generate_text(prompt, max_length=500)
        if result:
            return result
    # Fallback to template
    return generate_cover_letter_template(profile, description)

def generate_motivation_letter_ai(profile, description):
    if USE_LOCAL_AI and AI_AVAILABLE:
        prompt = f"""Write a motivation letter for a scholarship/fellowship program. The applicant is {profile['Name']} from Ethiopia, with background in water engineering and GeoAI. Explain why they are a perfect fit and how they will contribute. Use the narrative context: {profile['NarrativeContext']}

Profile: {profile['Name']}, {profile['Education']}
Narrative Context: {profile['NarrativeContext']}
Narrative Solution: {profile['NarrativeSolution']}
Achievements: {profile['Achievements']}
Skills: {profile['Skills']}

Program Description: {description}

Motivation Letter:
"""
        result = generate_text(prompt, max_length=600)
        if result:
            return result
    return generate_motivation_letter_template(profile, description)

# ------------------ TEMPLATE-BASED FALLBACKS ------------------
def align_profile(profile, description):
    achievements = [a.strip() for a in profile['Achievements'].split(';') if a.strip()]
    skills = [s.strip() for s in profile['Skills'].split(',') if s.strip()]
    desc_tokens = extract_keywords(description or "")
    matched_ach = [ach for ach in achievements if any(tok in ach.lower() for tok in desc_tokens)]
    matched_skills = [sk for sk in skills if any(tok in sk.lower() for tok in desc_tokens)]
    return matched_ach or achievements[:3], matched_skills or skills[:5]

def generate_cv_template(profile, description):
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

def generate_cover_letter_template(profile, description):
    return f"""
Dear Hiring Committee,

I am writing to apply for the position described. My name is {profile['Name']}, and I hold a {profile['Education']}. With a strong background in {profile['Experience']}, I am confident in my ability to contribute effectively.

My key achievements include {profile['Achievements']}. These experiences have honed my skills in {profile['Skills']}, which are directly relevant to this role.

I look forward to discussing how my background aligns with your needs. Thank you for your consideration.

Sincerely,
{profile['Name']}
"""

def generate_motivation_letter_template(profile, description):
    return f"""
Dear Selection Committee,

My name is {profile['Name']} from Ethiopia. My journey in water resource engineering and GeoAI has been driven by a desire to solve real-world problems. {profile['NarrativeContext']}

I have developed {profile['Achievements']} and possess strong skills in {profile['Skills']}. This opportunity would allow me to further my mission of {profile['NarrativeSolution']}.

I am excited about the possibility of contributing to your program and look forward to the chance to learn and grow.

Sincerely,
{profile['Name']}
"""

# ------------------ AUTOMATION HELPER (Selenium) ------------------
def open_browser(link):
    """Open the link in a browser (optional automation)."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service

        options = Options()
        options.add_argument("--start-maximized")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(link)
        st.success("Browser opened. Please complete the application manually if the site blocks automation.")
        return driver
    except Exception as e:
        st.error(f"Failed to open browser: {e}")
        return None

# ------------------ STREAMLIT UI ------------------
st.set_page_config(layout="wide", page_title="🎓 Scholarship & Job AI Dashboard", page_icon="🎓")

# Sidebar: urgent deadlines and summary
st.sidebar.title("📅 Deadline Monitor")
df_all = fetch_all()
if not df_all.empty:
    today = datetime.today().date()
    df_all['DeadlineDate'] = pd.to_datetime(df_all['Deadline']).dt.date
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

st.title("🎓 Scholarship & Job AI Dashboard")

# Main content
df = fetch_all()

if df.empty:
    st.info("No opportunities yet. Add one below.")
else:
    # Dataframe with color coding
    def deadline_color(deadline):
        try:
            days_left = (pd.to_datetime(deadline).date() - datetime.today().date()).days
        except:
            days_left = 999
        if days_left <= 10: return "🔴"
        elif days_left <= 30: return "🟡"
        return "🟢"

    df["deadline_alert"] = df["Deadline"].apply(deadline_color)
    # Show only relevant columns
    display_cols = ["Id", "Title", "Organization", "Deadline", "deadline_alert", "Status", "Saved"]
    st.dataframe(df[display_cols], use_container_width=True)

    # Select opportunity
    selected_id = st.selectbox("Select Opportunity ID", df["Id"].tolist())
    if selected_id:
        row = df[df["Id"] == selected_id].iloc[0]
        profile_df = fetch_profile()
        if profile_df.empty:
            st.error("MasterProfile table is empty.")
        else:
            profile = profile_df.iloc[0].to_dict()
            st.subheader(f"📄 {row['Title']} – {row['Organization']}")
            st.write(f"**Deadline:** {row['Deadline']} {deadline_color(row['Deadline'])}")
            st.write(f"**Status:** {row['Status']}")
            st.write(f"**Link:** {row['Link']}")
            description = st.text_area("Paste Job/Scholarship Description Here", value=row["UserDescription"] or "", height=150)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("⚡ Generate All Documents (AI)"):
                    with st.spinner("Generating documents..."):
                        cv = generate_cv_ai(profile, description)
                        cl = generate_cover_letter_ai(profile, description)
                        ml = generate_motivation_letter_ai(profile, description)
                        # Save to DB
                        update_generated_docs(selected_id, cv, cl, ml)
                        st.success("Documents generated and saved!")
                        st.rerun()

            with col2:
                if st.button("🔄 Update Status to 'Applied'"):
                    update_status(selected_id, "Applied")
                    st.rerun()

            # Show generated documents if exist
            if row['GeneratedCV']:
                st.subheader("📄 Generated CV")
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

            # Automation: open link in browser
            if st.button("🌐 Open Application Link (Auto-fill attempt)"):
                if row['Link'] and row['Link'].startswith("http"):
                    driver = open_browser(row['Link'])
                    if driver:
                        st.info("Browser opened. You can now manually fill the form.")
                else:
                    st.warning("No valid link provided.")

            # Delete
            if st.button("🗑️ Delete Opportunity"):
                delete_opportunity(selected_id)
                st.rerun()

# Add new opportunity
with st.expander("➕ Add New Opportunity"):
    with st.form("add"):
        title = st.text_input("Title")
        org = st.text_input("Organization")
        cat = st.selectbox("Category", ["Scholarship", "Job"])
        deadline = st.date_input("Deadline", value=datetime.today().date() + timedelta(days=30))
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
