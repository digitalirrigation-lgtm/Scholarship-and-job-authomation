import streamlit as st
import pandas as pd
import sqlite3
import re
import requests
from datetime import datetime, timedelta

# These packages power optional features (link-scraping, RSS sync, graphs).
# If one is missing on the server, the app must NOT go blank — it should
# just quietly disable that one feature and keep working.
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

try:
    import altair as alt
    HAS_ALTAIR = True
except ImportError:
    HAS_ALTAIR = False

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(layout="wide", page_title="Scholarship & Job AI Dashboard", page_icon="🎓")

# ==========================================
# CUSTOM CSS – OCEAN WAVE BACKGROUND
# ==========================================
st.markdown("""
<style>
.stApp {
    background: #0a192f;
    position: relative;
    overflow: hidden;
}
.wave-container {
    position: fixed;
    bottom: 0;
    left: 0;
    width: 200%;
    height: 200px;
    z-index: 0;
    pointer-events: none;
    opacity: 0.6;
    background: repeating-linear-gradient(90deg,
        rgba(0, 150, 255, 0.2) 0%,
        rgba(0, 200, 255, 0.4) 25%,
        rgba(0, 150, 255, 0.2) 50%);
    animation: waveMove 15s linear infinite;
    border-radius: 50% 50% 0 0;
}
.wave-container2 {
    position: fixed;
    bottom: 0;
    left: 0;
    width: 200%;
    height: 150px;
    z-index: 0;
    pointer-events: none;
    opacity: 0.4;
    background: repeating-linear-gradient(90deg,
        rgba(0, 200, 255, 0.1) 0%,
        rgba(0, 250, 255, 0.3) 30%,
        rgba(0, 200, 255, 0.1) 60%);
    animation: waveMove2 20s linear infinite;
    border-radius: 50% 50% 0 0;
}
@keyframes waveMove {
    0% { transform: translateX(0) scaleY(0.8); }
    50% { transform: translateX(-25%) scaleY(1.2); }
    100% { transform: translateX(-50%) scaleY(0.8); }
}
@keyframes waveMove2 {
    0% { transform: translateX(0) scaleY(0.6); }
    50% { transform: translateX(-20%) scaleY(1.0); }
    100% { transform: translateX(-40%) scaleY(0.6); }
}
.block-container {
    position: relative;
    z-index: 10 !important;
}
input, textarea, select {
    background-color: rgba(26,54,68,0.9) !important;
    color: white !important;
    border: 1px solid #00f2fe !important;
    border-radius: 8px;
    padding: 8px;
}
.stTabs [data-baseweb="tab"] {
    color: #8ab4f8 !important;
    font-size: 16px;
    font-weight: 600;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: #00f2fe !important;
    border-bottom: 2px solid #00f2fe;
}
div[data-testid="stExpander"] {
    background-color: rgba(32,58,67,0.5) !important;
    border: 1px solid #00f2fe;
    border-radius: 12px;
}
h1, h2, h3, h4, p, label {
    color: white !important;
}
.stButton button {
    background: linear-gradient(135deg, #00f2fe, #4facfe);
    color: white;
    border: none;
    border-radius: 20px;
    padding: 0.5rem 1.5rem;
    font-weight: 600;
    transition: all 0.3s ease;
}
.stButton button:hover {
    transform: scale(1.05);
    box-shadow: 0 0 20px #00f2fe;
}
.stDataFrame {
    background: rgba(0,0,0,0.3);
    border-radius: 12px;
    border: 1px solid #00f2fe;
}
.stDataFrame table {
    color: white !important;
}
.stDataFrame th {
    background: rgba(0,242,254,0.2) !important;
    color: #00f2fe !important;
}
</style>
<div class="wave-container"></div>
<div class="wave-container2"></div>
""", unsafe_allow_html=True)

# ==========================================
# DATABASE (SQLite) – unified
# ==========================================
DB_PATH = "pipeline_vault.db"


