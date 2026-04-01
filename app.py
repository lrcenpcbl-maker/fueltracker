import streamlit as st
from gspread_pandas import Spread
import pandas as pd
from datetime import datetime, timedelta
import qrcode
import io
import json

# --- ১. কনফিগারেশন ---
st.set_page_config(page_title="FuelGuard Pro", page_icon="⛽", layout="wide")
LOCKOUT_HOURS = 72
APP_URL = "https://fuel-tracker.streamlit.app" 

# --- ২. ইনস্ট্রাকশন পপ-আপ ---
@st.dialog("ব্যবহার নির্দেশিকা (How to Use)")
def show_instructions():
    st.markdown("""
    ### ⛽ ফুয়েলগার্ড প্রোর সুবিধা:
    ১. **সেন্ট্রাল ডাটাবেজ:** যেকোনো পাম্প থেকে তেল নিলেই সিস্টেম আপডেট হয়ে যাবে।
    ২. **ছবি ভেরিফিকেশন:** তেল দেওয়ার সময় গাড়ির ছবি তুললে স্বচ্ছতা নিশ্চিত হয়।
    ৩. **অটো লক:** একবার তেল নিলে পরবর্তী ৭২ ঘণ্টা অন্য কোনো পাম্প থেকেও তেল নেওয়া যাবে না।
    """)
    if st.button("বুঝেছি, শুরু করি"):
        st.session_state.initialized = True
        st.rerun()

if "initialized" not in st.session_state:
    show_instructions()

# --- ৩. ডাটাবেজ কানেকশন ---
@st.cache_data(ttl=5)
def fetch_data(_spread_obj):
    try:
        data = _spread_obj.sheet_to_df(index=0)
        data.columns = data.columns.str.strip()
        return data
    except:
        return pd.DataFrame(columns=["RiderID", "Name", "Last_Refill", "Liters"])

# ক্রেডিটেন্সিয়াল লোড
if "gcp_service_account" in st.secrets:
    creds = dict(st.secrets["gcp_service_account"])
    spread = Spread("FuelTracker", config=creds)
    df = fetch_data(spread)
else:
    st.error("Credentials missing!")
    st.stop()

# --- ৪. হেল্পার ফাংশন ---
def clean_id(text):
    return str(text).lower().replace(" ", "").replace("-", "").strip()

# --- ৫. মেইন ইন্টারফেস ---
st.title("⛽ FuelGuard Pro: সেন্ট্রাল ফুয়েল মনিটরিং")

scanned_id = st.text_input("🔍 রাইডার আইডি স্ক্যান বা লিখুন", placeholder="Ex: DHAKA-METRO-123")

if scanned_id:
    s_id = clean_id(scanned_id)
    match_df = df.copy()
    match_df['match_id'] = match_df['RiderID'].apply(clean_id)
    rider_row = match_df[match_df['match_id'] == s_id]

    if rider_row.empty:
        st.warning("❌ এই আইডিটি নিবন্ধিত নয়।")
    else:
        name = rider_row.iloc[0]['Name']
        last_val = rider_row.iloc[0]['Last_Refill']
        st.header(f"👤 রাইডার: {name}")

        # সময় চেক করা
        eligible = True
        unlock_time = None
        if not (pd.isna(last_val) or str(last_val).strip() == ""):
            last_dt = datetime.strptime(str(last_val), "%Y-%m-%d %H:%M:%S")
            unlock_time = last_dt + timedelta(hours=LOCKOUT_HOURS)
            if datetime.now() < unlock_time:
                eligible = False

        if not eligible:
            st.error(f"### 🚫 রিফিল রিজেক্ট করা হয়েছে!")
            diff = unlock_time - datetime.now()
            st.subheader(f"অপেক্ষা করুন: {diff.days} দিন {diff.seconds//3600} ঘণ্টা")
        else:
            st.success("### ✅ রিফিল অনুমোদিত")
            col1, col2 = st.columns(2)
            with col1:
                liters = st.number_input("লিটার (Liters)", 1.0, 50.0, 5.0)
            with col2:
                # পয়েন্ট ৩: ক্যামেরা ইনপুট
                photo = st.camera_input("নিরাপত্তার জন্য গাড়ির ছবি তুলুন")

            if st.button("💾 কনফার্ম এবং ডাটাবেজ আপডেট"):
                if photo:
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    mask = df['RiderID'].apply(clean_id) == s_id
                    df.loc[mask, 'Last_Refill'] = now_str
                    # পয়েন্ট ৫: ফাস্ট আপডেট
                    spread.df_to_sheet(df, index=False, replace=True)
                    st.success("সেন্ট্রাল ডাটাবেজে তথ্য আপডেট হয়েছে!")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("ছবি তোলা বাধ্যতামূলক (Security Protocol)")

# --- ৬. অ্যাডমিন ড্যাশবোর্ড (পয়েন্ট ৪) ---
st.sidebar.title("📊 অ্যাডমিন ড্যাশবোর্ড")
if st.sidebar.checkbox("আজকের রিপোর্ট দেখুন"):
    df['Last_Refill_Date'] = pd.to_datetime(df['Last_Refill']).dt.date
    today = datetime.now().date()
    today_data = df[df['Last_Refill_Date'] == today]
    
    st.sidebar.metric("আজকের মোট রাইডার", len(today_data))
    st.sidebar.write("সাম্প্রতিক রিফিল তালিকা:")
    st.sidebar.table(today_data[['RiderID', 'Name', 'Last_Refill']])

# রেজিস্ট্রেশন ও কিউআর জেনারেটর আগের মতোই থাকবে...
