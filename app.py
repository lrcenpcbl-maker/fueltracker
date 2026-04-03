import streamlit as st
from gspread_pandas import Spread
import pandas as pd
from datetime import datetime, timedelta
import qrcode
import io

# --- ১. কনফিগারেশন ও সিক্রেটস ---
st.set_page_config(page_title="FuelGuard Pro", page_icon="⛽", layout="wide")

LOCKOUT_HOURS = 72
APP_URL = "https://fuel-tracker.streamlit.app" 

# ডাইনামিক পিন জেনারেটর (প্রতিদিন পরিবর্তন হবে)
def get_daily_pin():
    try:
        base_pin = st.secrets["BASE_PIN"] 
    except:
        base_pin = "1234" # ডিফল্ট পিন
    day_str = datetime.now().strftime("%d") 
    return f"{base_pin}{day_str}"

CURRENT_DAILY_PIN = get_daily_pin()

BD_DISTRICTS = ["BAGERHAT", "BANDARBAN", "BARGUNA", "BARISHAL", "BHOLA", "BOGURA", "BRAHMANBARIA", "CHANDPUR", "CHATTOGRAM", "CHATTOGRAM METRO", "CHUADANGA", "COMILLA", "COXS BAZAR", "DHAKA", "DHAKA METRO", "DINAJPUR", "FARIDPUR", "FENI", "GAIBANDHA", "GAZIPUR", "GOPALGANJ", "HABIGANJ", "JAMALPUR", "JASHORE", "JHALOKATHI", "JHENAIDAH", "JOYPURHAT", "KHAGRACHHARI", "KHULNA", "KHULNA METRO", "KISHOREGANJ", "KURIGRAM", "KUSHTIA", "LAKSHMIPUR", "LALMONIRHAT", "MADARIPUR", "MAGURA", "MANIKGANJ", "MEHERPUR", "MOULVIBAZAR", "MUNSHIGANJ", "MYMENSINGH", "NAOGAON", "NARAIL", "NARAYANGANJ", "NARSINGDI", "NATORE", "NETROKONA", "NILPHAMARI", "NOAKHALI", "PABNA", "PANCHAGARH", "PATUAKHALI", "PIROJPUR", "RAJBARI", "RAJSHAHI", "RAJSHAHI METRO", "RANGAMATI", "RANGPUR", "SATKHIRA", "SHARIATPUR", "SHERPUR", "SIRAJGANJ", "SUNAMGANJ", "SYLHET", "SYLHET METRO", "TANGAIL", "THAKURGAON"]
SERIES_LIST = ["KA", "KHA", "GA", "GHA", "CHA", "THA", "HA", "LA", "MA", "BA"]

# --- ২. পপ-আপ নির্দেশিকা ---
@st.dialog("🚀 FuelGuard Pro: ইউজার গাইড")
def show_advanced_manual():
    st.markdown("""
    ### ⛽ নতুন সিস্টেম আপডেট:
    
    #### 👤 ১. রাইডার পোর্টাল:
    - পিন ছাড়াই **রেজিস্ট্রেশন** এবং **Eligibility** চেক করা যাবে।
    
    #### 🏢 ২. পাম্প স্টেশন:
    - **Daily PIN:** নিরাপত্তার জন্য প্রতিদিন পিন পরিবর্তিত হবে (Base PIN + আজকের তারিখ)।
    - **ঐচ্ছিক ছবি:** গাড়ির ছবি তোলা এখন আর বাধ্যতামূলক নয়। ছবি ছাড়াও ট্রানজ্যাকশন সেভ করা যাবে।
    
    #### ✅ স্মার্ট ফিচার:
    - **৭২ ঘণ্টা লক** এবং ডাটা সেভ হওয়ার পর **অটো-রিফ্রেশ**।
    """)
    if st.button("বুঝেছি, প্রবেশ করুন"):
        st.session_state.show_advanced_manual = False
        st.rerun()

if "show_advanced_manual" not in st.session_state:
    st.session_state.show_advanced_manual = True

if st.session_state.show_advanced_manual:
    show_advanced_manual()

# --- ৩. ডাটাবেজ কানেকশন ---
@st.cache_data(ttl=5)
def fetch_data(_spread_obj):
    try:
        data = _spread_obj.sheet_to_df(index=0)
        data.columns = data.columns.str.strip()
        if 'Liters' in data.columns:
            data['Liters'] = pd.to_numeric(data['Liters'], errors='coerce').fillna(0)
        return data
    except:
        return pd.DataFrame(columns=["RiderID", "Name", "Last_Refill", "Liters"])

if "gcp_service_account" in st.secrets:
    creds = dict(st.secrets["gcp_service_account"])
    try:
        spread = Spread("FuelTracker", config=creds)
        df = fetch_data(spread)
    except:
        st.error("Google Sheet Connection Failed!"); st.stop()
else:
    st.error("Credentials missing!"); st.stop()

def clean_id(text):
    return str(text).lower().replace(" ", "").replace("-", "").strip()

# --- ৪. রোল সিলেকশন ---
if "user_role" not in st.session_state:
    st.session_state.user_role = None