def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS opportunities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        track TEXT,
        title TEXT,
        organization TEXT,
        url TEXT,
        days_left INTEGER,
        moi_accepted TEXT,
        fully_funded TEXT,
        ethiopia_eligible TEXT,
        degree_required TEXT,
        sector TEXT,
        status TEXT,
        raw_description TEXT,
        deadline TEXT,
        is_recurring INTEGER DEFAULT 0,
        created_at TEXT,
        updated_at TEXT,
        source TEXT,
        user_description TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS master_profile (
        id INTEGER PRIMARY KEY,
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
        NarrativeCTA TEXT,
        GitHub TEXT
    )''')
    c.execute("SELECT COUNT(*) FROM master_profile")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO master_profile (
                Name, Email, Phone, Location, Education, Experience,
                Achievements, Skills, Certifications,
                NarrativeContext, NarrativeSolution, NarrativeCTA, GitHub
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            "ZEDAGIM TESFAYE TANTU",
            "zedagim100@gmail.com",
            "+251-924-700-390",
            "Jigjiga, Ethiopia",
            "Bachelor of Engineering (B.Eng.) — Water Resource & Irrigation Engineering (GPA: 3.87/4.00, Ranked in Top 1%)",
            "Water resource engineering, digital irrigation systems, satellite data analysis, climate prediction (drought/flood), Python/GIS/remote sensing.",
            "Developed 4 open-source Hydro-Agritech Digital Twin prototypes; Digitized FAO-56 Penman-Monteith; Automated multi-spectral satellite telemetry; Synthesized 20-year multi-spectral trends; Conducted 200+ field interviews; Contributed to prevention of 456+ human trafficking cases.",
            "Python, GIS, Remote Sensing, Machine Learning, Data Analysis, Project Management",
            "Certified in GeoAI, Digital Irrigation Systems",
            "Developing regions rely heavily on traditional agricultural systems that depend on guesswork, estimations, and seasonal rainfall variations without enough data arrays.",
            "Deploy spaceborne remote sensing arrays and validated Earth Observation data (NASA/ESA/FAO) to replace subjective observation with empirical ground-truth calibration profiles.",
            "I am ready to discuss my potential alignment with your goals at your representative's convenience. You can reach me at zedagim100@gmail.com or +251924700390. I respond within hours.",
            "digitalirrigation-lgtm.github.io/Zedagim10"
        ))
    conn.commit()
    conn.close()


init_db()


# ==========================================
# DATABASE HELPERS
# ==========================================
def fetch_all_opportunities():
    conn = get_db()
    df = pd.read_sql_query("SELECT * FROM opportunities ORDER BY id DESC", conn)
    conn.close()
    return df


def fetch_profile():
    conn = get_db()
    df = pd.read_sql_query("SELECT * FROM master_profile LIMIT 1", conn)
    conn.close()
    return df


def add_opportunity(data):
    conn = get_db()
    c = conn.cursor()
    cols = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    sql = f"INSERT INTO opportunities ({cols}) VALUES ({placeholders})"
    c.execute(sql, list(data.values()))
    conn.commit()
    conn.close()


def update_opportunity(opp_id, column, value):
    conn = get_db()
    c = conn.cursor()
    c.execute(f"UPDATE opportunities SET {column} = ? WHERE id = ?", (value, opp_id))
    conn.commit()
    conn.close()


def delete_opportunity(opp_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM opportunities WHERE id = ?", (opp_id,))
    conn.commit()
    conn.close()


# ==========================================
# CRAWLER / RSS FUNCTIONS (manual "Sync Now" button in sidebar)
# ==========================================
def fetch_rss_scholarships():
    if not HAS_FEEDPARSER:
        st.error("RSS sync is unavailable right now (the 'feedparser' package isn't installed on the server). Everything else still works.")
        return 0
    feeds = [
        "https://www.scholarshipportal.com/rss/",
        "https://www.opportunitydesk.org/feed/"
    ]
    count = 0
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                title = entry.title
                link = entry.link
                description = entry.get('description', '')
                deadline_match = re.search(r'(\d{4}-\d{2}-\d{2})', description, re.I)
                deadline_str = deadline_match.group(1) if deadline_match else (datetime.now() + timedelta(days=45)).strftime('%Y-%m-%d')
                try:
                    days_left = (datetime.strptime(deadline_str, '%Y-%m-%d').date() - datetime.now().date()).days
                except ValueError:
                    deadline_str = (datetime.now() + timedelta(days=45)).strftime('%Y-%m-%d')
                    days_left = 45
                opp = {
                    'category': 'Scholarship Platform',
                    'track': 'Fully Funded Scholarship',
                    'title': title[:100],
                    'organization': 'Scholarship Portal',
                    'url': link,
                    'days_left': days_left,
                    'moi_accepted': 'Yes',
                    'fully_funded': 'Yes',
                    'ethiopia_eligible': 'Yes',
                    'degree_required': 'Master',
                    'sector': 'Water, Climate, Agriculture',
                    'raw_description': description[:500],
                    'deadline': deadline_str,
                    'is_recurring': 0,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat(),
                    'source': 'RSS',
                    'status': 'Not Applied',
                    'user_description': ''
                }
                add_opportunity(opp)
                count += 1
        except Exception as e:
            st.warning(f"RSS error for {feed_url}: {e}")
    return count


def scrape_link(url):
    if not HAS_BS4:
        st.error("Link scraping is unavailable right now (the 'beautifulsoup4' package isn't installed on the server). Use 'Add New Opportunity' manually instead.")
        return None
    try:
        page = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(page.content, "html.parser")
        title = soup.title.string if soup.title else "Unknown"
        text = soup.get_text()
        deadline_match = re.search(r'(\d{4}-\d{2}-\d{2})', text, re.I)
        deadline_str = deadline_match.group(1) if deadline_match else (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        try:
            days_left = (datetime.strptime(deadline_str, '%Y-%m-%d').date() - datetime.now().date()).days
        except ValueError:
            deadline_str = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            days_left = 30
        return {
            'category': 'Scholarship',
            'track': 'Unknown',
            'title': (title or "Unknown")[:100],
            'organization': 'Extracted from page',
            'url': url,
            'days_left': days_left,
            'moi_accepted': 'Yes',
            'fully_funded': 'Yes',
            'ethiopia_eligible': 'Yes',
            'degree_required': 'Not specified',
            'sector': 'Various',
            'raw_description': text[:1000],
            'deadline': deadline_str,
            'is_recurring': 0,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'source': 'Web Scrape',
            'status': 'Not Applied',
            'user_description': ''
        }
    except Exception as e:
        st.error(f"Scraping error: {e}")
        return None


# ==========================================
# AI ALIGNMENT ENGINE
# (rule-based keyword + text-mining alignment between your master profile
#  and the pasted job/scholarship description — no external chatbot needed)
# ==========================================
def extract_keywords(text):
    stopwords = {'the', 'a', 'an', 'of', 'for', 'on', 'at', 'to', 'in', 'with', 'without', 'and', 'or', 'but',
                 'etc', 'from', 'by', 'as', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has',
                 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must',
                 'shall', 'can'}
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    return set(w for w in words if w not in stopwords)


def align_profile(profile, description):
    achievements = [a.strip() for a in profile['Achievements'].split(';') if a.strip()]
    skills = [s.strip() for s in profile['Skills'].split(',') if s.strip()]
    desc_tokens = extract_keywords(description or "")

    matched_ach = []
    for ach in achievements:
        score = len(extract_keywords(ach).intersection(desc_tokens))
        if score > 0:
            matched_ach.append((ach, score))
    matched_ach.sort(key=lambda x: x[1], reverse=True)
    matched_ach_text = '; '.join([a[0] for a in matched_ach[:3]]) if matched_ach else profile['Achievements']

    matched_skills = []
    for sk in skills:
        score = len(extract_keywords(sk).intersection(desc_tokens))
        if score > 0:
            matched_skills.append((sk, score))
    matched_skills.sort(key=lambda x: x[1], reverse=True)
    matched_skills_text = ', '.join([s[0] for s in matched_skills[:5]]) if matched_skills else profile['Skills']

    return matched_ach_text, matched_skills_text


def generate_cv(profile, description):
    matched_ach, matched_skills = align_profile(profile, description)
    return f"""===========================================================
CUSTOMIZED CV – ALIGNED TO TARGET
===========================================================
Name: {profile['Name']}
Email: {profile['Email']}
Phone: {profile['Phone']}
Location: {profile['Location']}
GitHub: {profile['GitHub']}

EDUCATION:
{profile['Education']}

EXPERIENCE:
{profile['Experience']}

ACHIEVEMENTS (aligned to this opportunity):
{matched_ach}

SKILLS (aligned to this opportunity):
{matched_skills}

CERTIFICATIONS:
{profile['Certifications']}
===========================================================
"""


def generate_cover_letter(profile, title, organization, description):
    matched_ach, matched_skills = align_profile(profile, description)
    ach_bullets = "\n".join(f"- {a}" for a in matched_ach.split('; ')) if matched_ach else ""
    return f"""===========================================================
COVER LETTER – {title}
===========================================================
{profile['Name']}
{profile['Email']} | {profile['Phone']}
{profile['Location']}

{datetime.now().strftime('%B %d, %Y')}

Dear {organization},

I am writing to express my strong interest in the {title} opportunity.
Your requirements emphasize: {(description or '')[:300]}...

I bring a unique combination of technical expertise and field experience that directly aligns with your needs:

{ach_bullets}

My technical skills in {matched_skills} have been honed through real-world projects, including:
{profile['Experience'][:300]}

{profile['NarrativeContext']}

{profile['NarrativeSolution']}

I am excited about the opportunity to contribute and would welcome the chance to discuss how my background can support your goals.

Sincerely,
{profile['Name']}
"""


def generate_motivation_letter(profile, title, description):
    matched_ach, matched_skills = align_profile(profile, description)
    return f"""===========================================================
MOTIVATION LETTER – {title}
===========================================================
{profile['Name']}
{profile['Email']} | {profile['Phone']}

Dear Selection Committee,

I am deeply motivated to pursue the {title} opportunity because it resonates with my core mission:

{profile['NarrativeContext']}

My key achievements align with your objectives:
{matched_ach}

My technical toolkit, including {matched_skills}, enables me to deliver impactful results.

{profile['NarrativeSolution']}

{profile['NarrativeCTA']}

Thank you for considering my application.

Warm regards,
{profile['Name']}
"""


# ==========================================
# STREAMLIT UI
# ==========================================
st.title("Scholarship & Job AI Dashboard")
st.markdown("Track opportunities, and instantly generate a CV, cover letter, and motivation letter aligned to your master profile.")

df = fetch_all_opportunities()
profile_df = fetch_profile()
profile = profile_df.iloc[0].to_dict() if not profile_df.empty else {}

with st.sidebar:
    st.header("Data Sync")
    if st.button("🔄 Sync RSS Feeds Now"):
        with st.spinner("Fetching RSS feeds..."):
            count = fetch_rss_scholarships()
            st.success(f"Added {count} new opportunities from RSS!")
            st.rerun()
    st.markdown("---")
    st.header("Quick Stats")
    if not df.empty:
        st.metric("Total Opportunities", len(df))
        st.metric("Scholarships", int(df['category'].str.contains('Scholarship', case=False, na=False).sum()))
        st.metric("Jobs", int(df['category'].str.contains('Job', case=False, na=False).sum()))

if df.empty:
    st.info("No opportunities yet. Add one manually, scrape from a link, or sync RSS feeds using the sidebar.")
else:
    def deadline_emoji(deadline):
        try:
            days = (datetime.strptime(deadline, '%Y-%m-%d').date() - datetime.now().date()).days
        except Exception:
            days = 999
        if days <= 10:
            return "🔴"
        elif days <= 30:
            return "🟡"
        return "🟢"

    df["alert"] = df["deadline"].apply(deadline_emoji)

    st.dataframe(
        df[["id", "title", "organization", "deadline", "alert", "status", "source"]],
        use_container_width=True,
        column_config={"id": "ID", "alert": "⚠️", "source": "Source"}
    )

    selected_id = st.selectbox("Select Opportunity ID", df["id"].tolist())
    if selected_id:
        row = df[df["id"] == selected_id].iloc[0]
        st.subheader(f"📌 {row['title']}")
        st.caption(f"Organization: {row['organization']} | Deadline: {row['deadline']} | Status: {row['status']}")

        saved_desc = row.get('user_description', '') or ''
        description = st.text_area(
            "Paste the job/scholarship description or requirements here",
            value=saved_desc,
            height=150,
            key=f"desc_{selected_id}"
        )

        st.markdown("#### Generate your application package")
        st.caption("This saves the description to this opportunity AND generates all 3 documents immediately.")

        if st.button("⚡ Save & Generate CV + Cover Letter + Motivation Letter", type="primary"):
            if not profile:
                st.error("Master profile not found. Please check your database.")
            elif not description.strip():
                st.warning("Please paste a job/scholarship description first.")
            else:
                update_opportunity(selected_id, "user_description", description)
                cv = generate_cv(profile, description)
                cover = generate_cover_letter(profile, row['title'], row['organization'], description)
                mot = generate_motivation_letter(profile, row['title'], description)

                st.session_state[f"cv_{selected_id}"] = cv
                st.session_state[f"cover_{selected_id}"] = cover
                st.session_state[f"mot_{selected_id}"] = mot
                st.success("Description saved and all 3 documents generated below.")

        safe_title = str(row['title']).replace(' ', '_').replace('/', '_')[:60]

        if f"cv_{selected_id}" in st.session_state:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.text_area("CV Preview", st.session_state[f"cv_{selected_id}"], height=200, key=f"cv_view_{selected_id}")
                st.download_button("⬇️ Download CV", data=st.session_state[f"cv_{selected_id}"],
                                    file_name=f"CV_{safe_title}.txt", key=f"cv_dl_{selected_id}")
            with col2:
                st.text_area("Cover Letter Preview", st.session_state[f"cover_{selected_id}"], height=200, key=f"cover_view_{selected_id}")
                st.download_button("⬇️ Download Cover Letter", data=st.session_state[f"cover_{selected_id}"],
                                    file_name=f"Cover_{safe_title}.txt", key=f"cover_dl_{selected_id}")
            with col3:
                st.text_area("Motivation Letter Preview", st.session_state[f"mot_{selected_id}"], height=200, key=f"mot_view_{selected_id}")
                st.download_button("⬇️ Download Motivation Letter", data=st.session_state[f"mot_{selected_id}"],
                                    file_name=f"Motivation_{safe_title}.txt", key=f"mot_dl_{selected_id}")

        st.markdown("---")
        col4, col5 = st.columns(2)
        with col4:
            status_options = ["Not Applied", "In Progress", "Applied", "Saved", "Rejected", "Accepted"]
            current_status = row['status'] if row['status'] in status_options else "Not Applied"
            new_status = st.selectbox("Update Status", status_options, index=status_options.index(current_status))
            if st.button("Update Status"):
                update_opportunity(selected_id, "status", new_status)
                st.success("Status updated!")
                st.rerun()
        with col5:
            if st.button("🗑️ Delete Opportunity"):
                delete_opportunity(selected_id)
                st.success("Deleted!")
                st.rerun()

with st.expander("➕ Add New Opportunity", expanded=False):
    with st.form("add_form"):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Title")
            org = st.text_input("Organization")
            url = st.text_input("URL (optional)")
        with col2:
            cat = st.selectbox("Category", ["Scholarship", "Job", "Fellowship", "Other"])
            deadline = st.date_input("Deadline", value=datetime.today().date() + timedelta(days=30))
            status = st.selectbox("Status", ["Not Applied", "In Progress", "Applied", "Saved"])
        description_input = st.text_area("Description (optional)", height=100)
        if st.form_submit_button("Add Opportunity"):
            if title and org:
                opp_data = {
                    'category': cat,
                    'track': '',
                    'title': title,
                    'organization': org,
                    'url': url or '',
                    'days_left': (deadline - datetime.today().date()).days,
                    'moi_accepted': 'Yes',
                    'fully_funded': 'Yes',
                    'ethiopia_eligible': 'Yes',
                    'degree_required': '',
                    'sector': '',
                    'status': status,
                    'raw_description': description_input[:500],
                    'deadline': deadline.strftime('%Y-%m-%d'),
                    'is_recurring': 0,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat(),
                    'source': 'Manual',
                    'user_description': description_input
                }
                add_opportunity(opp_data)
                st.success("Opportunity added!")
                st.rerun()
            else:
                st.warning("Title and Organization are required.")

with st.expander("🌐 Add Opportunity from Link", expanded=False):
    link = st.text_input("Paste opportunity link")
    if st.button("Scrape and Add"):
        if link:
            opp = scrape_link(link)
            if opp:
                add_opportunity(opp)
                st.success("Opportunity scraped and added!")
                st.rerun()
            else:
                st.error("Failed to scrape link. Check the URL or try manual entry.")

with st.expander("👤 Master Profile", expanded=False):
    if not profile_df.empty:
        st.dataframe(profile_df)
        st.caption("To edit your profile permanently, update the default values in app.py (search for 'INSERT INTO master_profile') and redeploy, or edit the pipeline_vault.db file directly with an external SQLite tool.")
    else:
        st.warning("No profile found. Please check your database.")

with st.expander("📊 Graphs", expanded=False):
    if not HAS_ALTAIR:
        st.warning("Graphs are unavailable right now (the 'altair' package isn't installed on the server). Everything else still works.")
    elif not df.empty:
        bar = alt.Chart(df).mark_bar().encode(
            x='category', y='count()', color='category'
        ).properties(title='Opportunities by Category')

        df_deadline = df.copy()
        df_deadline['deadline_dt'] = pd.to_datetime(df_deadline['deadline'], errors='coerce')
        df_deadline = df_deadline.dropna(subset=['deadline_dt'])
        if not df_deadline.empty:
            line = alt.Chart(df_deadline).mark_line(point=True).encode(
                x='deadline_dt:T', y='count()', color='category'
            ).properties(title='Deadline Distribution')
            st.altair_chart(bar | line, use_container_width=True)
        else:
            st.altair_chart(bar, use_container_width=True)
    else:
        st.info("No data to visualize.")

st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Powered by SQLite, Streamlit, and a keyword-alignment engine.")
