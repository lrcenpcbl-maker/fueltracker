import streamlit as st
from gspread_pandas import Spread
import pandas as pd
from datetime import datetime, timedelta
import qrcode
import io
import json

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="FuelGuard 72h", page_icon="⛽")
LOCKOUT_HOURS = 72

# IMPORTANT: Change this to your actual Streamlit URL after you deploy!
APP_URL = "https://fuel-tracker.streamlit.app" 

# --- 2. DATABASE CONNECTION (Secrets vs Local) ---
if "gcp_service_account" in st.secrets:
    creds = dict(st.secrets["gcp_service_account"])
else:
    try:
        with open("credentials.json") as f:
            creds = json.load(f)
    except FileNotFoundError:
        st.error("Credentials not found. Please configure Streamlit Secrets.")
        st.stop()

try:
    # Connecting to your Google Sheet: FuelTracker
    spread = Spread("FuelTracker", config=creds)
    df = spread.sheet_to_df(index=0)
except Exception as e:
    st.error(f"Google Sheets Connection Error: {e}")
    st.stop()

# --- 3. CORE LOGIC ---
def get_rider_status(rider_id):
    # Ensure ID is treated as a string for matching
    rider_row = df[df['RiderID'].astype(str) == str(rider_id)]
    
    if rider_row.empty:
        return "NOT_FOUND", None, None
    
    last_refill_val = rider_row.iloc[0]['Last_Refill']
    name = rider_row.iloc[0]['Name']
    
    if pd.isna(last_refill_val) or last_refill_val == "":
        return "ELIGIBLE", name, None

    last_dt = datetime.strptime(str(last_refill_val), "%Y-%m-%d %H:%M:%S")
    unlock_dt = last_dt + timedelta(hours=LOCKOUT_HOURS)
    
    if datetime.now() < unlock_dt:
        return "LOCKED", name, unlock_dt
    return "ELIGIBLE", name, unlock_dt

# --- 4. THE INTERFACE ---
st.title("⛽ FuelGuard 72-Hour System")

# Get ID from URL (e.g., ?rider=BDP123)
query_params = st.query_params
scanned_id = query_params.get("rider", st.text_input("Enter/Scan Rider ID"))

if scanned_id:
    status, rider_name, unlock_time = get_rider_status(scanned_id)
    
    if status == "NOT_FOUND":
        st.warning(f"⚠️ Rider ID '{scanned_id}' is not registered in FuelTracker.")
    else:
        st.header(f"Rider: {rider_name}")
        
        if status == "LOCKED":
            st.error("### ❌ NOT ELIGIBLE")
            diff = unlock_time - datetime.now()
            st.subheader(f"Wait: {diff.days}d {diff.seconds//3600}h remaining")
            st.info(f"Next available refill: {unlock_time.strftime('%b %d, %I:%M %p')}")
        
        else:
            st.success("### ✅ ELIGIBLE FOR FUEL")
            liters = st.number_input("Liters Issued", min_value=1.0, max_value=20.0, step=0.5)
            
            if st.button("Confirm & Save Transaction"):
                # Update Timestamp in Dataframe
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                df.loc[df['RiderID'].astype(str) == str(scanned_id), 'Last_Refill'] = now_str
                
                # Push back to Google Sheets
                spread.df_to_sheet(df, index=False, replace=True)
                st.cache_data.clear()
                st.balloons()
                st.success("Transaction Saved. Rider is now locked for 72 hours.")

        # --- PUBLIC RECORD (For transparency) ---
        st.divider()
        st.write("#### 📋 Public Record")
        st.write(f"Last recorded refill: **{df.loc[df['RiderID'].astype(str) == str(scanned_id), 'Last_Refill'].values[0]}**")

# --- 5. QR CODE GENERATOR (Sidebar) ---
with st.sidebar.expander("Register New Rider / QR"):
    new_id = st.text_input("New Rider ID")
    if st.button("Generate QR"):
        full_link = f"{APP_URL}?rider={new_id}"
        qr = qrcode.make(full_link)
        buf = io.BytesIO()
        qr.save(buf, format="PNG")
        st.image(buf.getvalue(), caption=f"QR for {new_id}")
        st.download_button("Download QR", buf.getvalue(), f"{new_id}.png")
