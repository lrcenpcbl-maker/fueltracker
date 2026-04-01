import streamlit as st
from gspread_pandas import Spread
import pandas as pd
from datetime import datetime, timedelta
import qrcode
import io
import random

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

# --- 2. DATABASE CONNECTION & DATA FETCHING ---
@st.cache_data(ttl=5)
def fetch_data(_spread_obj, sheet_name):
    try:
        return _spread_obj.sheet_to_df(sheet=sheet_name, index=0)
    except Exception:
        return pd.DataFrame()

if "gcp_service_account" in st.secrets:
    creds = dict(st.secrets["gcp_service_account"])
    try:
        spread = Spread("FuelTracker", config=creds)
        df_riders = fetch_data(spread, 'Riders')
        df_stations = fetch_data(spread, 'Stations')
    except Exception as e:
        st.error(f"Connection Failed: {e}")
        st.stop()
else:
    st.error("Credentials missing in Streamlit Secrets!")
    st.stop()

# --- 3. SESSION STATE INITIALIZATION ---
if "pump_logged_in" not in st.session_state:
    st.session_state.pump_logged_in = False
    st.session_state.station_info = None

# --- 4. HELPER FUNCTIONS ---
def clean_id(text):
    return str(text).lower().replace(" ", "").replace("-", "").strip()

# --- 5. PUMP LOGIN & REGISTRATION ---
if not st.session_state.pump_logged_in:
    st.title("⛽ FuelGuard: পাম্প স্টেশন এক্সেস")
    tab_login, tab_reg = st.tabs(["🔐 লগইন", "📝 নতুন স্টেশন নিবন্ধন"])

    with tab_login:
        s_id = st.text_input("স্টেশন আইডি (Station ID)")
        s_pin = st.text_input("গোপন পিন (PIN)", type="password")
        if st.button("প্রবেশ করুন"):
            match = df_stations[(df_stations['StationID'] == s_id.upper()) & (df_stations['PIN'] == s_pin)]
            if not match.empty:
                st.session_state.pump_logged_in = True
                st.session_state.station_info = match.iloc[0].to_dict()
                st.rerun()
            else:
                st.error("ভুল আইডি অথবা পিন!")

    with tab_reg:
        with st.form("reg_station"):
            new_name = st.text_input("পাম্পের নাম")
            new_loc = st.selectbox("অবস্থান (জেলা)", BD_DISTRICTS)
            if st.form_submit_button("নিবন্ধন করুন"):
                new_id = f"PUMP-{len(df_stations) + 101}"
                new_pin = str(random.randint(1000, 9999))
                new_row = pd.DataFrame([{"StationID": new_id, "StationName": new_name, "Location": new_loc, "PIN": new_pin}])
                spread.df_to_sheet(pd.concat([df_stations, new_row]), sheet='Stations', index=False, replace=True)
                st.success(f"নিবন্ধন সফল! আইডি: {new_id}, পিন: {new_pin}")
    
    st.info("💡 রাইডাররা শুধু তথ্য দেখতে চাইলে লগইন ছাড়াই কিউআর স্ক্যান করতে পারবেন।")
    # রাইডাররা যেন লগইন ছাড়াই তাদের স্ট্যাটাস চেক করতে পারে তার জন্য একটি বাটন
    if st.button("🔍 শুধুমাত্র রাইডার স্ট্যাটাস চেক করুন"):
        st.session_state.pump_logged_in = "VISITOR"
        st.rerun()
    st.stop()

# --- 6. MAIN APP INTERFACE ---
st.sidebar.title(f"🏪 {st.session_state.station_info['StationName'] if st.session_state.station_info else 'Visitor Mode'}")
if st.sidebar.button("Logout"):
    st.session_state.pump_logged_in = False
    st.rerun()

st.title("⛽ FuelGuard Pro")

# সার্চ বক্স
scanned_id = st.text_input("🔍 রাইডার আইডি লিখুন বা স্ক্যান করুন", value=st.query_params.get("rider", ""))

