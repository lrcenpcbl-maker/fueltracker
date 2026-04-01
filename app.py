import streamlit as st
from gspread_pandas import Spread
import pandas as pd
from datetime import datetime, timedelta
import qrcode
import io
import json

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="FuelGuard Pro", page_icon="⛽", layout="wide")
LOCKOUT_HOURS = 72
APP_URL = "https://fuel-tracker.streamlit.app" 

# বাংলাদেশের ৬৪টি জেলার তালিকা
BD_DISTRICTS = [
    "BAGERHAT", "BANDARBAN", "BARGUNA", "BARISHAL", "BHOLA", "BOGURA", "BRAHMANBARIA", 
    "CHANDPUR", "CHATTOGRAM", "CHATTOGRAM METRO", "CHUADANGA", "COMILLA", "COXS BAZAR", 
    "DHAKA", "DHAKA METRO", "DINAJPUR", "FARIDPUR", "FENI", "GAIBANDHA", "GAZIPUR", 
    "GOPALGANJ", "HABIGANJ", "JAMALPUR", "JASHORE", "JHALOKATHI", "JHENAIDAH", 
    "JOYPURHAT", "KHAGRACHHARI", "KHULNA", "KHULNA METRO", "KISHOREGANJ", "KURIGRAM", 
    "KUSHTIA", "LAKSHMIPUR", "LALMONIRHAT", "MADARIPUR", "MAGURA", "MANIKGANJ", 
    "MEHERPUR", "MOULVIBAZAR", "MUNSHIGANJ", "MYMENSINGH", "NAOGAON", "NARAIL", 
    "NARAYANGANJ", "NARSINGDI", "NATORE", "NETROKONA", "NILPHAMARI", "NOAKHALI", 
    "PABNA", "PANCHAGARH", "PATUAKHALI", "PIROJPUR", "RAJBARI", "RAJSHAHI", 
    "RAJSHAHI METRO", "RANGAMATI", "RANGPUR", "SATKHIRA", "SHARIATPUR", "SHERPUR", 
    "SIRAJGANJ", "SUNAMGANJ", "SYLHET", "SYLHET METRO", "TANGAIL", "THAKURGAON"
]

# --- 2. BANGLA INSTRUCTIONS DIALOG (আপডেটেড) ---
@st.dialog("ব্যবহার নির্দেশিকা (How to Use)")
def show_instructions():
    st.markdown("""
    ### ⛽ ফুয়েলগার্ড (FuelGuard) এ স্বাগতম
    এই অ্যাপটি জ্বালানি বণ্টন ব্যবস্থা স্বচ্ছ এবং নিরপেক্ষ রাখার জন্য তৈরি করা হয়েছে।
    
    **নিয়মাবলী:**
    1. **৭২ ঘণ্টার নিয়ম:** একবার তেল নেওয়ার পর পরবর্তী **৭২ ঘণ্টা** পর্যন্ত ওই আইডি দিয়ে পুনরায় তেল নেওয়া যাবে না।
    2. **কিউআর কোড স্ক্যান:** রাইডারের আইডি কার্ডের QR কোড স্ক্যান করুন অথবা ম্যানুয়ালি আইডি ইনপুট দিন।
    3. **স্ট্যাটাস চেক:** - ✅ **সবুজ সংকেত:** রাইডার তেল পাওয়ার যোগ্য। লিটার লিখে 'Confirm' বাটনে চাপ দিন।
        - 🚫 **লাল সংকেত:** রাইডার লকড। স্ক্রিনে প্রদর্শিত সময় শেষ না হওয়া পর্যন্ত অপেক্ষা করতে হবে।
    4. **ডেটা সেভ:** প্রতিবার তেল দেওয়ার পর অবশ্যই **'Confirm & Save'** বাটনে ক্লিক করবেন।

    **নতুন ফিচারসমূহ:**
    - 📸 **ছবি ভেরিফিকেশন:** তেল দেওয়ার সময় নিরাপত্তার জন্য গাড়ির ছবি তোলা বাধ্যতামূলক।
    - ☁️ **সেন্ট্রাল ডাটাবেজ:** যেকোনো পাম্প থেকে তেল নিলেই এই সিস্টেম আপডেট হবে।
    - 📊 **লাইভ রিপোর্ট:** অ্যাডমিন প্যানেলে আজকের মোট রিফিলের হিসাব দেখা যাবে।

    *যেকোনো সমস্যায় অ্যাডমিনের সাথে যোগাযোগ করুন: **vpersonal1123@gmail.com***
    """)
    if st.button("ঠিক আছে, শুরু করি"):
        st.session_state.initialized = True
        st.rerun()

if "initialized" not in st.session_state:
    show_instructions()

