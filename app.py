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

# --- 2. USAGE GUIDE POP-UP ---
# টেক্সটটি আলাদা ভেরিয়েবলে রাখা হয়েছে যাতে কোডের সাথে না মিশে
GUIDE_TEXT = """
### ⛽ এই অ্যাপটি কীভাবে কাজ করে?
1. **রাইডার:** আইডি সার্চ করে নিজের এলিজিবিলিটি চেক করতে পারবেন.
2. **পাম্প:** তেল দিতে হলে অবশ্যই স্টেশন আইডি ও পিন দিয়ে লগইন করতে হবে.
3. **নিরাপত্তা:** তেল দেওয়ার সময় গাড়ির ছবি তোলা এবং তেলের ধরন সিলেক্ট করা বাধ্যতামূলক.
4. **নিয়ম:** একবার তেল নিলে পরবর্তী **৭২ ঘণ্টা** ওই আইডি লক থাকবে.

**বিঃদ্রঃ** ভুল পিন দিলে বা ছবি না তুললে ডাটা সেভ হবে না.
"""

@st.dialog("ব্যবহার নির্দেশিকা (User Guide)")
def show_usage_guide():
    st.markdown(GUIDE_TEXT)
    if st.button("বুঝেছি, শুরু করি"):
        st.session_state.show_guide = False
        st.rerun()

if "show_guide" not in st.session_state:
    st.session_state.show_guide = True

if st.session_state.show_guide:
    show_usage_guide()

# --- 3. DATABASE CONNECTION ---
@st.cache_data(ttl=5)
def fetch_data(_spread_obj, sheet_name):
    try:
        return _spread_obj.sheet_to_df(sheet=sheet_name, index=0)
    except:
        return pd.DataFrame()

if "gcp_service_account" in st.secrets:
    creds = dict(st.secrets["gcp_service_account"])
    try:
        spread = Spread("FuelTracker", config=creds)
        df_riders = fetch_data(spread, 'Riders')
        df_stations = fetch_data(spread, 'Stations')
    except Exception as e:
        st.error(f"Database Connection Failed: {e}")
        st.stop()
else:
    st.error("Credentials missing in Streamlit Secrets!")
    st.stop()

# --- 4. SESSION STATE ---
if "pump_logged_in" not in st.session_state:
    st.session_state.pump_logged_in = False
    st.session_state.station_info = None

def clean_id(text):
    return str(text).lower().replace(" ", "").replace("-", "").strip()

# --- 5. LOGIN & REGISTRATION ---
if not st.session_state.pump_logged_in:
    st.title("⛽ FuelGuard: পাম্প লগইন")
    t_login, t_reg = st.tabs(["🔐 লগইন", "📝 নতুন স্টেশন নিবন্ধন"])

    with t_login:
        s_id_in = st.text_input("স্টেশন আইডি (Station ID)")
        s_pin_in = st.text_input("পিন (PIN)", type="password")
        if st.button("লগইন"):
            if not df_stations.empty:
                match = df_stations[(df_stations['StationID'] == s_id_in.upper()) & (df_stations['PIN'] == str(s_pin_in))]
                if not match.empty:
                    st.session_state.pump_logged_in = True
                    st.session_state.station_info = match.iloc[0].to_dict()
                    st.rerun()
                else:
                    st.error("ভুল আইডি বা পিন!")
            else:
                st.error("স্টেশন ডাটাবেজ খালি।")
        
        st.divider()
        if st.button("🔍 শুধুমাত্র রাইডার স্ট্যাটাস দেখুন"):
            st.session_state.pump_logged_in = "VISITOR"
            st.rerun()

    with t_reg:
        with st.form("st_reg"):
            n_name = st.text_input("পাম্পের নাম")
            n_loc = st.selectbox("জেলা", BD_DISTRICTS)
            if st.form_submit_button("নিবন্ধন করুন"):
                if n_name:
                    new_id = f"PUMP-{len(df_stations) + 101}"
                    new_pin = str(random.randint(1000, 9999))
                    new_st = pd.DataFrame([{"StationID": new_id, "StationName": n_name, "Location": n_loc, "PIN": new_pin}])
                    spread.df_to_sheet(pd.concat([df_stations, new_st]), sheet='Stations', index=False, replace=True)
                    st.success(f"সফল! আইডি: {new_id}, পিন: {new_pin}")
                    st.cache_data.clear()
                    st.rerun()
    st.stop()

