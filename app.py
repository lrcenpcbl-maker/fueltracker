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

# --- 2. BANGLA INSTRUCTIONS DIALOG (পপ-আপ) ---
@st.dialog("ব্যবহার নির্দেশিকা (How to Use)")
def show_instructions():
    st.markdown("""
    ⛽ ফুয়েলগার্ড (FuelGuard) এ স্বাগতম
    এই অ্যাপটি জ্বালানি বণ্টন ব্যবস্থা স্বচ্ছ এবং নিরপেক্ষ রাখার জন্য তৈরি করা হয়েছে।
    
    **নিয়মাবলী:**
    1. **৭২ ঘণ্টার নিয়ম:** একবার তেল নেওয়ার পর পরবর্তী **৭২ ঘণ্টা** পর্যন্ত ওই আইডি দিয়ে পুনরায় তেল নেওয়া যাবে না।
    2. **কিউআর কোড স্ক্যান:** রাইডারের আইডি কার্ডের QR কোড স্ক্যান করুন অথবা ম্যানুয়ালি আইডি ইনপুট দিন।
    3. **স্ট্যাটাস চেক:** - ✅ **সবুজ সংকেত:** রাইডার তেল পাওয়ার যোগ্য। লিটার লিখে 'Confirm' বাটনে চাপ দিন।
        - 🚫 **লাল সংকেত:** রাইডার লকড। স্ক্রিনে প্রদর্শিত সময় শেষ না হওয়া পর্যন্ত অপেক্ষা করতে হবে।
    4. **ডেটা সেভ:** প্রতিবার তেল দেওয়ার পর অবশ্যই **'Confirm & Save'** বাটনে ক্লিক করবেন।

    *যেকোনো সমস্যায় অ্যাডমিনের সাথে যোগাযোগ করুন। vpersonal1123@gmail.com*
    
    ### ⛽ ফুয়েলগার্ড (FuelGuard) এ স্বাগতম
    এই অ্যাপটি জ্বালানি বণ্টন ব্যবস্থা স্বচ্ছ এবং নিরপেক্ষ রাখার জন্য তৈরি করা হয়েছে।
    
    **নতুন ফিচারসমূহ:**
    1. **ছবি ভেরিফিকেশন:** তেল দেওয়ার সময় নিরাপত্তার জন্য গাড়ির ছবি তোলা বাধ্যতামূলক।
    2. **সেন্ট্রাল ডাটাবেজ:** যেকোনো পাম্প থেকে তেল নিলেই এই সিস্টেম আপডেট হবে।
    3. **লাইভ রিপোর্ট:** অ্যাডমিন প্যানেলে আজকের মোট রিফিলের হিসাব দেখা যাবে।
    """)
    if st.button("ঠিক আছে, শুরু করি"):
        st.session_state.initialized = True
        st.rerun()

if "initialized" not in st.session_state:
    show_instructions()

# --- 3. SECURE DATABASE CONNECTION ---
@st.cache_data(ttl=5)
def fetch_data(_spread_obj):
    try:
        data = _spread_obj.sheet_to_df(index=0)
        data.columns = data.columns.str.strip()
        # নিশ্চিত করা যে 'Liters' কলামটি আছে
        if 'Liters' not in data.columns:
            data['Liters'] = 0
        return data
    except Exception as e:
        st.error(f"Error reading sheet: {e}")
        return pd.DataFrame(columns=["RiderID", "Name", "Last_Refill", "Liters"])

# Load Credentials
if "gcp_service_account" in st.secrets:
    creds = dict(st.secrets["gcp_service_account"])
else:
    try:
        with open("credentials.json") as f:
            creds = json.load(f)
    except FileNotFoundError:
        st.error("Credentials missing!")
        st.stop()

# Initialize Connection
try:
    spread = Spread("FuelTracker", config=creds)
    df = fetch_data(spread)
except Exception as e:
    st.error(f"Connection Failed: {e}")
    st.stop()

# --- 4. HELPER FUNCTIONS ---
def clean_id(text):
    return str(text).lower().replace(" ", "").replace("-", "").strip()

def get_rider_status(rider_id, current_df):
    s_id = clean_id(rider_id)
    match_df = current_df.copy()
    match_df['match_id'] = match_df['RiderID'].apply(clean_id)
    rider_row = match_df[match_df['match_id'] == s_id]
    
    if rider_row.empty:
        return "NOT_FOUND", None, None
    
    name = rider_row.iloc[0]['Name']
    last_val = rider_row.iloc[0]['Last_Refill']
    
    if pd.isna(last_val) or str(last_val).strip() == "":
        return "ELIGIBLE", name, None

    try:
        last_dt = datetime.strptime(str(last_val), "%Y-%m-%d %H:%M:%S")
        unlock_dt = last_dt + timedelta(hours=LOCKOUT_HOURS)
        if datetime.now() < unlock_dt:
            return "LOCKED", name, unlock_dt
        return "ELIGIBLE", name, unlock_dt
    except:
        return "DATE_ERROR", name, None

