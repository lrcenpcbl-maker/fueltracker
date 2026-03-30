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
APP_URL = "https://fuel-tracker.streamlit.app" # Replace with your live URL

# --- 2. SECURE DATABASE CONNECTION ---
if "gcp_service_account" in st.secrets:
    creds = dict(st.secrets["gcp_service_account"])
else:
    try:
        with open("credentials.json") as f:
            creds = json.load(f)
    except FileNotFoundError:
        st.error("Credentials not found. Please setup Streamlit Secrets.")
        st.stop()

try:
    # Connect to the Google Sheet 'FuelTracker'
    spread = Spread("FuelTracker", config=creds)
    df = spread.sheet_to_df(index=0)
    # Clean headers: remove accidental spaces
    df.columns = df.columns.str.strip()
except Exception as e:
    st.error(f"Google Sheets Connection Error: {e}")
    st.stop()

# --- 3. CORE LOGIC (Case-Insensitive) ---
def get_rider_status(rider_id):
    if df.empty:
        return "EMPTY_DATABASE", None, None
    
    # Normalize ID for comparison (lowercase and no spaces)
    search_id = str(rider_id).strip().lower()
    
    # Create temporary matching column
    temp_df = df.copy()
    temp_df['match_id'] = temp_df['RiderID'].astype(str).str.strip().str.lower()
    
    rider_row = temp_df[temp_df['match_id'] == search_id]
    
    if rider_row.empty:
        return "NOT_FOUND", None, None
    
    name = rider_row.iloc[0]['Name']
    last_refill_val = rider_row.iloc[0]['Last_Refill']
    
    if pd.isna(last_refill_val) or str(last_refill_val).strip() == "":
        return "ELIGIBLE", name, None

    try:
        last_dt = datetime.strptime(str(last_refill_val), "%Y-%m-%d %H:%M:%S")
        unlock_dt = last_dt + timedelta(hours=LOCKOUT_HOURS)
    except Exception:
        return "DATE_ERROR", name, None
    
    if datetime.now() < unlock_dt:
        return "LOCKED", name, unlock_dt
    return "ELIGIBLE", name, unlock_dt

# --- 4. MAIN INTERFACE ---
st.title("⛽ FuelGuard 72-Hour System")

# Get ID from URL parameter (e.g. ?rider=BDP123)
query_params = st.query_params
scanned_id = query_params.get("rider", st.text_input("Enter/Scan Rider ID (Case-Insensitive)"))

if scanned_id:
    status, rider_name, unlock_time = get_rider_status(scanned_id)
    
    if status == "NOT_FOUND":
        st.warning(f"⚠️ Rider ID '{scanned_id}' not found in FuelTracker.")
    elif status == "DATE_ERROR":
        st.error(f"❌ Date format error in Google Sheet for {rider_name}.")
    else:
        st.header(f"Rider: {rider_name}")
        
        if status == "LOCKED":
            st.error("### ❌ ACCESS DENIED")
            diff = unlock_time - datetime.now()
            st.subheader(f"Wait: {diff.days}d {diff.seconds//3600}h remaining")
            st.info(f"Next Refill: {unlock_time.strftime('%b %d, %I:%M %p')}")
        
        else:
            st.success("### ✅ ELIGIBLE")
            liters = st.number_input("Liters Issued", min_value=1.0, max_value=50.0, step=0.5)
            
            if st.button("Confirm & Save Transaction"):
                # Use current time
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Find the correct row in the original dataframe
                search_id = str(scanned_id).strip().lower()
                # Update Last_Refill where lowercase ID matches
                mask = df['RiderID'].astype(str).str.strip().str.lower() == search_id
                df.loc[mask, 'Last_Refill'] = now_str
                
                # Save to Google Sheets
                spread.df_to_sheet(df, index=False, replace=True)
                st.cache_data.clear()
                st.balloons()
                st.success("Record Updated Successfully!")

# --- 5. QR GENERATOR (Sidebar) ---
st.sidebar.title("Admin Tools")
with st.sidebar.expander("Register / Generate QR"):
    new_id = st.text_input("New Rider ID")
    if st.button("Create QR Code"):
        # This link will be scanned by pump operators
        full_link = f"{APP_URL}?rider={new_id}"
        qr = qrcode.make(full_link)
        buf = io.BytesIO()
        qr.save(buf, format="PNG")
        st.image(buf.getvalue(), caption=f"Permanent QR for {new_id}")
        st.download_button("Download QR Image", buf.getvalue(), f"{new_id}_QR.png")
