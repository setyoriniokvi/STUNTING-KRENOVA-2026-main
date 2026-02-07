import pandas as pd
import numpy as np
import streamlit as st
import sqlite3
from datetime import datetime as dt
import hashlib
from google import genai

# ========= INTEGRASI GEMINI AI
### ======= KONFIGURASI AI
try:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error(f"Konfigurasi AI gagal: {e}")
    client = None

### ======= FUNGSI ANALISIS AI
def get_ai_analysis(data_anak, status_z):
    prompt = f"""
    Anda adalah Pakar Gizi Anak (Pediatrician) Berstandar WHO. Berikan analisis mendalam berdasarkan data:
    - Nama: {data_anak['name']}
    - Usia: {data_anak['age']} bulan ({data_anak['sex']})
    - Skor Weight for Age: {status_z['waz_z']} ({status_z['waz_label']})
    - Skor Height for Age: {status_z['haz_z']} ({status_z['haz_label']})
    - Skor Weight for Height: {status_z['whz_z']} ({status_z['whz_label']})
    - Skor Head Circum for Age: {status_z['hcz_z']} ({status_z['hcz_label']})
    
        Anda adalah asisten pendukung skrining pertumbuhan anak di tingkat Posyandu.
    Peran Anda terbatas pada interpretasi hasil skrining antropometri berdasarkan standar WHO
    dan pemberian saran tindak lanjut awal yang bersifat edukatif dan non-medis.

    Anda bukan tenaga kesehatan dan tidak melakukan diagnosis stunting atau penyakit.
    Anda tidak memberikan rekomendasi pengobatan atau terapi medis
    Batasan tugas Anda:
    - Hanya menjelaskan makna hasil skrining pertumbuhan anak
    - Memberikan saran tindak lanjut awal yang bersifat umum dan non-medis
    - Mengarahkan kader untuk merujuk ke tenaga kesehatan bila ditemukan risiko

    Dilarang:
    - Menyatakan diagnosis stunting atau penyakit
    - Memberikan rekomendasi pengobatan, suplemen, atau terapi medis
    - Menggantikan peran tenaga kesehatan profesional
    Menyusun interpretasi hasil skrining secara ringkas, jelas, dan mudah dipahami kader
    2. Menjelaskan arti kombinasi indikator antropometri tersebut terhadap risiko pertumbuhan anak
    3. Menyampaikan hasil dalam bahasa non-teknis dan tidak menakutkan
    4. Menyusun saran tindak lanjut awal yang dapat dilakukan kader Posyandu
    format keluaran WAJIB sebagai berikut:

    1. Ringkasan Hasil Skrining
    (jelaskan kondisi pertumbuhan anak secara umum)

    2. Interpretasi Risiko
    (jelaskan apakah anak perlu pemantauan rutin, perhatian khusus, atau rujukan)

    3. Saran Tindak Lanjut Awal untuk Kader
    (berupa langkah umum seperti pemantauan ulang, edukasi orang tua, rujukan)

    4. Catatan Penting
    (tegaskan bahwa hasil ini bukan diagnosis dan perlu konfirmasi tenaga kesehatan)

    5. Tambahan: Gunakan bahasa yang mudah dipahami oleh ibu-ibu posyandu dan orang tua, karena di desa tidak semua memiliki akses ke pendidikan tinggi. Tidak menakut-nakuti dan tetap ramah.
"""
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"Oops. Gagal mendapatkan saran Gemini: {str(e)}"

# ========= DATABASE SETUP
def init_database():
    conn = sqlite3.connect('krenova_data.db')
    c = conn.cursor()
    
    # Tabel Users
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  role TEXT NOT NULL,
                  nama_lengkap TEXT)''')
    
    # Tabel Measurements
    c.execute('''CREATE TABLE IF NOT EXISTS measurements
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  tanggal_pengukuran DATE,
                  nama_anak TEXT,
                  usia_bulan INTEGER,
                  gender TEXT,
                  alamat TEXT,
                  berat_badan REAL,
                  tinggi_badan REAL,
                  lingkar_kepala REAL,
                  wfa_zscore REAL,
                  wfa_status TEXT,
                  hfa_zscore REAL,
                  hfa_status TEXT,
                  wfh_zscore REAL,
                  wfh_status TEXT,
                  hcfa_zscore REAL,
                  hcfa_status TEXT,
                  risiko_stunting_persen INTEGER,
                  status_stunting TEXT,
                  created_by TEXT,
                  tanggal_lahir DATE,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Migration for existing tables
    try:
        c.execute("SELECT tanggal_lahir FROM measurements LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE measurements ADD COLUMN tanggal_lahir DATE")

    
    # Insert default admin jika belum ada
    c.execute("SELECT * FROM users WHERE username='tumbuh'")
    if not c.fetchone():
        admin_pass = hashlib.sha256('12345'.encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, role, nama_lengkap) VALUES (?, ?, ?, ?)",
                  ('tumbuh', admin_pass, 'admin', 'Administrator'))
    
    # Insert default user jika belum ada
    c.execute("SELECT * FROM users WHERE username='user'")
    if not c.fetchone():
        user_pass = hashlib.sha256('user123'.encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, role, nama_lengkap) VALUES (?, ?, ?, ?)",
                  ('user', user_pass, 'user', 'User Biasa'))
    
    conn.commit()
    conn.close()

# ========= AUTHENTICATION FUNCTIONS
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_login(username, password):
    conn = sqlite3.connect('krenova_data.db')
    c = conn.cursor()
    hashed_pw = hash_password(password)
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, hashed_pw))
    user = c.fetchone()
    conn.close()
    return user

