import streamlit as st
from gspread_pandas import Spread
import pandas as pd
from datetime import datetime, timedelta
import qrcode
import io

# --- 1. SECURE CONNECTION ---
# This pulls from the 'Secrets' tab in Streamlit Cloud (where you paste your JSON)
if "gcp_service_account" in st.secrets:
    creds = dict(st.secrets["gcp_service_account"])
else:
    # This is for testing on your local computer
    import json
    with open("credentials.json") as f:
        creds = json.load(f)

# Connect to your sheet named 'FuelTracker'
try:
    spread = Spread("FuelTracker", config=creds)
    df = spread.sheet_to_df(index=0)
except Exception as e:
    st.error(f"Cannot connect to FuelTracker sheet: {e}")
    st.stop()

# --- 2. 72-HOUR LOGIC ---
def get_status(rider_id):
    rider_data = df[df['RiderID'] == str(rider_id)]
    if rider_data.empty:
        return "NOT_FOUND", None, None
    
    last_refill_str = rider_data.iloc[0]['Last_Refill']
    if pd.isna(last_refill_str) or last_refill_str == "":
        return "ELIGIBLE", "First time refueling", None

    last_refill = datetime.strptime(str(last_refill_str), "%Y-%m-%d %H:%M:%S")
    unlock_time = last_refill + timedelta(hours=72)
    
    if datetime.now() < unlock_time:
        diff = unlock_time - datetime.now()
        return "LOCKED", f"{diff.days}d {diff.seconds//3600}h remaining", unlock_time
    return "ELIGIBLE", "72 hours have passed", unlock_time

# --- 3. UI INTERFACE ---
st.title("⛽ FuelTracker: 72-Hour Guard")

# Auto-detect ID from QR URL: your-app.com/?rider=ID
query_params = st.query_params
scanned_id = query_params.get("rider", st.text_input("Enter Rider ID (e.g. BDP-1234)"))

if scanned_id:
    status, msg, unlock_dt = get_status(scanned_id)
    
    if status == "NOT_FOUND":
        st.warning("⚠️ Rider ID not registered in FuelTracker.")
    elif status == "LOCKED":
        st.error(f"### ❌ {msg}")
        st.info(f"Next Refill Allowed: {unlock_dt.strftime('%b %d, %I:%M %p')}")
    else:
        st.success(f"### ✅ {msg}")
        amount = st.number_input("Amount Issued (Liters)", min_value=1.0)
        if st.button("Confirm Transaction"):
            # Update local data
            now_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            df.loc[df['RiderID'] == str(scanned_id), 'Last_Refill'] = now_now
            
            # Save back to Google Sheets
            spread.df_to_sheet(df, index=False, replace=True)
            st.cache_data.clear()
            st.success("Record Saved. Rider locked for 72 hours.")
            st.balloons()

# --- 4. QR GENERATOR ---
with st.expander("Generate New Rider QR"):
    new_id = st.text_input("New ID to Register")
    if st.button("Create QR Code"):
        # Replace the URL below with your actual deployed Streamlit URL
        my_url = f"https://fuel-tracker.streamlit.app/?rider={new_id}"
        qr = qrcode.make(my_url)
        buf = io.BytesIO()
        qr.save(buf, format="PNG")
        st.image(buf.getvalue())
        st.download_button("Download QR", buf.getvalue(), f"{new_id}_QR.png")