# --- 5. MAIN INTERFACE ---
st.title("⛽ FuelGuard Pro: সেন্ট্রাল ফুয়েল মনিটরিং")

query_params = st.query_params
scanned_id = query_params.get("rider", st.text_input("🔍 Scan QR or Enter Vehicle ID"))

if scanned_id:
    status, rider_name, unlock_time = get_rider_status(scanned_id, df)
    
    if status == "NOT_FOUND":
        st.warning(f"❌ আইডি '{scanned_id}' পাওয়া যায়নি।")
    elif status == "DATE_ERROR":
        st.error(f"❗ ডাটা ফরম্যাটে ভুল।")
    else:
        st.header(f"👤 রাইডার: {rider_name}")
        
        if status == "LOCKED":
            st.error("### 🚫 তেল দেওয়া যাবে না (Locked)")
            diff = unlock_time - datetime.now()
            st.subheader(f"অপেক্ষা করুন: {diff.days} দিন {diff.seconds//3600} ঘণ্টা")
        
        else:
            st.success("### ✅ তেল পাওয়ার যোগ্য (Eligible)")
            
            # ৩ নম্বর পয়েন্ট: ক্যামেরা এবং ইনপুট
            col1, col2 = st.columns(2)
            with col1:
                liters = st.number_input("লিটারের পরিমাণ (Liters)", 1.0, 100.0, 5.0)
                # ৫ নম্বর পয়েন্ট: দ্রুত আপডেটের জন্য কনফার্মেশন
                save_btn = st.button("💾 Confirm & Save to Cloud")
            
            with col2:
                photo = st.camera_input("নিরাপত্তার জন্য গাড়ির ছবি তুলুন")
            
            if save_btn:
                if photo is not None:
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    s_id = clean_id(scanned_id)
                    
                    # ডাটা আপডেট
                    mask = df['RiderID'].apply(clean_id) == s_id
                    df.loc[mask, 'Last_Refill'] = now_str
                    df.loc[mask, 'Liters'] = liters
                    
                    try:
                        spread.df_to_sheet(df, index=False, replace=True)
                        st.cache_data.clear() 
                        st.success(f"✅ সফল! {rider_name}-কে {liters} লিটার প্রদান করা হয়েছে।")
                        st.balloons()
                        st.rerun() 
                    except Exception as e:
                        st.error(f"Sync Failed: {e}")
                else:
                    st.warning("⚠️ ছবি তোলা বাধ্যতামূলক। ছবি ছাড়া তথ্য সেভ হবে না।")

# --- 6. SIDEBAR: ADMIN & ANALYTICS (৪ নম্বর পয়েন্ট) ---
st.sidebar.title("⚙️ এডমিন প্যানেল")

# লাইভ রিপোর্ট
st.sidebar.subheader("📊 আজকের লাইভ রিপোর্ট")
try:
    df_report = df.copy()
    df_report['Last_Refill'] = pd.to_datetime(df_report['Last_Refill'], errors='coerce')
    today = datetime.now().date()
    today_df = df_report[df_report['Last_Refill'].dt.date == today]
    
    st.sidebar.metric("আজকের মোট রাইডার", len(today_df))
    st.sidebar.metric("মোট লিটার বিতরণ", f"{today_df['Liters'].astype(float).sum()} L")
except:
    st.sidebar.write("রিপোর্ট লোড করা যাচ্ছে না।")

if st.sidebar.button("🔄 ডাটা রিফ্রেশ করুন"):
    st.cache_data.clear()
    st.rerun()

# রেজিস্ট্রেশন এবং QR জেনারেটর
with st.sidebar.expander("📝 নতুন রাইডার রেজিস্ট্রেশন"):
    with st.form("reg_form"):
        reg_id = st.text_input("Vehicle ID")
        reg_name = st.text_input("Full Name")
        submit = st.form_submit_button("সেভ করুন")
        if submit and reg_id and reg_name:
            new_row = pd.DataFrame([{"RiderID": reg_id, "Name": reg_name, "Last_Refill": "", "Liters": 0}])
            updated_df = pd.concat([df, new_row], ignore_index=True)
            spread.df_to_sheet(updated_df, index=False, replace=True)
            st.cache_data.clear()
            st.success("রেজিস্টার্ড হয়েছে!")
            st.rerun()

with st.sidebar.expander("📥 কিউআর কোড তৈরি"):
    qr_input = st.text_input("আইডি দিন")
    if st.button("QR তৈরি করুন"):
        link = f"{APP_URL}?rider={qr_input}"
        qr_img = qrcode.make(link)
        buf = io.BytesIO()
        qr_img.save(buf, format="PNG")
        st.image(buf.getvalue())
        st.download_button("ডাউনলোড", buf.getvalue(), f"{qr_input}.png")
