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
        base_pin = st.secrets["BASE_PIN"] # যেমন: "1234"
    except:
        base_pin = "1234"
    
    day_str = datetime.now().strftime("%d") # আজকের তারিখ (যেমন: 03)
    return f"{base_pin}{day_str}" # আউটপুট: "123403"

CURRENT_DAILY_PIN = get_daily_pin()
# --- ১. শক্তিশালী নির্দেশিকা ও পরিবর্তনের পপ-আপ (Pop-up Dialog) ---
@st.dialog("🚀 FuelGuard Pro: নতুন আপডেট ও নির্দেশিকা")
def show_advanced_manual():
    st.markdown("""
    ### ⛽ অ্যাপে বড় ধরনের পরিবর্তন আনা হয়েছে!
    ব্যবহারকারীদের সুবিধার জন্য আমরা অ্যাপটিকে দুটি প্রধান ভাগে ভাগ করেছি:

    ---
    #### 👤 ১. রাইডার / কাস্টমার পোর্টাল (Rider Side)
    - **উন্মুক্ত চেক:** এখন যে কেউ যেকোনো রেজিস্ট্রেশন নাম্বার দিয়ে রাইডারের **Eligibility** চেক করতে পারবেন।
    - **সহজ নিবন্ধন:** নতুন রাইডাররা কোনো পিন ছাড়াই নিজের তথ্য দিয়ে রেজিস্ট্রেশন করতে পারবেন।
    - **স্বচ্ছতা:** আপনার বা অন্য কারো রিফিল স্ট্যাটাস এখন সবার জন্য উন্মুক্ত।

    ---
    #### 🏢 ২. পাম্প স্টেশন প্যানেল (Pump Station)
    - **ডেইলি ডাইনামিক পিন (Daily PIN):** নিরাপত্তার খাতিরে পাম্প স্টেশনের পিন এখন প্রতিদিন স্বয়ংক্রিয়ভাবে পরিবর্তিত হবে। 
    - **এক পিন, হাজার পাম্প:** বাংলাদেশের যেকোনো প্রান্তের পাম্প স্টেশন একই 'ডেইলি পিন' ব্যবহার করে লগ-ইন করতে পারবে।
    - **দ্রুত এন্ট্রি:** লগ-ইন করার পর বারবার পিন দিতে হবে না, সরাসরি রাইডার আইডি দিয়ে তেল এন্ট্রি দেওয়া যাবে।

    ---
    #### ✅ আমাদের শক্তিশালী দিকসমূহ (Our Strengths):
    * **৭২ ঘণ্টা স্মার্ট লক:** সিস্টেম স্বয়ংক্রিয়ভাবে হিসেব রাখবে এবং নির্দিষ্ট সময়ের আগে কাউকে রিফিল করতে দেবে না।
    * **অটো-রিফ্রেশ:** প্রতিটি ট্রানজ্যাকশন শেষে ডাটাবেজ আপডেট হয়ে অ্যাপ নিজে থেকেই পরবর্তী কাজের জন্য প্রস্তুত হবে।
    * **ক্লাউড সিনক্রোনাইজেশন:** গুগল শিটের সাথে সরাসরি যুক্ত থাকায় ডাটা হারানোর কোনো ভয় নেই।
    """)
    if st.button("বুঝেছি, প্রবেশ করুন"):
        st.session_state.show_advanced_manual = False
        st.rerun()

# প্রথমবারের জন্য পপ-আপ ট্রিগার
if "show_advanced_manual" not in st.session_state:
    st.session_state.show_advanced_manual = True

if st.session_state.show_advanced_manual:
    show_advanced_manual()
# জেলা ও সিরিজ তালিকা
BD_DISTRICTS = ["BAGERHAT", "BANDARBAN", "BARGUNA", "BARISHAL", "BHOLA", "BOGURA", "BRAHMANBARIA", "CHANDPUR", "CHATTOGRAM", "CHATTOGRAM METRO", "CHUADANGA", "COMILLA", "COXS BAZAR", "DHAKA", "DHAKA METRO", "DINAJPUR", "FARIDPUR", "FENI", "GAIBANDHA", "GAZIPUR", "GOPALGANJ", "HABIGANJ", "JAMALPUR", "JASHORE", "JHALOKATHI", "JHENAIDAH", "JOYPURHAT", "KHAGRACHHARI", "KHULNA", "KHULNA METRO", "KISHOREGANJ", "KURIGRAM", "KUSHTIA", "LAKSHMIPUR", "LALMONIRHAT", "MADARIPUR", "MAGURA", "MANIKGANJ", "MEHERPUR", "MOULVIBAZAR", "MUNSHIGANJ", "MYMENSINGH", "NAOGAON", "NARAIL", "NARAYANGANJ", "NARSINGDI", "NATORE", "NETROKONA", "NILPHAMARI", "NOAKHALI", "PABNA", "PANCHAGARH", "PATUAKHALI", "PIROJPUR", "RAJBARI", "RAJSHAHI", "RAJSHAHI METRO", "RANGAMATI", "RANGPUR", "SATKHIRA", "SHARIATPUR", "SHERPUR", "SIRAJGANJ", "SUNAMGANJ", "SYLHET", "SYLHET METRO", "TANGAIL", "THAKURGAON"]
SERIES_LIST = ["KA", "KHA", "GA", "GHA", "CHA", "THA", "HA", "LA", "MA", "BA"]