if scanned_id:
    s_id = clean_id(scanned_id)
    mask = df_riders['RiderID'].apply(clean_id) == s_id
    rider_row = df_riders[mask]

    if rider_row.empty:
        st.warning("❌ রাইডার পাওয়া যায়নি।")
    else:
        r_data = rider_row.iloc[0]
        st.header(f"👤 রাইডার: {r_data['Name']} ({r_data['RiderID']})")
        
        # এলিজিবিলিটি চেক
        eligible = True
        unlock_time = None
        if r_data['Last_Refill'] != "":
            last_dt = datetime.strptime(str(r_data['Last_Refill']), "%Y-%m-%d %H:%M:%S")
            unlock_time = last_dt + timedelta(hours=LOCKOUT_HOURS)
            if datetime.now() < unlock_time:
                eligible = False

        if not eligible:
            st.error(f"🚫 লকড! পরবর্তীতে পাবেন: {unlock_time.strftime('%b %d, %I:%M %p')}")
        else:
            st.success("✅ এই রাইডার বর্তমানে তেল পাওয়ার যোগ্য।")
            
            # শুধুমাত্র পাম্প অপারেটর হলে ডাটা এন্ট্রি করতে পারবে
            if st.session_state.station_info:
                with st.expander("🛠 তেল প্রদান নিশ্চিত করুন (অপারেটর প্যানেল)"):
                    f_type = st.selectbox("তেলের ধরন", ["Octane", "Petrol", "Diesel"])
                    liters = st.number_input("লিটার", 1.0, 50.0, 5.0)
                    photo = st.camera_input("গাড়ির ছবি তুলুন")
                    
                    if st.button("💾 Confirm & Save"):
                        if photo:
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            # ১. রাইডার শিট আপডেট
                            df_riders.loc[mask, 'Last_Refill'] = now_str
                            spread.df_to_sheet(df_riders, sheet='Riders', index=False, replace=True)
                            
                            # ২. ট্রানজেকশন শিটে সেভ
                            trans_log = pd.DataFrame([{
                                "Timestamp": now_str,
                                "StationID": st.session_state.station_info['StationID'],
                                "StationName": st.session_state.station_info['StationName'],
                                "RiderID": r_data['RiderID'],
                                "FuelType": f_type,
                                "Liters": liters
                            }])
                            spread.df_to_sheet(trans_log, sheet='Transactions', index=False, append=True)
                            
                            st.success("ট্রানজেকশন সফল!")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error("ছবি তোলা বাধ্যতামূলক।")
            else:
                st.warning("⚠️ তেল প্রদান নিশ্চিত করতে পাম্প আইডি দিয়ে লগইন করুন।")

# --- 7. SIDEBAR FEATURES (ADMIN & QR) ---
if st.session_state.station_info:
    with st.sidebar.expander("📝 নতুন রাইডার নিবন্ধন"):
        with st.form("new_rider"):
            d_code = st.selectbox("জেলা", BD_DISTRICTS)
            r_num = st.text_input("গাড়ির নাম্বার")
            r_name = st.text_input("নাম")
            if st.form_submit_button("নিবন্ধন"):
                full_id = f"{d_code}-{r_num}".upper()
                new_r = pd.DataFrame([{"RiderID": full_id, "Name": r_name, "Last_Refill": "", "Liters": 0}])
                spread.df_to_sheet(pd.concat([df_riders, new_r]), sheet='Riders', index=False, replace=True)
                st.success("রাইডার নিবন্ধিত!")

    with st.sidebar.expander("📥 কিউআর কোড জেনারেটর"):
        qr_id = st.text_input("আইডি দিন")
        if st.button("QR তৈরি করুন"):
            qr_link = f"{APP_URL}?rider={qr_id.upper()}"
            qr = qrcode.make(qr_link)
            buf = io.BytesIO()
            qr.save(buf, format="PNG")
            st.image(buf.getvalue())
