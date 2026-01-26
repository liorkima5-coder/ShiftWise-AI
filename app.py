import streamlit as st
import pandas as pd
from supabase import create_client, Client
import time
import io
import plotly.express as px  
from solver_engine import run_scheduler 

# ==========================================
# 1. הגדרות דף + עיצוב CSS (ללא סרגל צד)
# ==========================================
st.set_page_config(
    page_title="ShiftWise AI", 
    page_icon="logo.png", 
    layout="wide",
    initial_sidebar_state="collapsed" # הגדרה ראשונית למצב סגור
)

# הזרקת CSS להסתרת הסרגל ועיצוב יוקרתי
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Rubik:wght@300;400;500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Rubik', sans-serif;
        direction: rtl;
    }
    
    /* הסתרת כפתור הסרגל הצידי והסרגל עצמו */
    [data-testid="stSidebarNav"] {display: none;}
    [data-testid="collapsedControl"] {display: none;}
    section[data-testid="stSidebar"] {display: none;}
    
    .stApp {
        background-color: #f8f9fc;
    }
    
    /* עיצוב כרטיסים */
    div[data-testid="stDataFrame"], div.stForm, div[data-testid="stExpander"], div[data-testid="metric-container"] {
        background-color: #ffffff;
        padding: 24px;
        border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        border: 1px solid #edf2f7;
    }

    h1 { color: #1a202c; font-weight: 800; }
    h2, h3 { color: #2d3748; font-weight: 600; }

    /* כפתורים */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 12px;
        padding: 14px 32px;
        font-weight: 600;
        border: none;
        box-shadow: 0 4px 15px rgba(118, 75, 162, 0.3);
        transition: all 0.3s ease;
    }
    
    /* טאבים */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #ffffff;
        padding: 10px;
        border-radius: 50px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.03);
        display: inline-flex;
        flex-wrap: wrap;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 30px;
        padding: 8px 16px; 
        font-weight: 500;
        border: none;
        background-color: transparent;
        flex-grow: 1; 
        text-align: center;
    }
    .stTabs [aria-selected="true"] {
        background-color: #e2e8f0 !important;
        color: #2d3748 !important;
        font-weight: 700;
    }
    
    .stDataFrame { direction: rtl; }
    div[data-testid="stDataFrame"] div[role="grid"] { direction: rtl; }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    @media only screen and (max-width: 768px) {
        h1 { font-size: 28px !important; }
        div.stButton > button { width: 100%; }
    }
    
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. התחברות ל-Supabase
# ==========================================
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# קבועים
DAYS_ORDER = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"]
SHIFT_TYPES = ["בוקר", "צהריים", "ערב", "לילה"]
ROLES = ["מלצר", "טבח", "אחמ״ש", "ברמן", "שטיפה", "מארחת"]

# ==========================================
# 3. כותרת ראשית (כולל הלוגו והקרדיט)
# ==========================================
header_col1, header_col2 = st.columns([1, 4])

with header_col1:
    try:
        st.image("logo.png", width=120)
    except:
        pass

with header_col2:
    st.title("ShiftWise AI")
    st.caption("מערכת אופטימיזציה לניהול משמרות | פותח ע״י ליאור")

st.markdown("---")

# ==========================================
# 4. מדדים ונתונים
# ==========================================
try:
    count_emps = supabase.table("employees").select("id", count="exact").execute().count
    count_asses = supabase.table("schedule_assignments").select("id", count="exact").execute().count
    count_reqs = supabase.table("shift_requirements").select("id", count="exact").execute().count
except:
    count_emps, count_asses, count_reqs = 0, 0, 0

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("👥 עובדים", f"{count_emps}")
kpi2.metric("📅 משובצים", f"{count_asses}")
kpi3.metric("⚙️ דרישות", f"{count_reqs}")
kpi4.metric("🤖 מנוע", "פעיל", delta_color="off")

st.markdown("###")

# ==========================================
# 5. טאבים (הלוגיקה נשארה זהה לחלוטין)
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["👥 צוות", "⚙️ דרישות", "⛔ אילוצים", "🚀 לוח"])

# --- טאב 1: צוות ---
with tab1:
    col_manual, col_excel = st.columns(2)
    with col_manual:
        st.markdown("#### ➕ הוספת עובד")
        with st.form("new_emp", border=False):
            name = st.text_input("שם מלא")
            role = st.selectbox("תפקיד", ROLES)
            max_s = st.number_input("משמרות לשבוע", 1, 7, 5)
            if st.form_submit_button("שמור עובד", type="primary", use_container_width=True):
                if name:
                    supabase.table("employees").insert({"name": name, "role": role, "max_shifts": max_s}).execute()
                    st.toast(f"העובד {name} נוסף!", icon="✅")
                    time.sleep(1)
                    st.rerun()

    with col_excel:
        st.markdown("#### 📥 טעינת Excel")
        template_df = pd.DataFrame(columns=["name", "role", "max_shifts"])
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            template_df.to_excel(writer, index=False, sheet_name='Employees')
        c_down, c_up = st.columns([1, 2])
        c_down.download_button("תבנית", buffer.getvalue(), "template.xlsx", use_container_width=True)
        uploaded_file = c_up.file_uploader("upload", type=['xlsx'], label_visibility="collapsed")
        if uploaded_file:
            if st.button("טען קובץ", type="primary", use_container_width=True):
                try:
                    df_upload = pd.read_excel(uploaded_file)
                    records = df_upload.to_dict(orient='records')
                    supabase.table("employees").insert(records).execute()
                    st.toast(f"נטענו {len(records)} עובדים!", icon="🎉")
                    time.sleep(1)
                    st.rerun()
                except:
                    st.error("שגיאה בטעינה")

    data = supabase.table("employees").select("*").order("id").execute().data
    if data:
        st.markdown("#### 📋 רשימת עובדים")
        df = pd.DataFrame(data)
        st.dataframe(df[['name', 'role', 'max_shifts']], use_container_width=True, hide_index=True)
        with st.expander("🗑️ מחיקת עובד"):
            to_del = st.selectbox("בחר עובד להסרה", df['name'], label_visibility="collapsed")
            if st.button("מחק לצמיתות", type="secondary", use_container_width=True):
                eid = df[df['name']==to_del].iloc[0]['id']
                supabase.table("schedule_assignments").delete().eq("employee_id", eid).execute()
                supabase.table("availability").delete().eq("employee_id", eid).execute()
                supabase.table("employees").delete().eq("id", eid).execute()
                st.toast("נמחק!", icon="🗑️")
                time.sleep(1)
                st.rerun()