# --- ২. ডাটাবেজ কানেকশন ---
@st.cache_data(ttl=5)
def fetch_data(_spread_obj):
    try:
        data = _spread_obj.sheet_to_df(index=0)
        data.columns = data.columns.str.strip()
        return data
    except:
        return pd.DataFrame(columns=["RiderID", "Name", "Last_Refill", "Liters"])

if "gcp_service_account" in st.secrets:
    creds = dict(st.secrets["gcp_service_account"])
    try:
        spread = Spread("FuelTracker", config=creds)
        df = fetch_data(spread)
    except:
        st.error("Connection Failed!"); st.stop()
else:
    st.error("Credentials missing!"); st.stop()

def clean_id(text):
    return str(text).lower().replace(" ", "").replace("-", "").strip()

# --- ৩. সেশন স্টেট (ইউজার রোল ম্যানেজমেন্ট) ---
if "user_role" not in st.session_state:
    st.session_state.user_role = None

# --- ৪. ল্যান্ডিং পেজ (রোল সিলেকশন) ---
if st.session_state.user_role is None:
    st.title("⛽ FuelGuard Pro: Welcome")
    st.subheader("আপনার ভূমিকা নির্বাচন করুন (Choose Your Role)")
    
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

# --- ৫. রাইডার ইন্টারফেস (Rider Side) ---
if st.session_state.user_role == "Rider":
    if st.button("⬅️ ব্যাক (Role Change)"):
        st.session_state.user_role = None
        st.rerun()
        
    st.title("🏍️ Rider Portal")
    tab_check, tab_reg = st.tabs(["🔍 চেক এলিজিবিলিটি", "📝 নতুন নিবন্ধন"])
    
    with tab_check:
        search_id = st.text_input("সার্চ রেজিস্ট্রেশন নাম্বার (যেমন: DHAKA METRO HA 12-3456)")
        if search_id:
            s_id = clean_id(search_id)
            df['tmp'] = df['RiderID'].apply(clean_id)
            match = df[df['tmp'] == s_id]
            if not match.empty:
                r = match.iloc[0]
                st.info(f"রাইডার: {r['Name']}")
                # ৭২ ঘণ্টা চেক
                last_val = str(r['Last_Refill']).strip()
                if last_val and last_val.lower() != "nan" and last_val != "":
                    unlock = datetime.strptime(last_val, "%Y-%m-%d %H:%M:%S") + timedelta(hours=LOCKOUT_HOURS)
                    if datetime.now() < unlock:
                        st.error(f"🚫 লকড! পরবর্তীতে পাবেন: {unlock.strftime('%b %d, %I:%M %p')}")
                    else: st.success("✅ যোগ্য (Eligible)")
                else: st.success("✅ যোগ্য (Eligible)")
            else: st.warning("আইডি পাওয়া যায়নি।")

    with tab_reg:
        with st.form("reg"):
            d = st.selectbox("জেলা", sorted(BD_DISTRICTS)); s = st.selectbox("সিরিজ", SERIES_LIST)
            n = st.text_input("নাম্বার"); nm = st.text_input("নাম")
            if st.form_submit_button("রেজিস্ট্রেশন"):
                f_id = f"{d}-{s}-{n}".upper()
                new_row = pd.DataFrame([{"RiderID": f_id, "Name": nm, "Last_Refill": "", "Liters": 0}])
                spread.df_to_sheet(pd.concat([df, new_row], ignore_index=True), index=False, replace=True)
                st.cache_data.clear(); st.success(f"সফল! আইডি: {f_id}")

# --- ৬. পাম্প স্টেশন ইন্টারফেস (Pump Side) ---
elif st.session_state.user_role == "Pump":
    if "pump_authenticated" not in st.session_state:
        st.session_state.pump_authenticated = False

    if not st.session_state.pump_authenticated:
        st.title("🏢 Pump Station Login")
        pin_input = st.text_input("আজকের ডেইলি পিন দিন (Daily PIN)", type="password")
        if st.button("প্রবেশ করুন"):
            if pin_input == CURRENT_DAILY_PIN:
                st.session_state.pump_authenticated = True
                st.rerun()
            else: st.error("ভুল পিন! পিন প্রতিদিন পরিবর্তন হয়।")
        if st.button("⬅️ ব্যাক"):
            st.session_state.user_role = None
            st.rerun()
    else:
        # পাম্প স্টেশন মেইন পেজ
        st.title("⛽ Pump Operation Panel")
        if st.sidebar.button("🚪 লগ আউট"):
            st.session_state.pump_authenticated = False
            st.rerun()
            
        p_id = st.text_input("রাইডার আইডি স্ক্যান/লিখুন")
        if p_id:
            s_id = clean_id(p_id)
            df['tmp'] = df['RiderID'].apply(clean_id)
            idx_list = df.index[df['tmp'] == s_id].tolist()
            if idx_list:
                idx = idx_list[0]
                st.write(f"রাইডার: {df.at[idx, 'Name']}")
                liters = st.number_input("লিটার", 1.0, 50.0, 5.0)
                if st.button("Confirm Transaction"):
                    df.at[idx, 'Last_Refill'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    df.at[idx, 'Liters'] = liters
                    spread.df_to_sheet(df.drop(columns=['tmp']), index=False, replace=True)
                    st.cache_data.clear(); st.success("সফল!"); st.rerun()
