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
APP_URL = "https://fuel-tracker.streamlit.app" # Update this to your live URL

# --- 2. DATABASE CONNECTION ---
@st.cache_data(ttl=10) # Cache only for 10 seconds to ensure freshness
def fetch_data(_spread_obj):
    df = _spread_obj.sheet_to_df(index=0)
    df.columns = df.columns.str.strip() # Clean headers
    return df

if "gcp_service_account" in st.secrets:
    creds = dict(st.secrets["gcp_service_account"])
else:
    try:
        with open("credentials.json") as f:
            creds = json.load(f)
    except FileNotFoundError:
        st.error("Credentials missing. Setup Streamlit Secrets.")
        st.stop()

try:
    spread = Spread("FuelTracker", config=creds)
    # Load data
    df = fetch_data(spread)
except Exception as e:
    st.error(f"Google Sheets Error: {e}")
    st.stop()

# --- 3. CORE LOGIC (Case-Insensitive) ---
def get_rider_status(rider_id, current_df):
    search_id = str(rider_id).strip().lower()
    temp_df = current_df.copy()
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
        if datetime.now() < unlock_dt:
            return "LOCKED", name, unlock_dt
        return "ELIGIBLE", name, unlock_dt
    except:
        return "DATE_ERROR", name, None

# --- 4. MAIN UI ---
st.title("⛽ FuelGuard 72-Hour System")

# URL parameter support
query_params = st.query_params
scanned_id = query_params.get("rider", st.text_input("Enter/Scan Rider ID"))

if scanned_id:
    status, rider_name, unlock_time = get_rider_status(scanned_id, df)
    
    if status == "NOT_FOUND":
        st.warning(f"ID '{scanned_id}' not found.")
    else:
        st.header(f"Rider: {rider_name}")
        
        if status == "LOCKED":
            st.error("### ❌ ACCESS DENIED")
            diff = unlock_time - datetime.now()
            st.subheader(f"Wait: {diff.days}d {diff.seconds//3600}h remaining")
            st.info(f"Available on: {unlock_time.strftime('%b %d, %I:%M %p')}")
        
        else:
            st.success("### ✅ ELIGIBLE")
            if st.button("Confirm & Save Refill"):
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Update the main dataframe
                search_id = str(scanned_id).strip().lower()
                mask = df['RiderID'].astype(str).str.strip().str.lower() == search_id
                df.loc[mask, 'Last_Refill'] = now_str
                
                # SAVE TO GOOGLE SHEETS
                try:
                    spread.df_to_sheet(df, index=False, replace=True)
                    st.cache_data.clear() # CLEAR CACHE IMMEDIATELY
                    st.success("Record saved permanently to Google Sheets!")
                    st.balloons()
                    st.rerun() # Refresh the page to show "LOCKED" status
                except Exception as e:
                    st.error(f"Save failed: {e}")

# --- 5. ADMIN TOOLS ---
st.sidebar.title("Admin")
if st.sidebar.button("🔄 Force Data Refresh"):
    st.cache_data.clear()
    st.rerun()

with st.sidebar.expander("Register / QR Generator"):
    new_id = st.text_input("New Rider ID")
    if st.button("Create QR"):
        full_link = f"{APP_URL}?rider={new_id}"
        qr = qrcode.make(full_link)
        buf = io.BytesIO()
        qr.save(buf, format="PNG")
        st.image(buf.getvalue())
        st.download_button("Download QR", buf.getvalue(), f"{new_id}.png")