# --- טאב 2: דרישות ---
with tab2:
    st.markdown("#### ⚙️ תקן כוח אדם")
    defaults = {
        "בוקר": {"מארחת": 1, "מלצר": 2, "טבח": 1, "אחמ״ש": 1, "שטיפה": 1},
        "צהריים": {"מארחת": 1, "מלצר": 2, "טבח": 1, "אחמ״ש": 1, "שטיפה": 1},
        "ערב": {"מארחת": 2, "מלצר": 3, "ברמן": 1, "אחמ״ש": 1, "טבח": 2, "שטיפה": 1},
        "לילה": {"ברמן": 2, "מלצר": 4, "אחמ״ש": 1}
    }
    standard_requirements = {} 
    cols = st.columns(4)
    for i, shift_type in enumerate(SHIFT_TYPES):
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"**{shift_type}**")
                reqs_for_shift = {}
                for role in ROLES:
                    default_val = defaults.get(shift_type, {}).get(role, 0)
                    val = st.number_input(f"{role}", min_value=0, max_value=10, value=default_val, key=f"req_{shift_type}_{role}")
                    if val > 0: reqs_for_shift[role] = val
                standard_requirements[shift_type] = reqs_for_shift

    st.markdown("#### 🗓️ ימי פעילות")
    matrix_data = pd.DataFrame(False, index=DAYS_ORDER, columns=SHIFT_TYPES)
    edited_matrix = st.data_editor(matrix_data, use_container_width=True)

    if st.button("⚡ עדכן דרישות מערכת", type="primary", use_container_width=True):
        rows_to_insert = []
        for day in DAYS_ORDER:
            for shift in SHIFT_TYPES:
                if edited_matrix.at[day, shift]:
                    role_config = standard_requirements.get(shift, {})
                    for role, qty in role_config.items():
                        rows_to_insert.append({"day": day, "shift_type": shift, "role_needed": role, "quantity": qty})
        if rows_to_insert:
            supabase.table("shift_requirements").delete().neq("id", 0).execute()
            supabase.table("shift_requirements").insert(rows_to_insert).execute()
            st.toast("הדרישות עודכנו!", icon="💾")

# --- טאב 3: אילוצים ---
with tab3:
    st.markdown("#### ⛔ דיווח אילוצים")
    emps = supabase.table("employees").select("*").execute().data
    if emps:
        emp_map = {e['name']: e['id'] for e in emps}
        s_name = st.selectbox("בחר עובד:", list(emp_map.keys()))
        s_id = emp_map[s_name]
        with st.form("av_form", border=True):
            cols = st.columns(len(DAYS_ORDER))
            new_av = []
            for i, day in enumerate(DAYS_ORDER):
                with cols[i]:
                    st.markdown(f"**{day}**")
                    for shift in SHIFT_TYPES:
                        if st.checkbox(f"{shift}", key=f"{s_name}{day}{shift}"):
                            new_av.append({"employee_id": s_id, "day": day, "shift_type": shift, "is_available": False})
            if st.form_submit_button("שמור אילוצים", type="primary", use_container_width=True):
                supabase.table("availability").delete().eq("employee_id", s_id).execute()
                if new_av: supabase.table("availability").insert(new_av).execute()
                st.toast("נשמר!", icon="🔒")

# --- טאב 4: הלוח ---
with tab4:
    st.markdown("#### 🚀 הפקת סידור עבודה")
    if st.button("הפעל מנוע AI לשיבוץ", type="primary", use_container_width=True):
        with st.status("🤖 עובד על זה...") as status:
            if run_scheduler():
                status.update(label="הושלם!", state="complete")
                st.balloons()
                st.rerun()

    asses = supabase.table("schedule_assignments").select("*").execute().data
    all_e = supabase.table("employees").select("*").execute().data
    if asses and all_e:
        df_a = pd.DataFrame(asses)
        df_e = pd.DataFrame(all_e)
        merged = pd.merge(df_a, df_e, left_on="employee_id", right_on="id")
        merged['show'] = merged['name'] + " (" + merged['role_assigned'] + ")"
        piv = merged.groupby(['day', 'shift_type'])['show'].apply(lambda x: ", ".join(x)).unstack(fill_value="")
        st.dataframe(piv.reindex(index=DAYS_ORDER, columns=SHIFT_TYPES), use_container_width=True)
        
        # גרפים
        g1, g2 = st.columns(2)
        with g1:
            st.plotly_chart(px.bar(merged['name'].value_counts().reset_index(), x='name', y='count', title="עומס עובדים"), use_container_width=True)
        with g2:
            st.plotly_chart(px.pie(merged['role_assigned'].value_counts().reset_index(), names='role_assigned', values='count', title="תפקידים"), use_container_width=True)
