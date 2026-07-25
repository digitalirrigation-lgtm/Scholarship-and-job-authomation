# ============================================================
# ULTIMATE AI DASHBOARD – PERMANENT GITHUB STORAGE
# SCHOLARSHIP & JOB TRACKER WITH LOCAL AI
# ============================================================
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
    .stButton button:hover {
        transform: translateY(-2px) scale(1.02);
        box-shadow: 0 6px 25px rgba(184, 134, 11, 0.5) !important;
    }
    h1, h2, h3 {
        color: #1a1a2e !important;
        font-weight: 700 !important;
    }
    .metric-card {
        background: rgba(255,255,255,0.8) !important;
        border-radius: 15px !important;
        padding: 15px !important;
        border-left: 4px solid #B8860B !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05) !important;
    }
    .dataframe {
        border-radius: 15px !important;
        overflow: hidden !important;
        background: rgba(255,255,255,0.8) !important;
    }
    .dataframe th {
        background: linear-gradient(145deg, #B8860B, #FFD700) !important;
        color: white !important;
        padding: 12px !important;
    }
    .dataframe td {
        padding: 10px !important;
        color: #1a1a2e !important;
    }
    .stAlert {
        background: rgba(184, 134, 11, 0.1) !important;
        border-left: 4px solid #B8860B !important;
        border-radius: 10px !important;
    }
    .status-applied {
        background: #28a745 !important;
        color: white !important;
        padding: 4px 12px !important;
        border-radius: 20px !important;
        font-size: 12px !important;
        font-weight: bold !important;
    }
    .status-pending {
        background: #ffc107 !important;
        color: black !important;
        padding: 4px 12px !important;
        border-radius: 20px !important;
        font-size: 12px !important;
        font-weight: bold !important;
    }
    .status-archived {
        background: #6c757d !important;
        color: white !important;
        padding: 4px 12px !important;
        border-radius: 20px !important;
        font-size: 12px !important;
        font-weight: bold !important;
    }
    .css-1d391kg {
        background: rgba(255,255,255,0.4) !important;
        backdrop-filter: blur(10px) !important;
    }
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: #f0f0f0; }
    ::-webkit-scrollbar-thumb { background: linear-gradient(145deg, #B8860B, #FFD700); border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# ---------- GITHUB CONFIGURATION ----------
def get_github_config():
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
        elif response.status_code == 404:
            df = pd.DataFrame(columns=[
                "Id", "Title", "Organization", "Category", "Deadline", 
                "Status", "Link", "Description", "Country", "CreatedAt"
            ])
            return df, None
        else:
            st.error(f"❌ Failed to load data: {response.status_code}")
            return pd.DataFrame(), None
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
            "message": f"Update opportunities - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "content": encoded,
            "branch": config['branch']
        }
        if sha:
            payload["sha"] = sha
        
        response = requests.put(url, headers=headers, json=payload)
        if response.status_code in [200, 201]:
            new_data = response.json()
            new_sha = new_data.get('content', {}).get('sha', sha)
            return True, new_sha
        else:
            st.error(f"❌ Failed to save: {response.status_code}")
            return False, sha
    except Exception as e:
        st.error(f"❌ Error saving data: {str(e)}")
        return False, sha

# ---------- LOCAL AI FUNCTIONS ----------
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

_model = None
_tokenizer = None

def load_ai_model():
    global _model, _tokenizer
    if _model is None and AI_AVAILABLE:
        try:
            with st.spinner("🧠 Loading AI model (first time may take 2-3 minutes)..."):
                model_name = "microsoft/phi-2"
                _tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
                _model = AutoModelForCausalLM.from_pretrained(
                    model_name, 
                    trust_remote_code=True,
                    device_map="auto"
                )
            st.success("✅ AI model loaded successfully!")
            return _model, _tokenizer
        except Exception as e:
            st.warning(f"⚠️ AI model not available: {str(e)}")
            return None, None
    return _model, _tokenizer

def generate_text(prompt, max_length=300):
    if not AI_AVAILABLE:
        return None
    
    model, tokenizer = load_ai_model()
    if model is None:
        return None
    
    try:
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        outputs = model.generate(
            **inputs, 
            max_new_tokens=max_length, 
            do_sample=True, 
            temperature=0.7,
            pad_token_id=tokenizer.eos_token_id
        )
        generated = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        if generated.startswith(prompt):
            generated = generated[len(prompt):].strip()
        
        words = generated.split()
        if len(words) > 200:
            generated = ' '.join(words[:200])
        
        return generated
    except Exception as e:
        st.warning(f"⚠️ AI generation error: {str(e)}")
        return None

def generate_cv(profile_data, description):
    prompt = f"""Write a professional CV (plain text) for a Water Resources Engineer. Use this format:

Contact: Name, Email, Phone, Location
Education: Degree and details
Experience: Relevant work experience
Achievements: Key accomplishments
Skills: Technical skills
Certifications: Professional certifications

Profile:
Name: {profile_data.get('name', 'ZEDAGIM TESFAYE TANTU')}
Email: {profile_data.get('email', 'zedagim100@gmail.com')}
Phone: {profile_data.get('phone', '+251-924-700-390')}
Location: {profile_data.get('location', 'Jigjiga, Ethiopia')}
Education: {profile_data.get('education', 'Bachelor in Water Resource Engineering')}
Experience: {profile_data.get('experience', 'Water resource engineering, irrigation systems')}
Achievements: {profile_data.get('achievements', 'Developed Hydro-Agritech prototypes; Digitized FAO-56 Penman-Monteith')}
Skills: {profile_data.get('skills', 'Python, GIS, Remote Sensing, Machine Learning')}

CV:"""
    
    ai_result = generate_text(prompt, max_length=400)
    if ai_result:
        return ai_result
    
    return f"""================================================================================
                               ZEDAGIM TESFAYE TANTU
================================================================================

CONTACT
---------
Email: zedagim100@gmail.com
Phone: +251-924-700-390
Location: Jigjiga, Ethiopia

EDUCATION
----------
Bachelor of Engineering in Water Resource & Irrigation Engineering
GPA: 3.87/4.00

EXPERIENCE
-----------
Water resource engineering
Irrigation systems design and management
Satellite data analysis for climate prediction
Hydrological modeling and assessment

ACHIEVEMENTS
-------------
• Developed Hydro-Agritech prototypes for automated irrigation
• Digitized FAO-56 Penman-Monteith for local conditions
• Contributed to preventing 456+ trafficking cases through community work

SKILLS
-------
Python, GIS, Remote Sensing, Machine Learning
Data Analysis, Project Management
Hydraulic Modeling, Water Quality Assessment

CERTIFICATIONS
---------------
Certified in GeoAI
Digital Irrigation Systems Specialist"""

def generate_cover_letter(profile_data, description):
    prompt = f"""Write a professional cover letter (3-4 paragraphs) for a job application. The applicant is an Ethiopian engineer.

Profile:
Name: {profile_data.get('name', 'ZEDAGIM TESFAYE TANTU')}
Education: {profile_data.get('education', 'Bachelor in Water Resource Engineering')}
Experience: {profile_data.get('experience', 'Water resource engineering')}
Achievements: {profile_data.get('achievements', 'Developed prototypes, digitized models')}
Skills: {profile_data.get('skills', 'Python, GIS, Remote Sensing')}

Job Description: {description[:300] if description else 'Water Resources position'}

Cover Letter:"""
    
    ai_result = generate_text(prompt, max_length=350)
    if ai_result:
        return ai_result
    
    return f"""Dear Hiring Committee,

My name is {profile_data.get('name', 'ZEDAGIM TESFAYE TANTU')} and I am writing to express my strong interest in this opportunity. With a background in Water Resource and Irrigation Engineering, I have developed expertise in using technology to solve complex water challenges.

Throughout my career, I have worked on projects that combine engineering principles with modern data analysis tools. My experience includes developing prototypes for automated irrigation systems and using satellite data for drought prediction - skills that directly align with your requirements.

What sets me apart is my ability to work in challenging environments with limited resources. I have proven that I can deliver high-quality results even without extensive budgets or sophisticated equipment. This experience has made me adaptable, creative, and determined.

I am confident that my skills and experiences make me a strong candidate for this position. Thank you for considering my application. I look forward to discussing how I can contribute to your team.

Sincerely,
{profile_data.get('name', 'ZEDAGIM TESFAYE TANTU')}"""

def generate_motivation_letter(profile_data, description):
    prompt = f"""Write a motivation letter (3-4 paragraphs) for a scholarship. The applicant is from Ethiopia.

Profile:
Name: {profile_data.get('name', 'ZEDAGIM TESFAYE TANTU')}
Background: {profile_data.get('background', 'Water engineering and GeoAI')}
Achievements: {profile_data.get('achievements', 'Developed prototypes, prevented trafficking')}
Skills: {profile_data.get('skills', 'Python, GIS, Remote Sensing')}

Program Description: {description[:300] if description else 'Scholarship program'}

Motivation Letter:"""
    
    ai_result = generate_text(prompt, max_length=350)
    if ai_result:
        return ai_result
    
    return f"""Dear Selection Committee,

My name is {profile_data.get('name', 'ZEDAGIM TESFAYE TANTU')} from Ethiopia. My journey in water resource engineering has been driven by a desire to solve real problems facing my community. As someone who has worked directly on irrigation challenges in the Horn of Africa, I understand the critical importance of water management.

I have developed practical solutions, including prototypes for smart irrigation systems and models for drought prediction using satellite data. These projects taught me that real impact comes from combining technical skills with deep understanding of local needs. My work has already prevented water waste and improved agricultural outcomes.

My experiences have also shown me the importance of international collaboration and knowledge sharing. I believe that bringing together diverse perspectives is essential for tackling global water challenges. This scholarship represents an opportunity to gain new skills and contribute to a global community of water professionals.

I am committed to returning to Ethiopia after my studies and applying what I learn to benefit my community. Thank you for considering my application.

Sincerely,
{profile_data.get('name', 'ZEDAGIM TESFAYE TANTU')}"""

# ---------- WEB SEARCH FUNCTIONS ----------
def search_opportunities():
    results = []
    
    search_sources = [
        "https://www.scholars4dev.com/category/developing-countries/",
        "https://www.mastersportal.com/search/ethiopia/",
        "https://www.opportunitiesforafricans.com/category/scholarships/"
    ]
    
    for url in search_sources:
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for item in soup.find_all(['h2', 'h3', 'h4'])[:5]:
                title = item.get_text().strip()
                if len(title) > 10 and any(term in title.lower() for term in ['water', 'engineering', 'scholarship', 'fellowship', 'master', 'phd']):
                    results.append({
                        "title": title[:80],
                        "source": url,
                        "found_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
            time.sleep(1)
        except:
            continue
    
    return results

def extract_description_from_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for script in soup(["script", "style"]):
            script.decompose()
        
        text = soup.get_text(separator='\n')
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        full_text = '\n'.join(lines)
        
        if len(full_text) > 2000:
            full_text = full_text[:2000] + "..."
        
        return full_text
    except Exception as e:
        return f"Error fetching content: {str(e)}"

# ---------- COUNTRY LIST ----------
COUNTRIES = [
    "All", "Afghanistan", "Albania", "Algeria", "Angola", "Argentina", "Armenia", "Australia", 
    "Austria", "Azerbaijan", "Bahrain", "Bangladesh", "Belarus", "Belgium", "Benin", "Bhutan", 
    "Bolivia", "Bosnia", "Brazil", "Bulgaria", "Burkina Faso", "Burundi", "Cambodia", "Cameroon", 
    "Canada", "Chad", "Chile", "China", "Colombia", "Comoros", "Congo", "Costa Rica", 
    "Croatia", "Cuba", "Cyprus", "Czech Republic", "Denmark", "Djibouti", "Dominican Republic", 
    "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", 
    "Ethiopia", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany", "Ghana", 
    "Greece", "Guatemala", "Guinea", "Guyana", "Haiti", "Honduras", "Hungary", "Iceland", 
    "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy", "Ivory Coast", 
    "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kuwait", "Kyrgyzstan", "Laos", 
    "Latvia", "Lebanon", "Liberia", "Libya", "Lithuania", "Luxembourg", "Madagascar", "Malawi", 
    "Malaysia", "Maldives", "Mali", "Malta", "Mauritania", "Mauritius", "Mexico", "Moldova", 
    "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia", "Nepal", "Netherlands", 
    "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea", "North Macedonia", "Norway", 
    "Oman", "Pakistan", "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland", 
    "Portugal", "Qatar", "Romania", "Russia", "Rwanda", "Saudi Arabia", "Senegal", "Serbia", 
    "Sierra Leone", "Singapore", "Slovakia", "Slovenia", "Somalia", "South Africa", "South Korea", 
    "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria", "Taiwan", 
    "Tajikistan", "Tanzania", "Thailand", "Togo", "Trinidad", "Tunisia", "Turkey", "Turkmenistan", 
    "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "United States", "Uruguay", 
    "Uzbekistan", "Vatican City", "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe"
]

# ---------- INITIALIZE SESSION STATE ----------
def init_session_state():
    if "df" not in st.session_state:
        df, sha = load_data_from_github()
        st.session_state.df = df if not df.empty else pd.DataFrame(columns=[
            "Id", "Title", "Organization", "Category", "Deadline", 
            "Status", "Link", "Description", "Country", "CreatedAt"
        ])
        st.session_state.sha = sha
    
    if "submitted" not in st.session_state:
        st.session_state.submitted = False
    
    if "selected_country" not in st.session_state:
        st.session_state.selected_country = "All"
    
    if "notification_count" not in st.session_state:
        st.session_state.notification_count = 0
    
    if "last_search" not in st.session_state:
        st.session_state.last_search = datetime.now()

init_session_state()

# ---------- PROFILE DATA ----------
def get_profile_data():
    return {
        "name": "ZEDAGIM TESFAYE TANTU",
        "email": "zedagim100@gmail.com",
        "phone": "+251-924-700-390",
        "location": "Jigjiga, Ethiopia",
        "education": "Bachelor of Engineering in Water Resource & Irrigation Engineering (GPA: 3.87/4.00)",
        "experience": "Water resource engineering, irrigation systems, satellite data analysis, climate prediction",
        "achievements": "Developed Hydro-Agritech prototypes; Digitized FAO-56 Penman-Monteith; Prevented 456+ trafficking cases",
        "skills": "Python, GIS, Remote Sensing, Machine Learning, Data Analysis, Project Management",
        "certifications": "Certified in GeoAI, Digital Irrigation Systems",
        "background": "Water engineering and GeoAI for developing regions"
    }

# ---------- CRUD OPERATIONS ----------
def add_opportunity(data):
    df = st.session_state.df
    new_id = len(df) + 1 if not df.empty else 1
    
    new_row = pd.DataFrame([{
        "Id": new_id,
        "Title": data["title"],
        "Organization": data["organization"],
        "Category": data["category"],
        "Deadline": data["deadline"],
        "Status": "Not Applied",
        "Link": data.get("link", ""),
        "Description": data.get("description", ""),
        "Country": data.get("country", "All"),
        "CreatedAt": datetime.now().strftime("%Y-%m-%d %H:%M")
    }])
    
    df = pd.concat([df, new_row], ignore_index=True)
    success, new_sha = save_data_to_github(df, st.session_state.sha)
    
    if success:
        st.session_state.df = df
        st.session_state.sha = new_sha
        st.session_state.submitted = True
        return True
    return False

def update_opportunity(opp_id, data):
    df = st.session_state.df
    idx = df[df["Id"] == opp_id].index
    
    if not idx.empty:
        for key, value in data.items():
            if key in df.columns:
                df.loc[idx, key] = value
        
        success, new_sha = save_data_to_github(df, st.session_state.sha)
        if success:
            st.session_state.df = df
            st.session_state.sha = new_sha
            return True
    return False

def archive_opportunity(opp_id):
    return update_opportunity(opp_id, {"Status": "Archived"})

def delete_opportunity_permanent(opp_id):
    df = st.session_state.df
    df = df[df["Id"] != opp_id]
    success, new_sha = save_data_to_github(df, st.session_state.sha)
    if success:
        st.session_state.df = df
        st.session_state.sha = new_sha
        return True
    return False

# ---------- FILTER FUNCTIONS ----------
def filter_by_country(df, country):
    if country == "All" or country == "":
        return df
    return df[df["Country"] == country]

def filter_by_status(df, status):
    if status == "All" or status == "":
        return df
    return df[df["Status"] == status]

def filter_by_deadline(df, days):
    if days == "All" or days == "":
        return df
    
    today = datetime.today().date()
    if days == "Today":
        return df[pd.to_datetime(df["Deadline"]).dt.date == today]
    elif days == "This Week":
        week_end = today + timedelta(days=7)
        return df[(pd.to_datetime(df["Deadline"]).dt.date >= today) & 
                  (pd.to_datetime(df["Deadline"]).dt.date <= week_end)]
    elif days == "This Month":
        month_end = today + timedelta(days=30)
        return df[(pd.to_datetime(df["Deadline"]).dt.date >= today) & 
                  (pd.to_datetime(df["Deadline"]).dt.date <= month_end)]
    return df

def filter_by_search(df, search_term):
    if not search_term:
        return df
    
    search_lower = search_term.lower()
    mask = df["Title"].str.lower().str.contains(search_lower, na=False) | \
           df["Organization"].str.lower().str.contains(search_lower, na=False) | \
           df["Category"].str.lower().str.contains(search_lower, na=False) | \
           df["Description"].str.lower().str.contains(search_lower, na=False)
    return df[mask]

# ---------- UI: SIDEBAR ----------
with st.sidebar:
    st.markdown("## 🎯 Dashboard")
    
    df = st.session_state.df
    if not df.empty:
        total = len(df)
        applied = len(df[df["Status"] == "Applied"])
        pending = len(df[df["Status"] == "Not Applied"])
        archived = len(df[df["Status"] == "Archived"])
        
        st.markdown(f"""
        ### 📊 Quick Stats
        - **Total:** {total}
        - **Applied:** {applied} ✅
        - **Pending:** {pending} ⏳
        - **Archived:** {archived} 📁
        """)
        
        today = datetime.today().date()
        urgent = df[pd.to_datetime(df["Deadline"]).dt.date <= today + timedelta(days=3)]
        if not urgent.empty:
            st.warning(f"🔴 {len(urgent)} urgent deadlines within 3 days!")
    else:
        st.info("No opportunities yet. Add your first one!")
    
    st.markdown("---")
    
    if st.button("🔔 Check Notifications", use_container_width=True):
        if not df.empty:
            urgent_count = len(df[pd.to_datetime(df["Deadline"]).dt.date <= datetime.today().date() + timedelta(days=3)])
            if urgent_count > 0:
                st.success(f"🔔 {urgent_count} urgent opportunities need attention!")
            else:
                st.success("✅ All deadlines are under control!")
        else:
            st.info("No opportunities to check.")
    
    if st.button("🌐 Find New Opportunities", use_container_width=True):
        with st.spinner("Searching for opportunities..."):
            results = search_opportunities()
            st.session_state.search_results = results
            if results:
                st.success(f"✅ Found {len(results)} new opportunities!")
                for r in results[:3]:
                    st.write(f"- {r['title'][:60]}...")
            else:
                st.info("No new opportunities found.")
    
    st.markdown("---")
    st.caption("⚡ Data stored on GitHub • AI runs locally")

# ---------- UI: MAIN PAGE ----------
st.title("🎓 Scholarship & Job AI Dashboard")
st.markdown("*Automated tracking, AI document generation, and permanent storage*")

if "search_results" in st.session_state and st.session_state.search_results:
    st.success(f"🔔 Found {len(st.session_state.search_results)} new opportunities from the web!")

# ---------- FILTERS SECTION ----------
st.markdown("### 🔍 Filters & Search")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    country_filter = st.selectbox(
        "🌍 Country",
        ["All"] + COUNTRIES[1:],
        index=0,
        key="country_filter"
    )

with col2:
    status_filter = st.selectbox(
        "📌 Status",
        ["All", "Not Applied", "Applied", "Archived"],
        key="status_filter"
    )

with col3:
    deadline_filter = st.selectbox(
        "⏰ Deadline",
        ["All", "Today", "This Week", "This Month"],
        key="deadline_filter"
    )

with col4:
    search_term = st.text_input("🔎 Search", placeholder="Type to search...", key="search_input")

with col5:
    if st.button("🔄 Reset Filters", use_container_width=True):
        st.session_state.country_filter = "All"
        st.session_state.status_filter = "All"
        st.session_state.deadline_filter = "All"
        st.session_state.search_input = ""
        st.rerun()

# ---------- APPLY FILTERS ----------
df = st.session_state.df.copy()

if not df.empty:
    df = filter_by_country(df, country_filter)
    df = filter_by_status(df, status_filter)
    df = filter_by_deadline(df, deadline_filter)
    df = filter_by_search(df, search_term)
    
    today = datetime.today().date()
    df["DeadlineDate"] = pd.to_datetime(df["Deadline"]).dt.date
    df["DaysLeft"] = (df["DeadlineDate"] - today).dt.days
    
    def get_status_badge(status):
        if status == "Applied":
            return "🟢 Applied"
        elif status == "Not Applied":
            return "🟡 Pending"
        elif status == "Archived":
            return "⚪ Archived"
        return status
    
    def get_deadline_color(days_left):
        if pd.isna(days_left):
            return "⚪"
        if days_left < 0:
            return "🔴"
        elif days_left <= 3:
            return "🔴"
        elif days_left <= 7:
            return "🟡"
        elif days_left <= 30:
            return "🟢"
        return "🔵"
    
    df["StatusBadge"] = df["Status"].apply(get_status_badge)
    df["Urgency"] = df["DaysLeft"].apply(get_deadline_color)
    
    st.info(f"📌 Showing {len(df)} opportunities out of {len(st.session_state.df)} total")
else:
    st.info("ℹ️ No opportunities match your filters. Add your first opportunity below!")

# ---------- METRICS ROW ----------
if not df.empty:
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("📌 Total", len(df))
    with col2:
        st.metric("✅ Applied", len(df[df["Status"] == "Applied"]))
    with col3:
        st.metric("⏳ Pending", len(df[df["Status"] == "Not Applied"]))
    with col4:
        urgent_count = len(df[df["DaysLeft"] <= 3])
        st.metric("🔴 Urgent", urgent_count, delta="⚠️" if urgent_count > 0 else None)
    with col5:
        with st.container():
            st.metric("📁 Archived", len(df[df["Status"] == "Archived"]))

# ---------- TABLE VIEW ----------
st.markdown("### 📋 All Opportunities")

if not df.empty:
    display_cols = ["Urgency", "Id", "Title", "Organization", "Deadline", "DaysLeft", "StatusBadge", "Category", "Country"]
    display_df = df[display_cols].copy()
    display_df = display_df.rename(columns={
        "StatusBadge": "Status",
        "DaysLeft": "Days Left"
    })
    
    st.dataframe(
        display_df,
        use_container_width=True,
        column_config={
            "Urgency": st.column_config.TextColumn("⚠️"),
            "Id": st.column_config.NumberColumn("ID"),
            "Title": st.column_config.TextColumn("📌 Title"),
            "Organization": st.column_config.TextColumn("🏢 Organization"),
            "Deadline": st.column_config.DateColumn("📅 Deadline"),
            "Days Left": st.column_config.NumberColumn("Days", format="%d"),
            "Status": st.column_config.TextColumn("✅ Status"),
            "Category": st.column_config.TextColumn("📂 Category"),
            "Country": st.column_config.TextColumn("🌍 Country")
        }
    )
    
    # ---------- DETAIL VIEW ----------
    st.markdown("### 📄 Opportunity Details")
    
    if not df.empty:
        selected_id = st.selectbox(
            "Select opportunity to view details:",
            options=df["Id"].tolist(),
            format_func=lambda x: f"{x} - {df[df['Id']==x]['Title'].iloc[0][:50]}"
        )
        
        if selected_id:
            row = df[df["Id"] == selected_id].iloc[0]
            
            with st.expander(f"📄 {row['Title']} – {row['Organization']}", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**📍 Organization:** {row['Organization']}")
                    st.write(f"**📂 Category:** {row['Category']}")
                    st.write(f"**🌍 Country:** {row['Country']}")
                    st.write(f"**📅 Deadline:** {row['Deadline']}")
                    st.write(f"**⏰ Days Left:** {row['DaysLeft']} days")
                with col2:
                    st.write(f"**✅ Status:** {row['Status']}")
                    st.write(f"**🔗 Link:** {row['Link'] if row['Link'] else 'Not provided'}")
                    if row['Link']:
                        st.write(f"**🌐 URL:** [{row['Link'][:30]}...]({row['Link']})")
                
                st.write(f"**📝 Description:**")
                description = row['Description'] if row['Description'] else "No description provided"
                st.text_area("", description, height=100, key=f"desc_{selected_id}")
                
                # Action buttons
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    if row["Status"] != "Applied":
                        if st.button("✅ Mark Applied", key=f"apply_{selected_id}"):
                            if update_opportunity(selected_id, {"Status": "Applied"}):
                                st.success("✅ Marked as Applied!")
                                st.rerun()
                
                with col2:
                    if row["Status"] != "Archived":
                        if st.button("📁 Archive", key=f"archive_{selected_id}"):
                            if archive_opportunity(selected_id):
                                st.success("📁 Archived successfully!")
                                st.rerun()
                
                with col3:
                    if row["Status"] == "Archived":
                        if st.button("🔄 Restore", key=f"restore_{selected_id}"):
                            if update_opportunity(selected_id, {"Status": "Not Applied"}):
                                st.success("🔄 Restored successfully!")
                                st.rerun()
                
                with col4:
                    if st.button("🗑️ Delete Permanently", key=f"delete_{selected_id}"):
                        if st.warning(f"⚠️ Are you sure you want to delete '{row['Title']}'? This cannot be undone!"):
                            if delete_opportunity_permanent(selected_id):
                                st.success("🗑️ Deleted permanently!")
                                st.rerun()
                
                # AI Document Generation
                st.markdown("---")
                st.subheader("🤖 AI Document Generator")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("📄 Generate CV", key=f"cv_{selected_id}"):
                        with st.spinner("Generating CV..."):
                            profile = get_profile_data()
                            cv = generate_cv(profile, description)
                            if cv:
                                st.session_state[f"cv_{selected_id}"] = cv
                                st.success("✅ CV Generated!")
                            else:
                                st.warning("⚠️ AI not available. Using template.")
                                cv = generate_cv(profile, description)
                                st.session_state[f"cv_{selected_id}"] = cv
                
                with col2:
                    if st.button("✉️ Generate Cover Letter", key=f"cl_{selected_id}"):
                        with st.spinner("Generating Cover Letter..."):
                            profile = get_profile_data()
                            cl = generate_cover_letter(profile, description)
                            if cl:
                                st.session_state[f"cl_{selected_id}"] = cl
                                st.success("✅ Cover Letter Generated!")
                
                with col3:
                    if st.button("📨 Generate Motivation Letter", key=f"ml_{selected_id}"):
                        with st.spinner("Generating Motivation Letter..."):
                            profile = get_profile_data()
                            ml = generate_motivation_letter(profile, description)
                            if ml:
                                st.session_state[f"ml_{selected_id}"] = ml
                                st.success("✅ Motivation Letter Generated!")
                
                # Display generated documents
                if f"cv_{selected_id}" in st.session_state:
                    with st.expander("📄 View CV"):
                        st.text_area("", st.session_state[f"cv_{selected_id}"], height=300)
                        st.download_button(
                            "⬇️ Download CV",
                            st.session_state[f"cv_{selected_id}"],
                            file_name=f"CV_{row['Title'][:30]}_{datetime.now().strftime('%Y%m%d')}.txt"
                        )
                
                if f"cl_{selected_id}" in st.session_state:
                    with st.expander("✉️ View Cover Letter"):
                        st.text_area("", st.session_state[f"cl_{selected_id}"], height=300)
                        st.download_button(
                            "⬇️ Download Cover Letter",
                            st.session_state[f"cl_{selected_id}"],
                            file_name=f"CoverLetter_{row['Title'][:30]}_{datetime.now().strftime('%Y%m%d')}.txt"
                        )
                
                if f"ml_{selected_id}" in st.session_state:
                    with st.expander("📨 View Motivation Letter"):
                        st.text_area("", st.session_state[f"ml_{selected_id}"], height=300)
                        st.download_button(
                            "⬇️ Download Motivation Letter",
                            st.session_state[f"ml_{selected_id}"],
                            file_name=f"Motivation_{row['Title'][:30]}_{datetime.now().strftime('%Y%m%d')}.txt"
                        )
else:
    st.info("ℹ️ No opportunities available. Add your first opportunity using the form below.")

# ---------- ADD NEW OPPORTUNITY ----------
st.markdown("---")
st.markdown("### ➕ Add New Opportunity")

with st.form("add_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    
    with col1:
        title = st.text_input("📌 Title *", placeholder="e.g., MSc Water Resources Engineering")
        organization = st.text_input("🏢 Organization *", placeholder="e.g., University of Oxford")
        category = st.selectbox("📂 Category", ["Scholarship", "Job", "Fellowship", "Internship", "Other"])
    
    with col2:
        deadline = st.date_input("📅 Deadline", value=datetime.today().date() + timedelta(days=30))
        country = st.selectbox("🌍 Country", COUNTRIES, index=COUNTRIES.index("Ethiopia"))
        link = st.text_input("🔗 Link", placeholder="https://example.com/opportunity")
    
    description = st.text_area("📝 Description", height=100, placeholder="Paste or describe the opportunity...")
    
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        submitted = st.form_submit_button("➕ Add Opportunity", use_container_width=True)
    
    if submitted:
        if title and organization:
            if add_opportunity({
                "title": title,
                "organization": organization,
                "category": category,
                "deadline": deadline.strftime("%Y-%m-%d"),
                "country": country,
                "link": link,
                "description": description
            }):
                st.success("✅ Opportunity added successfully!")
                st.rerun()
        else:
            st.error("❌ Title and Organization are required!")

# ---------- FOOTER ----------
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("📊 Data stored permanently on GitHub")
with col2:
    st.caption("🤖 AI runs locally on your machine")
with col3:
    st.caption(f"🔄 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