if st.session_state.user_role is None:
    st.title("⛽ FuelGuard Pro")
    st.subheader("আপনার ভূমিকা নির্বাচন করুন:")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🏍️ Rider / Customer", use_container_width=True):
            st.session_state.user_role = "Rider"
            st.rerun()
    with col2:
        if st.button("🏢 Pump Station", use_container_width=True):
            st.session_state.user_role = "Pump"
            st.rerun()
    st.stop()

# --- ৫. রাইডার ইন্টারফেস ---
if st.session_state.user_role == "Rider":
    if st.sidebar.button("⬅️ Home"):
        st.session_state.user_role = None
        st.rerun()
        
    st.title("🏍️ Rider Portal")
    t1, t2 = st.tabs(["🔍 চেক এলিজিবিলিটি", "📝 নতুন নিবন্ধন"])
    
    with t1:
        search_id = st.text_input("রেজিস্ট্রেশন নাম্বার লিখুন")
        if search_id:
            s_id = clean_id(search_id)
            df['tmp'] = df['RiderID'].apply(clean_id)
            match = df[df['tmp'] == s_id]
            if not match.empty:
                r = match.iloc[0]
                st.info(f"রাইডার: **{r['Name']}**")
                last_val = str(r['Last_Refill']).strip()
                if last_val and last_val.lower() != "nan" and last_val != "":
                    unlock = datetime.strptime(last_val, "%Y-%m-%d %H:%M:%S") + timedelta(hours=LOCKOUT_HOURS)
                    if datetime.now() < unlock:
                        st.error(f"🚫 লকড! পরবর্তীতে পাবেন: {unlock.strftime('%b %d, %I:%M %p')}")
                    else: st.success("✅ জ্বালানি পাওয়ার যোগ্য")
                else: st.success("✅ জ্বালানি পাওয়ার যোগ্য")
            else: st.warning("আইডি পাওয়া যায়নি।")

    with t2:
        with st.form("reg"):
            d = st.selectbox("জেলা", sorted(BD_DISTRICTS)); s = st.selectbox("সিরিজ", SERIES_LIST)
            n = st.text_input("নাম্বার"); nm = st.text_input("নাম")
            if st.form_submit_button("রেজিস্ট্রেশন করুন"):
                if n and nm:
                    f_id = f"{d}-{s}-{n}".upper()
                    new_row = pd.DataFrame([{"RiderID": f_id, "Name": nm, "Last_Refill": "", "Liters": 0}])
                    spread.df_to_sheet(pd.concat([df.drop(columns=['tmp'] if 'tmp' in df.columns else []), new_row], ignore_index=True), index=False, replace=True)
                    st.cache_data.clear(); st.success(f"সফল! আইডি: {f_id}"); st.rerun()

# --- ৬. পাম্প স্টেশন ইন্টারফেস ---
elif st.session_state.user_role == "Pump":
    if "pump_auth" not in st.session_state:
        st.session_state.pump_auth = False

    if not st.session_state.pump_auth:
        st.title("🏢 Pump Station Login")
        pin_in = st.text_input("আজকের ডেইলি পিন (Daily PIN)", type="password")
        if st.button("প্রবেশ করুন"):
            if pin_in == CURRENT_DAILY_PIN:
                st.session_state.pump_auth = True
                st.rerun()
            else: st.error("ভুল পিন! প্রতিদিন পিন পরিবর্তন হয়।")
        if st.button("⬅️ ব্যাক"):
            st.session_state.user_role = None
            st.rerun()
    else:
        st.title("⛽ Pump Operation Panel")
        if st.sidebar.button("🚪 লগ আউট"):
            st.session_state.pump_auth = False
            st.rerun()
            
        p_id = st.text_input("রাইডার আইডি (Scan/Type)")
        if p_id:
            s_id = clean_id(p_id)
            df['tmp'] = df['RiderID'].apply(clean_id)
            idx_list = df.index[df['tmp'] == s_id].tolist()
            if idx_list:
                idx = idx_list[0]
                st.write(f"রাইডার: **{df.at[idx, 'Name']}**")
                
                # ৭২ ঘণ্টা লক চেক
                eligible = True
                last_refill_val = str(df.at[idx, 'Last_Refill']).strip()
                if last_refill_val and last_refill_val.lower() != "nan" and last_refill_val != "":
                    unlock = datetime.strptime(last_refill_val, "%Y-%m-%d %H:%M:%S") + timedelta(hours=LOCKOUT_HOURS)
                    if datetime.now() < unlock: eligible = False

                if not eligible:
                    st.error(f"🚫 এই আইডিটি লক করা। পরবর্তীতে পাবেন: {unlock.strftime('%b %d, %I:%M %p')}")
                else:
                    c1, c2 = st.columns(2)
                    with c1:
                        liters = st.number_input("লিটার পরিমাণ", 1.0, 100.0, 5.0)
                        if st.button("💾 Confirm & Save"):
                            df.at[idx, 'Last_Refill'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            df.at[idx, 'Liters'] = float(liters)
                            final_df = df.drop(columns=['tmp'])
                            spread.df_to_sheet(final_df, index=False, replace=True)
                            st.cache_data.clear()
                            st.success("সেভ হয়েছে!"); st.balloons(); st.rerun()
                    with c2:
                        photo = st.camera_input("গাড়ির ছবি (ঐচ্ছিক)")
            else: st.warning("আইডি পাওয়া যায়নি।")
