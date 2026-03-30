import streamlit as st
from gspread_pandas import Spread
import pandas as pd
from datetime import datetime, timedelta
import qrcode
import io
import json

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="FuelGuard 72h", page_icon="⛽", layout="wide")
LOCKOUT_HOURS = 72
APP_URL = "https://fuel-tracker.streamlit.app" # UPDATE THIS after deployment

# --- 2. BANGLA INSTRUCTIONS DIALOG ---
@st.dialog("ব্যবহার নির্দেশিকা (How to Use)")
def show_instructions():
    st.markdown("""
    ### ⛽ ফুয়েলগার্ড (FuelGuard) এ স্বাগতম
    এই অ্যাপটি জ্বালানি বণ্টন ব্যবস্থা স্বচ্ছ এবং নিরপেক্ষ রাখার জন্য তৈরি করা হয়েছে।
    
    **নিয়মাবলী:**
    1. **৭২ ঘণ্টার নিয়ম:** একবার তেল নেওয়ার পর পরবর্তী **৭২ ঘণ্টা** পর্যন্ত ওই আইডি দিয়ে পুনরায় তেল নেওয়া যাবে না।
    2. **কিউআর কোড স্ক্যান:** রাইডারের আইডি কার্ডের QR কোড স্ক্যান করুন অথবা ম্যানুয়ালি আইডি ইনপুট দিন।
    3. **স্ট্যাটাস চেক:** - ✅ **সবুজ সংকেত:** রাইডার তেল পাওয়ার যোগ্য। লিটার ইনপুট দিয়ে 'Confirm' বাটনে চাপ দিন।
        - 🚫 **লাল সংকেত:** রাইডার বর্তমানে লকড। স্ক্রিনে প্রদর্শিত সময় শেষ না হওয়া পর্যন্ত অপেক্ষা করতে হবে।
    4. **ডেটা সেভ:** প্রতিবার তেল দেওয়ার পর অবশ্যই **'Confirm & Save'** বাটনে ক্লিক করবেন।

    *যেকোনো সমস্যায় অ্যাডমিনের সাথে যোগাযোগ করুন।*
    """)
    if st.button("ঠিক আছে, শুরু করি"):
        st.session_state.initialized = True
        st.rerun()

# Trigger instructions on first visit
if "initialized" not in st.session_state:
    show_instructions()

# --- 3. SECURE DATABASE CONNECTION ---
@st.cache_data(ttl=5)
def fetch_data(_spread_obj):
    try:
        data = _spread_obj.sheet_to_df(index=0)
        data.columns = data.columns.str.strip()
        return data
    except Exception as e:
        st.error(f"Error reading sheet: {e}")
        return pd.DataFrame(columns=["RiderID", "Name", "Last_Refill"])

# Load Credentials
if "gcp_service_account" in st.secrets:
    creds = dict(st.secrets["gcp_service_account"])
else:
    try:
        with open("credentials.json") as f:
            creds = json.load(f)
    except FileNotFoundError:
        st.error("Credentials missing! Add them to Streamlit Secrets.")
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
st.title("⛽ FuelGuard: 72-Hour Anti-Fraud System")

# Handle QR Scans via URL (?rider=ID)
query_params = st.query_params
scanned_id = query_params.get("rider", st.text_input("🔍 Scan QR or Enter Vehicle ID"))

if scanned_id:
    status, rider_name, unlock_time = get_rider_status(scanned_id, df)
    
    if status == "NOT_FOUND":
        st.warning(f"❌ ID '{scanned_id}' not found in database.")
    elif status == "DATE_ERROR":
        st.error(f"❗ Data Format Error in Sheet for {rider_name}.")
    else:
        st.header(f"👤 Rider: {rider_name}")
        
        if status == "LOCKED":
            st.error("### 🚫 REFILL DENIED")
            diff = unlock_time - datetime.now()
            st.subheader(f"Status: Wait {diff.days}d {diff.seconds//3600}h more")
            st.info(f"Available: {unlock_time.strftime('%b %d, %I:%M %p')}")
        
        else:
            st.success("### ✅ ELIGIBLE FOR REFILL")
            liters = st.number_input("Liters Issued", 1.0, 100.0, 5.0)
            
            if st.button("💾 Confirm & Save to Cloud"):
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                s_id = clean_id(scanned_id)
                
                mask = df['RiderID'].apply(clean_id) == s_id
                df.loc[mask, 'Last_Refill'] = now_str
                
                try:
                    spread.df_to_sheet(df, index=False, replace=True)
                    st.cache_data.clear() 
                    st.success("Data synced to Google Sheets!")
                    st.balloons()
                    st.rerun() 
                except Exception as e:
                    st.error(f"Sync Failed: {e}")

# --- 6. SIDEBAR: REGISTRATION & ADMIN ---
st.sidebar.title("⚙️ Administration")

# Instructions button in sidebar for manual access
if st.sidebar.button("❓ নির্দেশিকা (Instructions)"):
    show_instructions()

if st.sidebar.button("🔄 Refresh Database"):
    st.cache_data.clear()
    st.rerun()

# Registration Form
with st.sidebar.expander("📝 Register New Rider", expanded=False):
    with st.form("reg_form"):
        reg_id = st.text_input("Vehicle ID")
        reg_name = st.text_input("Full Name")
        submit = st.form_submit_button("Register & Save")
        
        if submit and reg_id and reg_name:
            if clean_id(reg_id) in df['RiderID'].apply(clean_id).values:
                st.error("This ID is already registered!")
            else:
                new_row = pd.DataFrame([{"RiderID": reg_id, "Name": reg_name, "Last_Refill": ""}])
                updated_df = pd.concat([df, new_row], ignore_index=True)
                spread.df_to_sheet(updated_df, index=False, replace=True)
                st.cache_data.clear()
                st.success("Registered!")
                st.rerun()

# QR Generator
with st.sidebar.expander("📥 Generate QR Code"):
    qr_input = st.text_input("Enter ID for QR")
    if st.button