def save_measurement(data, z_scores, statuses, risk, status_stunting, username):
    conn = sqlite3.connect('krenova_data.db')
    c = conn.cursor()
    c.execute('''INSERT INTO measurements 
                 (tanggal_pengukuran, nama_anak, usia_bulan, gender, alamat, berat_badan, tinggi_badan, 
                  lingkar_kepala, wfa_zscore, wfa_status, hfa_zscore, hfa_status, wfh_zscore, 
                  wfh_status, hcfa_zscore, hcfa_status, risiko_stunting_persen, status_stunting, created_by, tanggal_lahir)

                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (data['date'], data['name'], data['age'], data['sex'], data['alamat'], data['weight'], data['height'],
               data['hc'], z_scores['wfa'], statuses['wfa'], z_scores['hfa'], statuses['hfa'],
               z_scores['wfh'], statuses['wfh'], z_scores['hcfa'], statuses['hcfa'],
               risk, status_stunting, username, data.get('birth_date')))

    conn.commit()
    conn.close()

def get_all_measurements():
    conn = sqlite3.connect('krenova_data.db')
    df = pd.read_sql_query("SELECT * FROM measurements ORDER BY created_at DESC", conn)
    conn.close()
    return df

def update_measurement(record_id, data, z_scores, statuses, risk, status_stunting):
    conn = sqlite3.connect('krenova_data.db')
    c = conn.cursor()
    c.execute('''UPDATE measurements 
                 SET tanggal_pengukuran=?, nama_anak=?, usia_bulan=?, gender=?, alamat=?, 
                     berat_badan=?, tinggi_badan=?, lingkar_kepala=?,
                     wfa_zscore=?, wfa_status=?, hfa_zscore=?, hfa_status=?, 
                     wfh_zscore=?, wfh_status=?, hcfa_zscore=?, hcfa_status=?,
                     risiko_stunting_persen=?, status_stunting=?, tanggal_lahir=?
                 WHERE id=?''',
              (data['date'], data['name'], data['age'], data['sex'], data['alamat'], 
               data['weight'], data['height'], data['hc'],
               z_scores['wfa'], statuses['wfa'], z_scores['hfa'], statuses['hfa'],
               z_scores['wfh'], statuses['wfh'], z_scores['hcfa'], statuses['hcfa'],
               risk, status_stunting, data.get('birth_date'), record_id))

    conn.commit()
    conn.close()

def delete_measurement(record_id):
    conn = sqlite3.connect('krenova_data.db')
    c = conn.cursor()
    c.execute('DELETE FROM measurements WHERE id=?', (record_id,))
    conn.commit()
    conn.close()

def get_measurement_by_id(record_id):
    conn = sqlite3.connect('krenova_data.db')
    c = conn.cursor()
    c.execute('SELECT * FROM measurements WHERE id=?', (record_id,))
    result = c.fetchone()
    conn.close()
    return result

# Initialize database
init_database()

# ========= SESSION STATE
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = 'pengguna_umum'
if 'role' not in st.session_state:
    st.session_state.role = 'user'
if 'nama_lengkap' not in st.session_state:
    st.session_state.nama_lengkap = 'Pengguna Umum'
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = 'public'  # public atau admin
if 'edit_record_id' not in st.session_state:
    st.session_state.edit_record_id = None
if 'delete_confirm_id' not in st.session_state:
    st.session_state.delete_confirm_id = None

# ========= BACA DATA
wfa = pd.read_csv("wfa-all.csv")
hfa = pd.read_csv("lhfa-all.csv")
wfh = pd.read_csv("wfh-all.csv")
hcfa = pd.read_csv("hcfa-all.csv")

# ========== FUNGSI Z-Score
def who_zscore(x, L, M, S):
    if L == 0:
        return np.log(x/M)/S
    return ((x / M) ** L - 1) / (L * S)

# ========== FUNGSI INDIKATOR
## BB Terhadap Usia
def calc_wfa(age, sex, weight):
    ref = wfa[
        (wfa['Usia'] == age) &
        (wfa['Gender'] == sex)
    ]
    if ref.empty:
        return None

    L, M, S = ref[["L", "M", "S"]].values[0]
    return who_zscore(weight, L, M, S)

## TB Terhadap Usia
def calc_hfa(age, sex, height):
    ref = hfa[
        (hfa['Usia'] == age) &
        (hfa['Gender'] == sex)
        ]
    if ref.empty:
        return None

    L, M, S = ref[["L", "M", "S"]].values[0]
    return who_zscore(height, L, M, S)

## BB Terhadap Panjang/Tinggi Badan
def calc_wfh(age, sex, weight, body_cm):
    # Tentukan tipe pengukuran berdasarkan usia
    m_type = "Length" if age < 24 == "Height" else "Height"

    rounded_height = round(body_cm * 2) / 2  # Pembulatan ke 0.5 terdekat

    # Filter data WHO sesuai kolom dataset kamu
    ref = wfh[
        (wfh["Gender"] == sex) &
        (wfh["Pengukuran"] == m_type) &
        (wfh["Tinggi"] == rounded_height)
    ]

    if ref.empty:
        return None

    L, M, S = ref[["L", "M", "S"]].values[0]
    return who_zscore(weight, L, M, S)

## LK Berdasarkan Usia
def calc_hcfa(age, sex, hc):
    ref = hcfa[
        (hcfa['Usia'] == age) &
        (hcfa['Gender'] == sex)
    ]
    if ref.empty:
        return None
    L, M, S = ref[["L", "M", "S"]].values[0]
    return who_zscore(hc, L, M, S)

## ======= STATUS STUNTING (HFA)
def stunting_status(z):
    if z < -2:
        return "Berisiko Stunting"
    return "Tidak Berisiko Stunting"

## ======= EVALUASI GIZI
### Berat/Usia
def wfa_status(z):
    
    if z is None:
        return None
    elif z < -3 :
        return "Berat Anak Sangat Kurang\n(Z-Score normal -2 s/d +2)"
    elif z < -2:
        return "Berat Anak Kurang\n(Z-Score normal -2 s/d +2)"
    elif z > 3:
        return "Anak Obesitas\n(Z-Score normal -2 s/d +2)"
    elif z > 2:
        return "Berat Badan Anak Berlebih\n(Z-Score normal -2 s/d +2)"
    else:
        return "Berat Badan Anak Normal\n(Z-Score normal -2 s/d +2)"

### Tinggi/Usia
def hfa_status(z):
    if z is None:
        return None
    elif z < -3:
        return "Anak Sangat Pendek\n(Z-Score normal -2 s/d +3)"
    elif z < -2:
        return "Anak Pendek\n(Z-Score normal -2 s/d +3)"
    elif z > 3:
        return "Anak Tinggi\n(Z-Score normal -2 s/d +3)"
    else:
        return "Tinggi Anak Normal\n(Z-Score normal -2 s/d +3)"

### Berat/Tinggi
def wfh_status(z):
    if z is None:
        return None
    elif z < -3:
        return "Gizi Anak Buruk\n(Z-Score normal -2 s/d +2)"
    elif z < -2:
        return "Gizi Anak Kurang\n(Z-Score normal -2 s/d +2)"
    elif z > 3:
        return  "Anak Obesitas\n(Z-Score normal -2 s/d +2)"
    elif z > 2:
        return "Anak Overweight\n(Z-Score normal -2 s/d +2)"
    else:
        return "Gizi Anak Baik/Normal\n(Z-Score normal -2 s/d +2)"

### Lingkar Kepala/Usia
def hcaf_status(z):
    if z is None:
        return None
    elif z < -2:
        return "Anak Terindikasi Microcephaly. Berisiko keterlambatan kognitif, motorik, dan belajar jangka panjang, serta gangguan neurologis\n(Z-Score normal -2 s/d +2)"
    elif z > 2:
        return "Anak Terindikasi Macrocephaly. Indikasi adanya hydrocephalus atau masalah genetik, memerlukan skrining dini\n(Z-Score normal -2 s/d +2)"
    else:
        return "Lingkar Kepala Anak Normal\n(Z-Score normal -2 s/d +2)"

## ======= SAFE ROUND
def safe_round(x):
    return round(x, 2) if x is not None else None

## ======= RISK STUNTING (%)
def stunting_risk_percent(hfa, wfa):
    score = 0

    if hfa < -2:
        score += 60
    if wfa < -2:
        score += 40
    return min(score, 100)


## ========= STREAMLIT
st.set_page_config(page_title="SI Tumbuh")

# Custom CSS untuk mempercantik
st.markdown("""
<style>
    /* Background colors */
    .main {
        background-color: #FFFFF0;
    }
    [data-testid="stSidebar"] {
        background-color: #DBE4C9;
    }
    [data-testid="stSidebar"] .element-container {
        color: #1a1a1a;
    }
    [data-testid="stSidebar"] * {
        color: #1a1a1a !important;
    }
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] h4 {
        color: #8AA624 !important;
        font-weight: 700 !important;
    }
    
    /* Radio buttons in sidebar */
    [data-testid="stSidebar"] .stRadio > label {
        background-color: #8AA624;
        color: #FFFFFF;
        padding: 0.6rem;
        border-radius: 8px;
        font-weight: 700;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
    }
    [data-testid="stSidebar"] .stRadio > div {
        background-color: #FFFFFF;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.15);
        border: 2px solid #8AA624;
    }
    [data-testid="stSidebar"] .stRadio label {
        background-color: transparent !important;
        color: #1a1a1a !important;
        padding: 0.4rem !important;
        font-weight: 600 !important;
    }
    
    .main-header {
        font-size: 2.5rem;
        color: #8AA624;
        text-align: center;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #555;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #8AA624 0%, #6d851d 100%);
        color: #FFFFFF;
        font-weight: 700;
        border-radius: 10px;
        padding: 0.6rem 1.2rem;
        border: 2px solid #FEA405;
        box-shadow: 0 3px 6px rgba(0,0,0,0.2);
        text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #6d851d 0%, #5a6e18 100%);
        box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        transform: translateY(-1px);
    }
    .result-box {
        background-color: #FFFFFF;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 6px solid #8AA624;
        margin: 1rem 0;
        box-shadow: 0 3px 8px rgba(0,0,0,0.15);
        border: 2px solid #DBE4C9;
    }
    .metric-card {
        background: linear-gradient(135deg, #8AA624 0%, #6d851d 100%);
        padding: 1.2rem;
        border-radius: 10px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        border: 3px solid #FEA405;
        margin: 0.5rem 0;
    }
    .metric-card h4 {
        color: #FFFFFF;
        font-weight: 700;
        margin-bottom: 0.8rem;
        font-size: 1.1rem;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
    }
    .metric-card p {
        color: #FFFFFF;
        font-weight: 500;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
    }
    
    /* Form inputs - lebih kontras */
    .stTextInput>div>div>input,
    .stNumberInput>div>div>input,
    .stDateInput>div>div>input {
        background-color: #FFF9E6 !important;
        border: 3px solid #8AA624 !important;
        border-radius: 8px;
        padding: 0.6rem !important;
        color: #000000 !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
    }
    .stTextInput>div>div>input::placeholder {
        color: #666666 !important;
        opacity: 0.7;
    }
    .stSelectbox>div>div>div {
        background-color: #FFF9E6 !important;
        border: 3px solid #8AA624 !important;
        border-radius: 8px;
    }
    .stSelectbox>div>div>div>div {
        color: #000000 !important;
        font-weight: 600 !important;
    }
    .stTextInput label,
    .stNumberInput label,
    .stDateInput label,
    .stSelectbox label {
        color: #000000 !important;
        font-weight: 800 !important;
        font-size: 1.15rem !important;
        text-shadow: 1px 1px 2px rgba(255,255,255,0.8);
        margin-bottom: 0.4rem !important;
    .stTextInput > label > div,
    .stNumberInput > label > div,
    .stDateInput > label > div,
    .stSelectbox > label > div {
        color: #000000 !important;
        font-weight: 800 !important;
        font-size: 1.15rem !important;
    }
    
    /* Headers in content */
    h1, h2, h3 {
        color: #8AA624;
        font-weight: 700;
    }
    h1 {
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    h2, h3 {
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }
    
    /* Info boxes */
    .stAlert {
        background-color: #FFF9E6 !important;
        border: 3px solid #8AA624 !important;
        border-radius: 10px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    }
    .stAlert > div {
        color: #1a1a1a !important;
        font-weight: 500;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background-color: #FFF9E6 !important;
        border: 3px solid #8AA624 !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        color: #1a1a1a !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Delete button */
    button[kind="secondary"] {
        background: linear-gradient(135deg, #dc3545 0%, #c82333 100%) !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        border: 2px solid #a71d2a !important;
        box-shadow: 0 3px 6px rgba(0,0,0,0.2) !important;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.2) !important;
    }
    button[kind="secondary"]:hover {
        background: linear-gradient(135deg, #c82333 0%, #a71d2a 100%) !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.3) !important;
    }
</style>
""", unsafe_allow_html=True)

# ========= MAIN APP
# Header dengan info user atau tombol login admin
if st.session_state.view_mode == 'public':
    # Mode Publik - Tampilkan header dengan tombol login admin
    col1, col2 = st.columns([4, 1])
    with col1:
        st.image("header situmbuh.png")
        # st.markdown(f"<h1 class='main-header'> SI Tumbuh</h1>", unsafe_allow_html=True)
        # st.markdown("<p class='sub-header'>Berdasarkan Standar WHO</p>", unsafe_allow_html=True)
    with col2:
        st.write("")
        st.write("")
        if st.button(" Login Admin", use_container_width=True):
            st.session_state.show_login_modal = True
            st.rerun()
else:
    # Mode Admin - Tampilkan header dengan info user
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        # st.markdown(f"<h1 class='main-header'> SI Tumbuh</h1>", unsafe_allow_html=True)
        st.image("header situmbuh.png")
    with col2:
        st.write(f"**{st.session_state.nama_lengkap}**")
        st.caption(f"Role: {st.session_state.role.upper()}")
    with col3:
        if st.button(" Logout"):
            st.session_state.logged_in = False
            st.session_state.username = 'pengguna_umum'
            st.session_state.role = 'user'
            st.session_state.nama_lengkap = 'Pengguna Umum'
            st.session_state.view_mode = 'public'
            if 'show_login_modal' in st.session_state:
                del st.session_state.show_login_modal
            st.rerun()

# Login Modal (Popup)
if 'show_login_modal' in st.session_state and st.session_state.show_login_modal:
    with st.container():
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("###  Login Admin")
            
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="Masukkan username")
                password = st.text_input("Password", type="password", placeholder="Masukkan password")
                col_a, col_b = st.columns(2)
                with col_a:
                    submit = st.form_submit_button("Login", use_container_width=True)
                with col_b:
                    cancel = st.form_submit_button("Batal", use_container_width=True)
                
                if submit:
                    user = verify_login(username, password)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.username = user[1]
                        st.session_state.role = user[3]
                        st.session_state.nama_lengkap = user[4]
                        st.session_state.view_mode = 'admin'
                        del st.session_state.show_login_modal
                        st.success(f"Selamat datang, {user[4]}!")
                        st.rerun()
                    else:
                        st.error("Username atau password salah!")
                
                if cancel:
                    del st.session_state.show_login_modal
                    st.rerun()
        st.markdown("---")
    st.stop()

st.markdown("---")

# Sidebar Navigation
st.sidebar.title(" Menu Navigasi")

if st.session_state.view_mode == 'public':
    st.sidebar.info(" Mode: Akses Publik\n\nAnda dapat menggunakan fitur skrining dan melihat panduan pengukuran.\n\nLogin sebagai admin untuk mengakses database.")
else:
    st.sidebar.markdown(f"**Logged in as:** {st.session_state.username}")

menu_options = [" Skrining Balita", " Cara Pengukuran", " Profile"]
if st.session_state.view_mode == 'admin' and st.session_state.role == 'admin':
    menu_options.append(" Database (Admin)")
    
page = st.sidebar.radio("Pilih Menu:", menu_options)

# ========= ADMIN DATABASE PAGE
if page == " Database (Admin)" and st.session_state.view_mode == 'admin' and st.session_state.role == 'admin':
    st.title(" Database Hasil Pengukuran")
    st.markdown("Dashboard untuk melihat semua data pengukuran yang telah direkam")
    
    df = get_all_measurements()
    
    if not df.empty:
        # Statistik
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Pengukuran", len(df))
        with col2:
            stunting_count = len(df[df['status_stunting'] != 'Tidak Berisiko Stunting'])
            st.metric("Risiko Stunting", stunting_count)
        with col3:
            avg_age = df['usia_bulan'].mean()
            st.metric("Rata-rata Usia", f"{avg_age:.1f} bulan")
        with col4:
            avg_risk = df['risiko_stunting_persen'].mean()
            st.metric("Rata-rata Risiko", f"{avg_risk:.1f}%")
        
        st.markdown("---")
        
        # Visualisasi Diagram Status Stunting
        st.subheader(" Diagram Persentase Status Stunting")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Pie Chart - Status Stunting
            status_counts = df['status_stunting'].value_counts()
            
            # Create data for pie chart
            import plotly.graph_objects as go
            
            colors = {
                'Tidak Berisiko Stunting': '#8AA624',
                'Berisiko Stunting': '#FEA405'
            }
            
            fig_pie = go.Figure(data=[go.Pie(
                labels=status_counts.index,
                values=status_counts.values,
                marker=dict(colors=[colors.get(label, '#999') for label in status_counts.index]),
                hole=.3,
                textposition='auto',
                textinfo='label+percent+value'
            )])
            
            fig_pie.update_layout(
                title="Distribusi Status Stunting",
                showlegend=True,
                height=400
            )
            
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            # Bar Chart - Perbandingan
        #     total_anak = len(df)
        #     berisiko = len(df[df['status_stunting'] != 'Tidak Berisiko Stunting'])
        #     tidak_berisiko = total_anak - berisiko
            
        #     persentase_berisiko = (berisiko / total_anak * 100) if total_anak > 0 else 0
        #     persentase_tidak_berisiko = (tidak_berisiko / total_anak * 100) if total_anak > 0 else 0
            
        #     fig_bar = go.Figure(data=[
        #         go.Bar(
        #             x=['Tidak Berisiko', 'Berisiko Stunting'],
        #             y=[tidak_berisiko, berisiko],
        #             text=[f'{tidak_berisiko}<br>({persentase_tidak_berisiko:.1f}%)', 
        #                   f'{berisiko}<br>({persentase_berisiko:.1f}%)'],
        #             textposition='auto',
        #             marker=dict(color=['#8AA624', '#FEA405'])
        #         )
        #     ])
            
        #     fig_bar.update_layout(
        #         title="Perbandingan Risiko Stunting",
        #         xaxis_title="Status",
        #         yaxis_title="Jumlah Anak",
        #         showlegend=False,
        #         height=400
        #     )
            
        #     st.plotly_chart(fig_bar, use_container_width=True)
        
        # st.markdown("---")
        
            if 'alamat' in df.columns:
                # Hitung statistik per alamat
                alamat_stats = df.groupby('alamat').agg(
                    total_anak=('id', 'count'),
                    berisiko_stunting=('status_stunting', lambda x: (x != 'Tidak Berisiko Stunting').sum())
                ).reset_index()

                alamat_stats['persentase'] = (
                    alamat_stats['berisiko_stunting'] / alamat_stats['total_anak'] * 100
                ).round(1)

                # Bar Chart
                fig_bar = go.Figure(data=[
                    go.Bar(
                        x=alamat_stats['alamat'],
                        y=alamat_stats['berisiko_stunting'],
                        text=alamat_stats['persentase'].astype(str) + '%',
                        textposition='auto',
                        marker=dict(color='#FEA405')
                    )
                ])

                fig_bar.update_layout(
                    title="Perbandingan Risiko Stunting per Dukuh",
                    xaxis_title="Alamat",
                    yaxis_title="Jumlah Anak Berisiko Stunting",
                    height=400
                )

                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Kolom 'alamat' tidak ditemukan dalam data.")
                
        # Statistik per Daerah
        st.subheader(" Statistik Risiko Stunting per Daerah")
        if 'alamat' in df.columns:
            alamat_stats = df.groupby('alamat').agg({
                'id': 'count',
                'status_stunting': lambda x: (x != 'Tidak Berisiko Stunting').sum(),
                'risiko_stunting_persen': 'mean'
            }).rename(columns={
                'id': 'Total Anak',
                'status_stunting': 'Berisiko Stunting',
                'risiko_stunting_persen': 'Rata-rata Risiko (%)'
            }).sort_values('Berisiko Stunting', ascending=False)
            
            alamat_stats['Persentase Risiko'] = (alamat_stats['Berisiko Stunting'] / alamat_stats['Total Anak'] * 100).round(1)
            st.dataframe(alamat_stats, use_container_width=True)
        
        st.markdown("---")
        
        # Filter
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            filter_gender = st.selectbox("Filter Gender", ["Semua", "L", "P"])
        with col2:
            filter_status = st.selectbox("Filter Status", 
                ["Semua", "Tidak Berisiko Stunting", "Berisiko Stunting"])
        with col3:
            unique_alamat = ["Semua"] + sorted(df['alamat'].dropna().unique().tolist()) if 'alamat' in df.columns else ["Semua"]
            filter_alamat = st.selectbox("Filter Alamat", unique_alamat)
        with col4:
            search_name = st.text_input("Cari Nama Anak", "")
        
        # Apply filters
        filtered_df = df.copy()
        if filter_gender != "Semua":
            filtered_df = filtered_df[filtered_df['gender'] == filter_gender]
        if filter_status != "Semua":
            filtered_df = filtered_df[filtered_df['status_stunting'] == filter_status]
        if filter_alamat != "Semua" and 'alamat' in df.columns:
            filtered_df = filtered_df[filtered_df['alamat'] == filter_alamat]
        if search_name:
            filtered_df = filtered_df[filtered_df['nama_anak'].str.contains(search_name, case=False, na=False)]
        
        st.markdown("---")
        
        # Form Edit Data
        if st.session_state.edit_record_id is not None:
            record = get_measurement_by_id(st.session_state.edit_record_id)
            if record:
                st.subheader(" Edit Data Pengukuran")
                
                with st.form("edit_form"):
                    col1, col2 = st.columns(2)

                    raw_birth_date = record[-1] 
        
                    try:
                        if raw_birth_date:
                            # Pastikan dikonversi ke objek date
                            birth_date_val = pd.to_datetime(raw_birth_date).date()
                        else:
                            birth_date_val = dt.now().date()
                    except:
                        birth_date_val = dt.now().date()
                    
                    with col1:
                        edit_date = st.date_input("Tanggal Pengukuran", value=pd.to_datetime(record[1]).date())
                        edit_name = st.text_input("Nama Anak", value=record[2])
                        # edit_alamat = st.text_input("Alamat/Desa", value=record[5])
                        edit_alamat = st.selectbox("Alamat Dukuh", ["Karangasem", "Bentak", "Gonggangan", "Sukolelo", "Pijinan"])
                        edit_age = st.number_input("Usia (bulan)", min_value=0, max_value=60, value=record[3])
                        edit_sex = st.selectbox("Jenis Kelamin", ["L", "P"], 
                                              index=0 if record[4] == "L" else 1,
                                              format_func=lambda x: "Laki-laki" if x == "L" else "Perempuan")
                    
                    with col2:
                        edit_weight = st.number_input("Berat Badan (kg)", min_value=0.0, max_value=50.0, 
                                                     value=float(record[6]), step=0.1, format="%.1f")
                        edit_height = st.number_input("Tinggi Badan (cm)", min_value=0.0, max_value=150.0, 
                                                     value=float(record[7]), step=0.1, format="%.1f")
                        edit_hc = st.number_input("Lingkar Kepala (cm)", min_value=0.0, max_value=60.0, 
                                                 value=float(record[8]), step=0.1, format="%.1f")
                        
                        edit_birth_date = st.date_input("Tanggal Lahir", value=birth_date_val)
                    
                    col_submit, col_cancel = st.columns(2)
                    with col_submit:
                        submit_edit = st.form_submit_button(" Simpan Perubahan", use_container_width=True)
                    with col_cancel:
                        cancel_edit = st.form_submit_button(" Batal", use_container_width=True)
                    
                    if submit_edit:
                        # Hitung ulang Z-Scores
                        edit_data = {
                            "date": edit_date,
                            "name": edit_name,
                            "alamat": edit_alamat,
                            "age": int(edit_age),
                            "sex": edit_sex,
                            "weight": edit_weight,
                            "height": edit_height,
                            "hc": edit_hc,
                            "birth_date": edit_birth_date
                        }

                        
                        waz_z = calc_wfa(edit_data["age"], edit_data["sex"], edit_data["weight"])
                        waz_label = wfa_status(waz_z)
                        haz_z = calc_hfa(edit_data["age"], edit_data["sex"], edit_data["height"])
                        haz_label = hfa_status(haz_z)
                        whz_z = calc_wfh(edit_data["age"], edit_data["sex"], edit_data["weight"], edit_data["height"])
                        whz_label = wfh_status(whz_z)
                        hcz_z = calc_hcfa(edit_data["age"], edit_data["sex"], edit_data["hc"])
                        hcz_label = hcaf_status(hcz_z)
                        
                        risk = stunting_risk_percent(haz_z, waz_z) if haz_z and waz_z else None
                        status = stunting_status(haz_z) if haz_z else None
                        
                        WFA = safe_round(waz_z)
                        HFA = safe_round(haz_z)
                        WFH = safe_round(whz_z)
                        HCFA = safe_round(hcz_z)
                        
                        z_scores = {'wfa': WFA, 'hfa': HFA, 'wfh': WFH, 'hcfa': HCFA}
                        statuses = {'wfa': waz_label, 'hfa': haz_label, 'wfh': whz_label, 'hcfa': hcz_label}
                        
                        update_measurement(st.session_state.edit_record_id, edit_data, z_scores, statuses, risk, status)
                        st.success(" Data berhasil diupdate!")
                        st.session_state.edit_record_id = None
                        st.rerun()
                    
                    if cancel_edit:
                        st.session_state.edit_record_id = None
                        st.rerun()
                
                st.markdown("---")
        
        # Konfirmasi Delete
        if st.session_state.delete_confirm_id is not None:
            st.warning(" Apakah Anda yakin ingin menghapus data ini?")
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button(" Ya, Hapus", use_container_width=True):
                    delete_measurement(st.session_state.delete_confirm_id)
                    st.success(" Data berhasil dihapus!")
                    st.session_state.delete_confirm_id = None
                    st.rerun()
            with col2:
                if st.button(" Batal", use_container_width=True):
                    st.session_state.delete_confirm_id = None
                    st.rerun()
            st.markdown("---")
        
        # Display table

        st.subheader(f" Data Pengukuran ({len(filtered_df)} records)")
        
        # Format display columns
        display_cols = ['id', 'tanggal_pengukuran', 'nama_anak', 'usia_bulan', 'gender']
        display_names = ['ID', 'Tanggal', 'Nama', 'Usia (bln)', 'Gender']
        
        if 'alamat' in filtered_df.columns:
            display_cols.append('alamat')
            display_names.append('Alamat')
            
        if 'tanggal_lahir' in filtered_df.columns:
            display_cols.append('tanggal_lahir')
            display_names.append('Tgl Lahir')

        
        display_cols.extend([
            'berat_badan', 'tinggi_badan', 'lingkar_kepala',
            'wfa_zscore', 'hfa_zscore', 'wfh_zscore', 'hcfa_zscore',
            'risiko_stunting_persen', 'status_stunting', 'created_by'
        ])
        display_names.extend([
            'BB (kg)', 'TB (cm)', 'LK (cm)',
            'WFA Z', 'HFA Z', 'WFH Z', 'HCFA Z',
            'Risiko %', 'Status', 'Oleh'
        ])
        
        display_df = filtered_df[display_cols].copy()
        display_df.columns = display_names
        
        st.dataframe(display_df, use_container_width=True, height=400)
        
        st.markdown("---")
        
        # Aksi Edit dan Delete dengan input ID
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            record_id_to_edit = st.number_input("Masukkan ID untuk Edit", min_value=0, step=1, value=0, key="id_edit")
            if st.button(" Edit Data", use_container_width=True):
                if record_id_to_edit > 0:
                    st.session_state.edit_record_id = record_id_to_edit
                    st.rerun()
                else:
                    st.warning("Masukkan ID yang valid")
        
        with col2:
            record_id_to_delete = st.number_input("Masukkan ID untuk Hapus", min_value=0, step=1, value=0, key="id_delete")
            if st.button(" Hapus Data", use_container_width=True, type="secondary"):
                if record_id_to_delete > 0:
                    st.session_state.delete_confirm_id = record_id_to_delete
                    st.rerun()
                else:
                    st.warning("Masukkan ID yang valid")
        
        st.markdown("---")
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label=" Download Data (CSV)",
            data=csv,
            file_name=f"data_stunting_{dt.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )
    
    else:
        st.info("Belum ada data pengukuran yang tersimpan.")

# ========= CARA PENGUKURAN PAGE
elif page == " Cara Pengukuran":
    # st.image("header situmbuh.png", width=400)
    st.title(" Panduan Cara Pengukuran Antropometri Balita")
    st.info(" **Referensi:** Akun Youtube @direktoratYanKesga")
    st.video('https://youtu.be/D-_JimQkBuA?si=Un2gdqlYUfy1fTQ6')
    st.markdown("---")

# ========= SKRINING GIZI PAGE
elif page == " Skrining Balita":
    # col1, col2 = st.columns([2, 1])
    # with col1:
    st.title("Skrining Pertumbuhan & Status Gizi Balita")
    st.markdown("Silakan masukkan hasil pengukuran yang telah dilakukan dengan tepat!")
    
    st.markdown("---")
    
    # Form Input dengan 2 kolom
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader(" Data Balita")
        date = st.date_input("Tanggal Pengukuran", value=None)
        name = st.text_input("Nama Anak", placeholder="Masukkan nama lengkap anak")
        # alamat = st.text_input("Alamat/Desa", placeholder="Contoh: Desa Slogo, Kec. Tanon")
        alamat = st.selectbox("Alamat Dukuh", ["Karangasem", "Bentak", "Gonggangan", "Sukolelo", "Pijinan"])
        
        birth_date = st.date_input("Tanggal Lahir Anak", value=None)
        
        # Auto-calculate age if birth_date is set
        age_val = 0
        if birth_date:
            today = dt.now().date()
            if birth_date <= today:
                # Calculate age in months
                age_val = (today.year - birth_date.year) * 12 + (today.month - birth_date.month)
                # Adjust if day is before birth day
                if today.day < birth_date.day:
                    age_val -= 1
                if age_val < 0: age_val = 0
        
        if birth_date:
            if age_val > 60:
                st.error(f"Usia terdeteksi {age_val} bulan. Sistem ini khusus untuk balita (0-60 bulan)")
                input_age_val = 60
            else:
                st.info(f"Usia Terhitung: {age_val} bulan")
                input_age_val = age_val
        
        if birth_date:
            # st.info(f"Usia Terhitung: **{age_val} bulan**")
            age = st.number_input("Usia (bulan)", min_value=0, max_value=60, step=1, value=input_age_val)
        else:
            age = st.number_input("Usia (bulan)", min_value=0, max_value=60, step=1, value=0)
            
        sex = st.selectbox("Jenis Kelamin", ["L", "P"], format_func=lambda x: "Laki-laki" if x == "L" else "Perempuan")

    
    with col2:
        st.subheader(" Hasil Pengukuran")
        weight = st.number_input("Berat Badan (kg)", min_value=0.0, max_value=50.0, step=0.1, format="%.1f")
        height = st.number_input("Panjang/Tinggi Badan (cm)", min_value=0.0, max_value=150.0, step=0.1, format="%.1f")
        hc = st.number_input("Lingkar Kepala (cm)", min_value=0.0, max_value=60.0, step=0.1, format="%.1f")
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        analyze_button = st.button(" Analisis Data", type="primary", use_container_width=True)
    
    if analyze_button:
        if not name or not alamat or age == 0 or weight == 0 or height == 0 or hc == 0:
            st.error(" Mohon lengkapi semua data pengukuran!")
        else:
            data = {
                "date": date,
                "name": name,
                "alamat": alamat,
                "age": int(age),
                "sex": sex,
                "weight": weight,
                "height": height,
                "hc": hc,
                "birth_date": birth_date
            }


            # Hitung Z-Scores
            waz_z = calc_wfa(data["age"], data["sex"], data["weight"])
            waz_label = wfa_status(waz_z)
            haz_z = calc_hfa(data["age"], data["sex"], data["height"])
            haz_label = hfa_status(haz_z)
            whz_z = calc_wfh(data["age"], data["sex"], data["weight"], data["height"])
            whz_label = wfh_status(whz_z)
            hcz_z = calc_hcfa(data["age"], data["sex"], data["hc"])
            hcz_label = hcaf_status(hcz_z)

            risk = stunting_risk_percent(haz_z, waz_z) if haz_z and waz_z else None
            status = stunting_status(haz_z) if haz_z else None

            WFA = safe_round(waz_z)
            HFA = safe_round(haz_z)
            WFH = safe_round(whz_z)
            HCFA = safe_round(hcz_z)

            status_z = {
            "waz_z": WFA, "waz_label": waz_label,
            "haz_z": HFA, "haz_label": haz_label,
            "whz_z": WFH, "whz_label": whz_label,
            "hcz_z": HCFA, "hcz_label": hcz_label }
            
            # Save to database
            z_scores = {'wfa': WFA, 'hfa': HFA, 'wfh': WFH, 'hcfa': HCFA}
            statuses = {'wfa': waz_label, 'hfa': haz_label, 'wfh': whz_label, 'hcfa': hcz_label}
            save_measurement(data, z_scores, statuses, risk, status, st.session_state.username)
            
            st.success(" Data berhasil dianalisis dan disimpan!")
            st.markdown("---")
            
            # Header Hasil
            st.markdown(f"<h2 style='text-align: center; color: #8AA624;'> Hasil Analisis: {data['name']}</h2>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center;'>Tanggal Pengukuran: <b>{data['date']}</b> | Usia: <b>{data['age']} bulan</b> | Jenis Kelamin: <b>{'Laki-laki' if data['sex'] == 'L' else 'Perempuan'}</b></p>", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Data Antropometri dalam Cards
            st.subheader(" Indikator Antropometri (Z-Score)")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"""
                <div class='metric-card'>
                    <h4> Berat Badan menurut Usia (WFA)</h4>
                    <p style='font-size: 1.8rem; font-weight: 800; color: #FFEB3B; text-shadow: 2px 2px 3px rgba(0,0,0,0.4);'>Z-Score: {WFA}</p>
                    <p style='font-size: 1.1rem;'><b>Status:</b> {waz_label}</p>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(f"""
                <div class='metric-card'>
                    <h4> Berat Badan menurut Tinggi (WFH)</h4>
                    <p style='font-size: 1.8rem; font-weight: 800; color: #FFEB3B; text-shadow: 2px 2px 3px rgba(0,0,0,0.4);'>Z-Score: {WFH}</p>
                    <p style='font-size: 1.1rem;'><b>Status:</b> {whz_label}</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class='metric-card'>
                    <h4> Tinggi Badan menurut Usia (HFA)</h4>
                    <p style='font-size: 1.8rem; font-weight: 800; color: #FFEB3B; text-shadow: 2px 2px 3px rgba(0,0,0,0.4);'>Z-Score: {HFA}</p>
                    <p style='font-size: 1.1rem;'><b>Status:</b> {haz_label}</p>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(f"""
                <div class='metric-card'>
                    <h4> Lingkar Kepala menurut Usia (HCFA)</h4>
                    <p style='font-size: 1.8rem; font-weight: 800; color: #FFEB3B; text-shadow: 2px 2px 3px rgba(0,0,0,0.4);'>Z-Score: {HCFA}</p>
                    <p style='font-size: 1.1rem;'><b>Status:</b> {hcz_label}</p>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Interpretasi Stunting
            st.subheader(" Interpretasi Risiko Stunting")
            
            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown(f"""
                <div style='text-align: center; padding: 2rem; background: linear-gradient(135deg, #8AA624 0%, #FEA405 100%); border-radius: 15px; color: white;'>
                    <h1 style='margin: 0; font-size: 3rem;'>{risk}%</h1>
                    <p style='margin: 0; font-size: 1.2rem;'>Risiko Stunting</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                if status != "Tidak Berisiko Stunting":
                    st.error(f" **Status Stunting:** {status}")
                else:
                    st.success(f" **Status Stunting:** {status}")
            
            st.markdown("---")
            st.caption(" Hasil ini merupakan skrining awal. Untuk diagnosis dan penanganan lebih lanjut, konsultasikan dengan tenaga kesehatan profesional.")

            # Output gemini
            st.markdown("---")
            st.markdown("### Penjelasan Hasil Skrining")
            with st.spinner("AI sedang menganalisis data..."):
                saran_ai = get_ai_analysis(data, status_z)
                st.info(saran_ai)

# ========= PROFILE PAGE
elif page == " Profile":
    # Judul
    st.title(" Tentang Kami")
    st.markdown("---")
    
    # Deskripsi Sistem
    st.markdown("""
    <div style='background: linear-gradient(135deg, rgba(138, 166, 36, 0.1) 0%, rgba(254, 164, 5, 0.1) 100%); 
                padding: 2rem; border-radius: 15px; border-left: 5px solid #8AA624;'>
        <p style='font-size: 1.1rem; line-height: 1.8; text-align: justify;'>
            <strong>SI Tumbuh</strong> merupakan sistem informasi berbasis web yang dikembangkan untuk mendukung skrining 
            pertumbuhan dan penilaian status gizi balita di tingkat layanan posyandu. Sistem ini menggunakan 
            data antropometri balita meliputi berat badan, tinggi/panjang badan, usia, dan jenis kelamin untuk menghitung 
            indikator pertumbuhan (BB/U, TB/U, BB/TB, dan LK/U) berdasarkan standar WHO, sehingga dapat mengidentifikasi 
            gangguan pertumbuhan dan risiko stunting.
        </p>
        <p style='font-size: 1.1rem; line-height: 1.8; text-align: justify;'>
            SI Tumbuh menyajikan hasil pengukuran dalam bentuk visualisasi yang mudah dipahami, disertai interpretasi
            status gizi dan rekomendasi tindak lanjut awal yang ditujukan untuk mendukung peran kader Posyandu. 
            Sistem ini dirancang untuk memperkuat pemantauan pertumbuhan balita, deteksi dini masalah gizi, serta upaya
            promotif dan preventif dalam peningkatan kesehatan dan status gizi balita.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # 3 Gambar Berjajar Horizontal (Responsif)
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.image("Khusna.png", use_container_width=True)
        st.markdown("""
        <div style='text-align: center; margin-top: 1rem;'>
            <a href='mailto:khusnalathifah@gmail.com' style='text-decoration: none;'>
                <button style='background: #8AA624; color: white; border: none; padding: 0.5rem 1.5rem; 
                               border-radius: 5px; cursor: pointer; font-size: 1rem; width: 100%;'>
                     Kontak Khusna
                </button>
            </a>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.image("Mayang.png", use_container_width=True)
        st.markdown("""
        <div style='text-align: center; margin-top: 1rem;'>
            <a href='mailto:gumelarmayang@gmail.com' style='text-decoration: none;'>
                <button style='background: #8AA624; color: white; border: none; padding: 0.5rem 1.5rem; 
                               border-radius: 5px; cursor: pointer; font-size: 1rem; width: 100%;'>
                     Kontak Mayang
                </button>
            </a>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.image("Via.png", use_container_width=True)
        st.markdown("""
        <div style='text-align: center; margin-top: 1rem;'>
            <a href='mailto:setyoriniokviana@gmail.com' style='text-decoration: none;'>
                <button style='background: #8AA624; color: white; border: none; padding: 0.5rem 1.5rem; 
                               border-radius: 5px; cursor: pointer; font-size: 1rem; width: 100%;'>
                     Kontak Via
                </button>
            </a>
        </div>
        """, unsafe_allow_html=True)