# --- 3. DATABASE CONNECTION ---
@st.cache_data(ttl=5)
def fetch_data(_spread_obj):
    try:
        data = _spread_obj.sheet_to_df(index=0)
        data.columns = data.columns.str.strip()
        required_cols = ["RiderID", "Name", "Last_Refill", "Liters"]
        for col in required_cols:
            if col not in data.columns:
                data[col] = "" if col != "Liters" else 0
        return data
    except Exception:
        return pd.DataFrame(columns=["RiderID", "Name", "Last_Refill", "Liters"])

# Load Credentials
if "gcp_service_account" in st.secrets:
    creds = dict(st.secrets["gcp_service_account"])
    try:
        spread = Spread("FuelTracker", config=creds)
        df = fetch_data(spread)
    except Exception as e:
        st.error(f"Connection Failed: {e}")
        st.stop()
else:
    st.error("Credentials missing!")
    st.stop()

# --- 4. SMART HELPER FUNCTIONS ---
def clean_id(text):
    return str(text).lower().replace(" ", "").replace("-", "").strip()

# --- 5. MAIN INTERFACE ---
st.title("⛽ FuelGuard Pro: স্মার্ট ফুয়েল মনিটরিং")

search_input = st.text_input("🔍 রাইডার আইডি লিখুন বা কিউআর স্ক্যান করুন", 
                            placeholder="যেমন: pabna ha 11 0101")

if search_input:
    s_id = clean_id(search_input)
    mask = df['RiderID'].apply(clean_id) == s_id
    rider_row = df[mask]

    if rider_row.empty:
        st.warning(f"❌ '{search_input}' আইডিটি ডাটাবেজে পাওয়া যায়নি।")
    else:
        rider_name = rider_row.iloc[0]['Name']
        last_val = rider_row.iloc[0]['Last_Refill']
        actual_id = rider_row.iloc[0]['RiderID']
        
        st.header(f"👤 রাইডার: {rider_name} ({actual_id})")

        eligible = True
        unlock_time = None
        if not (pd.isna(last_val) or str(last_val).strip() == ""):
            try:
                last_dt = datetime.strptime(str(last_val), "%Y-%m-%d %H:%M:%S")
                unlock_time = last_dt + timedelta(hours=LOCKOUT_HOURS)
                if datetime.now() < unlock_time:
                    eligible = False
            except:
                st.error("তারিখের ফরম্যাটে সমস্যা।")

        if not eligible:
            st.error(f"### 🚫 রিফিল রিজেক্ট (Locked)")
            diff = unlock_time - datetime.now()
            st.subheader(f"অপেক্ষা: {diff.days} দিন {diff.seconds//3600} ঘণ্টা")
        else:
            st.success("### ✅ রিফিল অনুমোদিত")
            col1, col2 = st.columns(2)
            with col1:
                liters = st.number_input("লিটারের পরিমাণ", 1.0, 100.0, 5.0)
                confirm = st.button("💾 Confirm & Save to Cloud")
            with col2:
                photo = st.camera_input("নিরাপত্তার জন্য গাড়ির ছবি তুলুন")
            
            if confirm:
                if photo:
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    df.loc[mask, 'Last_Refill'] = now_str
                    df.loc[mask, 'Liters'] = liters
                    spread.df_to_sheet(df, index=False, replace=True)
                    st.cache_data.clear() 
                    st.success("সফলভাবে আপডেট হয়েছে!")
                    st.balloons()
                    st.rerun()
                else:
                    st.warning("⚠️ ছবি তোলা বাধ্যতামূলক।")

# --- 6. SIDEBAR ---
st.sidebar.title("⚙️ এডমিন প্যানেল")
with st.sidebar.expander("📝 নতুন রাইডার রেজিস্ট্রেশন"):
    with st.form("reg"):
        d = st.selectbox("জেলা", sorted(BD_DISTRICTS))
        s = st.selectbox("সিরিজ", ["KA", "KHA", "GA", "GHA", "CHA", "THA", "HA", "LA", "MA", "BA"])
        n = st.text_input("নাম্বার (11-0101)")
        name = st.text_input("নাম")
        if st.form_submit_button("রেজিস্টার"):
            final_id = f"{d}-{s}-{n}".upper()
            new_row = pd.DataFrame([{"RiderID": final_id, "Name": name, "Last_Refill": "", "Liters": 0}])
            spread.df_to_sheet(pd.concat([df, new_row]), index=False, replace=True)
            st.cache_data.clear()
            st.success("রেজিস্টার্ড হয়েছে!")
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("📊 আজকের লাইভ রিপোর্ট")
try:
    df['Last_Refill_DT'] = pd.to_datetime(df['Last_Refill'], errors='coerce')
    today_df = df[df['Last_Refill_DT'].dt.date == datetime.now().date()]
    st.sidebar.metric("আজকের রিফিল", len(today_df))
    st.sidebar.metric("মোট লিটার", f"{today_df['Liters'].astype(float).sum()} L")
except: pass