# --- 6. MAIN INTERFACE ---
s_name = st.session_state.station_info['StationName'] if st.session_state.station_info else 'Visitor Mode'
st.sidebar.title(f"🏪 {s_name}")
if st.sidebar.button("Log Out"):
    st.session_state.pump_logged_in = False
    st.session_state.station_info = None
    st.rerun()

st.title("⛽ FuelGuard Pro")

search_id = st.text_input("🔍 রাইডার আইডি লিখুন বা স্ক্যান করুন", value=st.query_params.get("rider", ""))

if search_id:
    s_id = clean_id(search_id)
    if not df_riders.empty:
        mask = df_riders['RiderID'].apply(clean_id) == s_id
        rider_row = df_riders[mask]

        if rider_row.empty:
            st.warning("❌ আইডি নিবন্ধিত নয়।")
        else:
            r_data = rider_row.iloc[0]
            st.header(f"👤 রাইডার: {r_data['Name']}")
            
            eligible = True
            unlock_time = None
            if str(r_data['Last_Refill']).strip() != "":
                try:
                    last_dt = datetime.strptime(str(r_data['Last_Refill']), "%Y-%m-%d %H:%M:%S")
                    unlock_time = last_dt + timedelta(hours=LOCKOUT_HOURS)
                    if datetime.now() < unlock_time:
                        eligible = False
                except: pass

            if not eligible:
                st.error(f"🚫 লকড! পরবর্তীতে তেল পাবেন: {unlock_time.strftime('%b %d, %I:%M %p')}")
            else:
                st.success("✅ এই রাইডার বর্তমানে তেল পাওয়ার যোগ্য।")
                
                if st.session_state.station_info:
                    with st.expander("🛠 তেল প্রদান ফরম", expanded=True):
                        f_type = st.selectbox("তেলের ধরন", ["Octane", "Petrol", "Diesel"])
                        liters = st.number_input("লিটার", 1.0, 100.0, 5.0)
                        photo = st.camera_input("গাড়ির ছবি তুলুন")
                        
                        if st.button("💾 কনফার্ম এবং সেভ"):
                            if photo:
                                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                df_riders.loc[mask, 'Last_Refill'] = now_str
                                spread.df_to_sheet(df_riders, sheet='Riders', index=False, replace=True)
                                
                                trans_log = pd.DataFrame([{
                                    "Timestamp": now_str,
                                    "StationID": st.session_state.station_info['StationID'],
                                    "StationName": st.session_state.station_info['StationName'],
                                    "RiderID": r_data['RiderID'],
                                    "FuelType": f_type,
                                    "Liters": liters
                                }])
                                spread.df_to_sheet(trans_log, sheet='Transactions', index=False, append=True)
                                st.success("সেভ হয়েছে!")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error("ছবি তোলা বাধ্যতামূলক।")

# --- 7. SIDEBAR ---
if st.session_state.station_info:
    with st.sidebar.expander("📝 রাইডার রেজিস্ট্রেশন"):
        with st.form("new_r"):
            d = st.selectbox("জেলা", BD_DISTRICTS)
            s = st.selectbox("সিরিজ", ["KA", "KHA", "GA", "GHA", "HA", "LA"])
            n = st.text_input("গাড়ির নম্বর")
            name = st.text_input("নাম")
            if st.form_submit_button("নিবন্ধন"):
                f_id = f"{d}-{s}-{n}".upper()
                new_row = pd.DataFrame([{"RiderID": f_id, "Name": name, "Last_Refill": "", "Liters": 0}])
                spread.df_to_sheet(pd.concat([df_riders, new_row]), sheet='Riders', index=False, replace=True)
                st.success("সফল!")
                st.cache_data.clear()
                st.rerun()

    with st.sidebar.expander("📥 কিউআর কোড"):
        qr_in = st.text_input("আইডি দিন")
        if st.button("QR তৈরি করুন"):
            q_link = f"{APP_URL}?rider={qr_in.upper()}"
            img = qrcode.make(q_link)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            st.image(buf.getvalue())
