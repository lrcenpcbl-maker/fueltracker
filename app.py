import streamlit as st
from gspread_pandas import Spread
import pandas as pd
from datetime import datetime, timedelta
import qrcode
from PIL import Image
import io
import json

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="FuelGuard Pro", page_icon="⛽", layout="wide")
LOCKOUT_HOURS = 72
APP_URL = "https://fuel-tracker.streamlit.app" # আপনার আসল অ্যাপ লিঙ্কটি এখানে দিন

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

# --- 2. BANGLA INSTRUCTIONS DIALOG ---
@st.dialog("ব্যবহার নির্দেশিকা (How to Use)")
def show_instructions():
    st.markdown("""
    ### ⛽ ফুয়েলগার্ড (FuelGuard) এ স্বাগতম
    এই অ্যাপটি জ্বালানি বণ্টন ব্যবস্থা স্বচ্ছ এবং নিরপেক্ষ রাখার জন্য তৈরি করা হয়েছে।
    
    **নিয়মাবলী:**
    1. **৭২ ঘণ্টার নিয়ম:** একবার তেল নেওয়ার পর পরবর্তী **৭২ ঘণ্টা** পর্যন্ত ওই আইডি দিয়ে পুনরায় তেল নেওয়া যাবে না।
    2. **কিউআর কোড স্ক্যান:** রাইডারের আইডি কার্ডের QR কোড স্ক্যান করুন অথবা ম্যানুয়ালি আইডি ইনপুট দিন।
    3. **স্ট্যাটাস চেক:** - ✅ **সবুজ সংকেত:** রাইডার তেল পাওয়ার যোগ্য। লিটার লিখে 'Confirm' বাটনে চাপ দিন।
        - 🚫 **লাল সংকেত:** রাইডার লকড। স্ক্রিনে প্রদর্শিত সময় শেষ না হওয়া পর্যন্ত অপেক্ষা করতে হবে।
    4. **ডেটা সেভ:** প্রতিবার তেল দেওয়ার পর অবশ্যই **'Confirm & Save'** বাটনে ক্লিক করবেন।

    **নতুন ফিচারসমূহ:**
    1. **ছবি ভেরিফিকেশন:** তেল দেওয়ার সময় নিরাপত্তার জন্য গাড়ির ছবি তোলা বাধ্যতামূলক।
    2. **সেন্ট্রাল ডাটাবেজ:** যেকোনো পাম্প থেকে তেল নিলেই এই সিস্টেম আপডেট হবে।
    3. **লাইভ রিপোর্ট:** অ্যাডমিন প্যানেলে আজকের মোট রিফিলের হিসাব দেখা যাবে।

    *যেকোনো সমস্যায় অ্যাডমিনের সাথে যোগাযোগ করুন: **vpersonal1123@gmail.com***
    """)
    if st.button("ঠিক আছে, শুরু করি"):
        st.session_state.initialized = True
        st.rerun()

if "initialized" not in st.session_state:
    show_instructions()

# --- 3. DATABASE CONNECTION ---
@st.cache_data(ttl=5)
def fetch_data(_spread_obj):
    try:
        data = _spread_obj.sheet_to_df(index=0)
        data.columns = data.columns.str.strip()
        required_cols = ["RiderID", "Name", "Last_Refill", "Liters"]
        for col in required_cols:
            if col not in data.columns:
                data[col] = "" if col != "Liters" else 0
        return data
    except Exception:
        return pd.DataFrame(columns=["RiderID", "Name", "Last_Refill", "Liters"])

# Load Credentials (Streamlit Secrets)
if "gcp_service_account" in st.secrets:
    creds = dict(st.secrets["gcp_service_account"])
    try:
        spread = Spread("FuelTracker", config=creds)
        df = fetch_data(spread)
    except Exception as e:
        st.error(f"Connection Failed: {e}")
        st.stop()
else:
    st.error("Credentials missing in Streamlit Secrets!")
    st.stop()

# --- 4. HELPER FUNCTIONS ---
def clean_id(text):
    """আইডি থেকে স্পেস ও ড্যাশ সরিয়ে ছোট হাতের অক্ষরে রূপান্তর করে।"""
    return str(text).lower().replace(" ", "").replace("-", "").strip()

# --- 5. MAIN INTERFACE ---
st.title("⛽ FuelGuard Pro: স্মার্ট ফুয়েল মনিটরিং")

# হ্যান্ডেল কিউআর স্ক্যান (URL ?rider=ID)
query_params = st.query_params
scanned_id = query_params.get("rider", st.text_input("🔍 রাইডার আইডি লিখুন বা কিউআর স্ক্যান করুন", placeholder="যেমন: pabna ha 11 0101"))

if scanned_id:
    s_id = clean_id(scanned_id)
    mask = df['RiderID'].apply(clean_id) == s_id
    rider_row = df[mask]

    if rider_row.empty:
        st.warning(f"❌ আইডি '{scanned_id}' পাওয়া যায়নি।")
    else:
        rider_name = rider_row.iloc[0]['Name']
        last_val = rider_row.iloc[0]['Last_Refill']
        actual_id = rider_row.iloc[0]['RiderID']
        
        st.header(f"👤 রাইডার: {rider_name} ({actual_id})")

        eligible = True
        unlock_time = None
        if not (pd.isna(last_val) or str(last_val).strip() == ""):
            try:
                last_dt = datetime.strptime(str(last_val), "%Y-%m-%d %H:%M:%S")
                unlock_time = last_dt + timedelta(hours=LOCKOUT_HOURS)
                if datetime.now() < unlock_time:
                    eligible = False
            except:
                st.error("ডাটাবেজে তারিখের ফরম্যাটে সমস্যা আছে।")

        if not eligible:
            st.error(f"### 🚫 রিফিল রিজেক্ট (Locked)")
            diff = unlock_time - datetime.now()
            st.subheader(f"অপেক্ষা করুন: {diff.days} দিন {diff.seconds//3600} ঘণ্টা")
            st.info(f"পরবর্তীতে পাওয়া যাবে: {unlock_time.strftime('%b %d, %I:%M %p')}")
        
        else:
            st.success("### ✅ রিফিল অনুমোদিত")
            col1, col2 = st.columns(2)
            with col1:
                liters_to_issue = st.number_input("লিটারের পরিমাণ (Liters)", 1.0, 100.0, 5.0)
                confirm_btn = st.button("💾 Confirm & Save to Cloud")
            
            with col2:
                photo = st.camera_input("নিরাপত্তার জন্য গাড়ির ছবি তুলুন")
            
            if confirm_btn:
                if photo is not None:
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    df.loc[mask, 'Last_Refill'] = now_str
                    df.loc[mask, 'Liters'] = liters_to_issue
                    
                    try:
                        spread.df_to_sheet(df, index=False, replace=True)
                        st.cache_data.clear() 
                        st.success(f"✅ সফল! {rider_name}-কে {liters_to_issue} লিটার তেল দেওয়া হয়েছে।")
                        st.balloons()
                        st.rerun() 
                    except Exception as e:
                        st.error(f"Sync Failed: {e}")
                else:
                    st.warning("⚠️ ছবি তোলা বাধ্যতামূলক।")

# --- 6. SIDEBAR: ADMIN, REGISTRATION & QR ---
st.sidebar.title("⚙️ এডমিন প্যানেল")

# নতুন রাইডার রেজিস্ট্রেশন (৬৪ জেলা ভিত্তিক)
with st.sidebar.expander("📝 নতুন রাইডার রেজিস্ট্রেশন", expanded=False):
    with st.form("reg_form"):
        sel_dist = st.selectbox("জেলা/মেট্রো এরিয়া", sorted(BD_DISTRICTS))
        sel_series = st.selectbox("গাড়ির শ্রেণী (Series)", ["KA", "KHA", "GA", "GHA", "CHA", "THA", "HA", "LA", "MA", "BA"])
        sel_num = st.text_input("গাড়ির নাম্বার (যেমন: 11-0101)")
        reg_name = st.text_input("রাইডারের পূর্ণ নাম")
        
        if st.form_submit_button("রেজিস্ট্রেশন সম্পন্ন করুন"):
            if sel_num and reg_name:
                final_id = f"{sel_dist}-{sel_series}-{sel_num}".upper()
                if clean_id(final_id) in df['RiderID'].apply(clean_id).values:
                    st.error("এই আইডি আগে থেকেই নিবন্ধিত!")
                else:
                    new_row = pd.DataFrame([{"RiderID": final_id, "Name": reg_name, "Last_Refill": "", "Liters": 0}])
                    updated_df = pd.concat([df, new_row], ignore_index=True)
                    spread.df_to_sheet(updated_df, index=False, replace=True)
                    st.cache_data.clear()
                    st.success(f"সফলভাবে নিবন্ধিত: {final_id}")
                    st.rerun()
            else:
                st.warning("সবগুলো ঘর পূরণ করুন।")

# কিউআর কোড জেনারেটর (Fix)
with st.sidebar.expander("📥 কিউআর কোড তৈরি"):
    qr_input = st.text_input("আইডি লিখুন (QR এর জন্য)")
    if st.button("QR তৈরি করুন"):
        if qr_input:
            # সঠিক লিঙ্ক তৈরি
            qr_link = f"{APP_URL}?rider={qr_input.upper().replace(' ', '%20')}"
            
            # QR ইমেজ জেনারেট
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_link)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # মেমোরিতে ছবি সেভ (ডাউনলোডের জন্য)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            byte_im = buf.getvalue()
            
            st.image(byte_im, caption=f"QR for: {qr_input.upper()}")
            st.download_button(
                label="ডাউনলোড QR",
                data=byte_im,
                file_name=f"QR_{qr_input.upper()}.png",
                mime="image/png"
            )
        else:
            st.warning("আগে একটি আইডি লিখুন।")

# ড্যাশবোর্ড রিপোর্ট
st.sidebar.markdown("---")
st.sidebar.subheader("📊 আজকের লাইভ রিপোর্ট")
try:
    df_rep = df.copy()
    df_rep['Last_Refill'] = pd.to_datetime(df_rep['Last_Refill'], errors='coerce')
    today_df = df_rep[df_rep['Last_Refill'].dt.date == datetime.now().date()]
    st.sidebar.metric("আজকের মোট রিফিল", len(today_df))
    st.sidebar.metric("মোট লিটার বিতরণ", f"{today_df['Liters'].astype(float).sum()} L")
except:
    pass

if st.sidebar.button("🔄 ডাটা রিফ্রেশ করুন"):
    st.cache_data.clear()
    st.rerun()
**বিঃদ্রঃ** ভুল পিন বা ছবি ছাড়া ডাটা সেভ হবে না
"""

@st.dialog("ব্যবহার নির্দেশিকা")
def show_guide():
    st.markdown(GUIDE_TEXT)

    if st.button("বুঝেছি"):
        st.session_state.show_guide = False
        st.rerun()

if "show_guide" not in st.session_state:
    st.session_state.show_guide = True

if st.session_state.show_guide:
    show_guide()

# ---------------- DATABASE ----------------
@st.cache_data(ttl=10)
def load_sheet(spread, sheet_name):
    try:
        return spread.sheet_to_df(sheet=sheet_name, index=0)
    except:
        return pd.DataFrame()

if "gcp_service_account" not in st.secrets:
    st.error("Google credentials missing in Streamlit secrets")
    st.stop()

spread = Spread(
    "FuelTracker",
    config=dict(st.secrets["gcp_service_account"])
)

df_riders = load_sheet(spread, "Riders")
df_stations = load_sheet(spread, "Stations")

# ensure columns exist
if "Last_Refill" not in df_riders.columns:
    df_riders["Last_Refill"] = ""

# ---------------- SESSION ----------------
if "pump_logged_in" not in st.session_state:
    st.session_state.pump_logged_in = False
    st.session_state.station_info = None

def clean_id(text):
    return str(text).lower().replace(" ", "").replace("-", "").strip()

# ---------------- LOGIN PAGE ----------------
if not st.session_state.pump_logged_in:

    st.title("⛽ FuelGuard Pump Login")

    tab_login, tab_register = st.tabs(["🔐 Login", "📝 Register Station"])

    # ---------- LOGIN ----------
    with tab_login:

        station_id_input = st.text_input("Station ID")
        station_pin_input = st.text_input("PIN", type="password")

        if st.button("Login"):

            if not df_stations.empty:

                match = df_stations[
                    (df_stations["StationID"] == station_id_input.upper()) &
                    (df_stations["PIN"] == str(station_pin_input))
                ]

                if not match.empty:

                    st.session_state.pump_logged_in = True
                    st.session_state.station_info = match.iloc[0].to_dict()

                    st.rerun()

                else:

                    st.error("Wrong ID or PIN")

            else:

                st.error("Stations sheet empty")

        if st.button("Visitor Mode"):

            st.session_state.pump_logged_in = True
            st.session_state.station_info = None

            st.rerun()

    # ---------- REGISTER ----------
    with tab_register:

        with st.form("register_station"):

            pump_name = st.text_input("Pump Name")

            district = st.selectbox("District", BD_DISTRICTS)

            submitted = st.form_submit_button("Register")

            if submitted and pump_name:

                new_id = f"PUMP-{len(df_stations)+101}"

                new_pin = str(random.randint(1000,9999))

                new_station = pd.DataFrame([{
                    "StationID": new_id,
                    "StationName": pump_name,
                    "Location": district,
                    "PIN": new_pin
                }])

                spread.df_to_sheet(
                    pd.concat([df_stations,new_station]),
                    sheet="Stations",
                    index=False,
                    replace=True
                )

                st.success(f"ID: {new_id} | PIN: {new_pin}")

                st.cache_data.clear()

    st.stop()

# ---------------- SIDEBAR ----------------
station = st.session_state.station_info

st.sidebar.title(
    station["StationName"] if station else "Visitor Mode"
)

if st.sidebar.button("Logout"):

    st.session_state.pump_logged_in = False
    st.session_state.station_info = None

    st.rerun()

# ---------------- SEARCH RIDER ----------------
st.title("⛽ FuelGuard Pro")

search_id = st.text_input(
    "🔍 Rider ID",
    value=st.query_params.get("rider","")
)

if search_id:

    mask = df_riders["RiderID"].apply(clean_id) == clean_id(search_id)

    rider_row = df_riders[mask]

    if rider_row.empty:

        st.warning("❌ Rider not registered")

    else:

        rider = rider_row.iloc[0]

        st.subheader(f"👤 {rider['Name']}")

        eligible = True

        if rider["Last_Refill"] != "":

            try:

                last_time = datetime.strptime(
                    rider["Last_Refill"],
                    "%Y-%m-%d %H:%M:%S"
                )

                unlock_time = last_time + timedelta(hours=LOCKOUT_HOURS)

                if datetime.now() < unlock_time:

                    eligible = False

                    st.error(
                        f"🚫 Locked until {unlock_time.strftime('%d %b %I:%M %p')}"
                    )

            except:
                pass

        if eligible:

            st.success("✅ Eligible for fuel")

            if station:

                fuel_type = st.selectbox(
                    "Fuel Type",
                    ["Octane","Petrol","Diesel"]
                )

                liters = st.number_input(
                    "Liters",
                    1.0,
                    100.0,
                    5.0
                )

                photo = st.camera_input(
                    "Take vehicle photo"
                )

                if st.button("Confirm Fuel"):

                    if photo is not None:

                        now_str = datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )

                        df_riders.loc[mask,"Last_Refill"] = now_str

                        spread.df_to_sheet(
                            df_riders,
                            sheet="Riders",
                            index=False,
                            replace=True
                        )

                        transaction = pd.DataFrame([{

                            "Timestamp": now_str,

                            "StationID": station["StationID"],

                            "StationName": station["StationName"],

                            "RiderID": rider["RiderID"],

                            "FuelType": fuel_type,

                            "Liters": liters

                        }])

                        spread.df_to_sheet(
                            transaction,
                            sheet="Transactions",
                            index=False,
                            append=True
                        )

                        st.success("Saved successfully")

                        st.cache_data.clear()

                        st.rerun()

                    else:

                        st.error("Photo required")

# ---------------- ADD RIDER ----------------
if station:

    with st.sidebar.expander("➕ Register Rider"):

        with st.form("add_rider"):

            district = st.selectbox("District", BD_DISTRICTS)

            series = st.selectbox("Series", ["KA","KHA","GA","GHA","HA","LA"])

            number = st.text_input("Vehicle Number")

            name = st.text_input("Rider Name")

            submitted = st.form_submit_button("Save")

            if submitted and number and name:

                rider_id = f"{district}-{series}-{number}".upper()

                new_rider = pd.DataFrame([{

                    "RiderID": rider_id,

                    "Name": name,

                    "Last_Refill": ""

                }])

                spread.df_to_sheet(
                    pd.concat([df_riders,new_rider]),
                    sheet="Riders",
                    index=False,
                    replace=True
                )

                st.success("Rider added")

                st.cache_data.clear()

                st.rerun()

# ---------------- QR CODE ----------------
with st.sidebar.expander("📥 QR Code"):

    qr_id = st.text_input("Rider ID for QR")

    if st.button("Generate QR"):

        qr_link = f"{APP_URL}?rider={qr_id.upper()}"

        img = qrcode.make(qr_link)

        buf = io.BytesIO()

        img.save(buf, format="PNG")

        st.image(buf.getvalue())
ভুল পিন বা ছবি ছাড়া ডাটা সেভ হবে না
"""

@st.dialog("ব্যবহার নির্দেশিকা")
def show_guide():
    st.markdown(GUIDE_TEXT)

    if st.button("বুঝেছি"):
        st.session_state.show_guide = False
        st.rerun()

if "show_guide" not in st.session_state:
    st.session_state.show_guide = True

if st.session_state.show_guide:
    show_guide()

# ---------------- DATABASE ----------------
@st.cache_data(ttl=10)
def load_sheet(spread, sheet_name):

    try:
        return spread.sheet_to_df(sheet=sheet_name, index=0)

    except:
        return pd.DataFrame()

if "gcp_service_account" not in st.secrets:

    st.error("Google credentials missing")
    st.stop()

spread = Spread(
    "FuelTracker",
    config=dict(st.secrets["gcp_service_account"])
)

df_riders = load_sheet(spread, "Riders")
df_stations = load_sheet(spread, "Stations")

# create empty columns if sheet blank
if "Last_Refill" not in df_riders.columns:
    df_riders["Last_Refill"] = ""

# ---------------- SESSION ----------------
if "pump_logged_in" not in st.session_state:

    st.session_state.pump_logged_in = False
    st.session_state.station_info = None

def clean_id(text):

    return str(text).lower().replace(" ", "").replace("-", "")

# ---------------- LOGIN ----------------
if not st.session_state.pump_logged_in:

    st.title("⛽ FuelGuard Pump Login")

    tab1, tab2 = st.tabs(["🔐 Login", "📝 Register Station"])

    # -------- login --------
    with tab1:

        sid = st.text_input("Station ID")
        pin = st.text_input("PIN", type="password")

        if st.button("Login"):

            match = df_stations[
                (df_stations["StationID"] == sid.upper()) &
                (df_stations["PIN"] == str(pin))
            ]

            if not match.empty:

                st.session_state.pump_logged_in = True

                st.session_state.station_info = match.iloc[0].to_dict()

                st.rerun()

            else:

                st.error("Wrong ID or PIN")

        if st.button("Visitor Mode"):

            st.session_state.pump_logged_in = True

            st.session_state.station_info = None

            st.rerun()

    # -------- register --------
    with tab2:

        with st.form("reg_station"):

            name = st.text_input("Pump name")

            loc = st.selectbox("District", BD_DISTRICTS)

            submitted = st.form_submit_button("Register")

            if submitted:

                new_id = f"PUMP-{len(df_stations)+101}"

                new_pin = str(random.randint(1000,9999))

                new_row = pd.DataFrame([{

                    "StationID": new_id,

                    "StationName": name,

                    "Location": loc,

                    "PIN": new_pin

                }])

                spread.df_to_sheet(

                    pd.concat([df_stations,new_row]),

                    sheet="Stations",

                    index=False,

                    replace=True

                )

                st.success(f"ID: {new_id} | PIN: {new_pin}")

                st.cache_data.clear()

    st.stop()

# ---------------- SIDEBAR ----------------
station = st.session_state.station_info

st.sidebar.title(

    station["StationName"] if station else "Visitor Mode"

)

if st.sidebar.button("Logout"):

    st.session_state.pump_logged_in = False

    st.session_state.station_info = None

    st.rerun()

# ---------------- SEARCH RIDER ----------------
st.title("⛽ FuelGuard Pro")

search_id = st.text_input(

    "রাইডার আইডি লিখুন",

    value=st.query_params.get("rider","")

)

if search_id:

    mask = df_riders["RiderID"].apply(clean_id) == clean_id(search_id)

    rider_row = df_riders[mask]

    if rider_row.empty:

        st.warning("আইডি পাওয়া যায়নি")

    else:

        rider = rider_row.iloc[0]

        st.subheader(f"👤 {rider['Name']}")

        eligible = True

        unlock_time = None

        if rider["Last_Refill"] != "":

            try:

                last_dt = datetime.strptime(

                    rider["Last_Refill"],

                    "%Y-%m-%d %H:%M:%S"

                )

                unlock_time = last_dt + timedelta(hours=LOCKOUT_HOURS)

                if datetime.now() < unlock_time:

                    eligible = False

            except:

                pass

        # -------- lock check --------
        if not eligible:

            st.error(

                f"🚫 Locked until {unlock_time.strftime('%d %b %I:%M %p')}"

            )

        else:

            st.success("✅ Eligible for fuel")

            # -------- fuel form --------
            if station:

                fuel_type = st.selectbox(

                    "Fuel Type",

                    ["Octane","Petrol","Diesel"]

                )

                liters = st.number_input(

                    "Liters",

                    1.0,

                    100.0,

                    5.0

                )

                photo = st.camera_input(

                    "Vehicle photo"

                )

                if st.button("Confirm Fuel"):

                    if photo:

                        now = datetime.now().strftime(

                            "%Y-%m-%d %H:%M:%S"

                        )

                        df_riders.loc[mask,"Last_Refill"] = now

                        spread.df_to_sheet(

                            df_riders,

                            sheet="Riders",

                            index=False,

                            replace=True

                        )

                        log = pd.DataFrame([{

                            "Timestamp": now,

                            "StationID": station["StationID"],

                            "StationName": station["StationName"],

                            "RiderID": rider["RiderID"],

                            "FuelType": fuel_type,

                            "Liters": liters

                        }])

                        spread.df_to_sheet(

                            log,

                            sheet="Transactions",

                            index=False,

                            append=True

                        )

                        st.success("Saved")

                        st.cache_data.clear()

                        st.rerun()

                    else:

                        st.error("Photo required")

# ---------------- ADD RIDER ----------------
if station:

    with st.sidebar.expander("➕ Register Rider"):

        with st.form("add_rider"):

            d = st.selectbox("District", BD_DISTRICTS)

            s = st.selectbox("Series", ["KA","KHA","GA","GHA","HA","LA"])

            num = st.text_input("Number")

            name = st.text_input("Name")

            ok = st.form_submit_button("Save")

            if ok:

                rider_id = f"{d}-{s}-{num}".upper()

                new_row = pd.DataFrame([{

                    "RiderID": rider_id,

                    "Name": name,

                    "Last_Refill": ""

                }])

                spread.df_to_sheet(

                    pd.concat([df_riders,new_row]),

                    sheet="Riders",

                    index=False,

                    replace=True

                )

                st.success("Saved")

                st.cache_data.clear()

                st.rerun()

# ---------------- QR ----------------
with st.sidebar.expander("📥 QR Code"):

    rid = st.text_input("Rider ID for QR")

    if st.button("Generate QR"):

        link = f"{APP_URL}?rider={rid.upper()}"

        img = qrcode.make(link)

        buf = io.BytesIO()

        img.save(buf, format="PNG")

        st.image(buf.getvalue())
**বিঃদ্রঃ** ভুল পিন বা ছবি ছাড়া ডাটা সেভ হবে না
"""

@st.dialog("ব্যবহার নির্দেশিকা")
def show_guide():
    st.markdown(GUIDE_TEXT)
    if st.button("বুঝেছি"):
        st.session_state.show_guide = False
        st.rerun()

if "show_guide" not in st.session_state:
    st.session_state.show_guide = True

if st.session_state.show_guide:
    show_guide()

# --- 3. DATABASE ---
@st.cache_data(ttl=5)
def fetch_data(spread, sheet):
    try:
        return spread.sheet_to_df(sheet=sheet, index=0)
    except:
        return pd.DataFrame()

if "gcp_service_account" not in st.secrets:
    st.error("Missing Google credentials")
    st.stop()

spread = Spread("FuelTracker", config=dict(st.secrets["gcp_service_account"]))

df_riders = fetch_data(spread, "Riders")
df_stations = fetch_data(spread, "Stations")

# --- 4. SESSION ---
if "pump_logged_in" not in st.session_state:
    st.session_state.pump_logged_in = False
    st.session_state.station_info = None

def clean_id(x):
    return str(x).lower().replace(" ", "").replace("-", "")

# --- 5. LOGIN ---
if not st.session_state.pump_logged_in:

    st.title("⛽ Pump Login")

    tab1, tab2 = st.tabs(["Login", "Register Station"])

    with tab1:

        sid = st.text_input("Station ID")
        pin = st.text_input("PIN", type="password")

        if st.button("Login"):

            match = df_stations[
                (df_stations["StationID"] == sid.upper()) &
                (df_stations["PIN"] == str(pin))
            ]

            if not match.empty:

                st.session_state.pump_logged_in = True
                st.session_state.station_info = match.iloc[0].to_dict()
                st.rerun()

            else:
                st.error("Invalid ID or PIN")

    with tab2:

        with st.form("reg_station"):

            name = st.text_input("Station Name")
            loc = st.selectbox("District", BD_DISTRICTS)

            if st.form_submit_button("Register"):

                new_id = f"PUMP-{len(df_stations)+101}"
                new_pin = str(random.randint(1000,9999))

                new_row = pd.DataFrame([{
                    "StationID": new_id,
                    "StationName": name,
                    "Location": loc,
                    "PIN": new_pin
                }])

                spread.df_to_sheet(
                    pd.concat([df_stations, new_row]),
                    sheet="Stations",
                    index=False,
                    replace=True
                )

                st.success(f"ID: {new_id} PIN: {new_pin}")

    st.stop()

# --- 6. MAIN ---
st.title("⛽ FuelGuard Pro")

station = st.session_state.station_info

st.sidebar.title(station["StationName"])

if st.sidebar.button("Logout"):
    st.session_state.pump_logged_in = False
    st.rerun()

search_id = st.text_input(
    "Rider ID",
    value=st.query_params.get("rider","")
)

if search_id:

    mask = df_riders["RiderID"].apply(clean_id) == clean_id(search_id)

    if mask.sum()==0:
        st.warning("Not registered")

    else:

        rider = df_riders[mask].iloc[0]

        st.subheader(rider["Name"])

        eligible = True

        if rider["Last_Refill"]!="":

            last = datetime.strptime(
                rider["Last_Refill"],
                "%Y-%m-%d %H:%M:%S"
            )

            unlock = last + timedelta(hours=LOCKOUT_HOURS)

            if datetime.now() < unlock:

                eligible=False
                st.error(f"Locked until {unlock}")

        if eligible:

            st.success("Eligible")

            fuel = st.selectbox(
                "Fuel",
                ["Octane","Petrol","Diesel"]
            )

            liters = st.number_input(
                "Liters",
                1.0,
                100.0,
                5.0
            )

            photo = st.camera_input("Photo")

            if st.button("Confirm"):

                if photo:

                    now = datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

                    df_riders.loc[mask,"Last_Refill"]=now

                    spread.df_to_sheet(
                        df_riders,
                        sheet="Riders",
                        index=False,
                        replace=True
                    )

                    log = pd.DataFrame([{
                        "Timestamp":now,
                        "StationID":station["StationID"],
                        "RiderID":rider["RiderID"],
                        "Fuel":fuel,
                        "Liters":liters
                    }])

                    spread.df_to_sheet(
                        log,
                        sheet="Transactions",
                        index=False,
                        append=True
                    )

                    st.success("Saved")

# --- 7. QR ---
with st.sidebar:

    st.subheader("QR")

    rid = st.text_input("Rider ID")

    if st.button("Generate QR"):

        url = f"{APP_URL}?rider={rid}"

        img = qrcode.make(url)

        buf = io.BytesIO()

        img.save(buf)

        st.image(buf.getvalue())**বিঃদ্রঃ** ভুল পিন দিলে বা ছবি না তুললে ডাটা সেভ হবে না.
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
            st.image(buf.getvalue())    4. "**নিয়ম:** একবার তেল নিলে পরবর্তী **৭২ ঘণ্টা** ওই আইডি লক থাকবে।"

   " **বিঃদ্রঃ** ভুল পিন দিলে বা ছবি না তুললে ডাটা সেভ হবে না।"
    """)
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
    st.stop()

# --- 6. MAIN INTERFACE ---
s_name = st.session_state.station_info['StationName'] if st.session_state.station_info else 'Visitor Mode'
st.sidebar.title(f"🏪 {s_name}")
if st.sidebar.button("Log Out"):
    st.session_state.pump_logged_in = False
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
            st.image(buf.getvalue())    4. **নিয়ম:** একবার তেল নিলে পরবর্তী **72 ঘণ্টা** ওই আইডি লক থাকবে.

    **বিঃদ্রঃ** ভুল পিন দিলে বা ছবি না তুললে ডাটা সেভ হবে না।
    """)
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
    st.stop()

# --- 6. MAIN INTERFACE ---
s_name = st.session_state.station_info['StationName'] if st.session_state.station_info else 'Visitor Mode'
st.sidebar.title(f"🏪 {s_name}")
if st.sidebar.button("Log Out"):
    st.session_state.pump_logged_in = False
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
            st.image(buf.getvalue())    4. **নিয়ম:** একবার তেল নিলে পরবর্তী **৭২ ঘণ্টা** ওই আইডি লক থাকবে.

    **বিঃদ্রঃ** ভুল পিন দিলে বা ছবি না তুললে ডাটা সেভ হবে না.
    """)
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

# --- 5. LOGIN & REGISTRATION GATEWAY ---
if not st.session_state.pump_logged_in:
    st.title("⛽ FuelGuard: Pump Station Access")
    t_login, t_reg = st.tabs(["🔐 Login", "📝 New Station Registration"])

    with t_login:
        s_id_input = st.text_input("Station ID (e.g. PUMP-101)")
        s_pin_input = st.text_input("PIN", type="password")
        if st.button("Login"):
            if not df_stations.empty:
                match = df_stations[(df_stations['StationID'] == s_id_input.upper()) & (df_stations['PIN'] == str(s_pin_input))]
                if not match.empty:
                    st.session_state.pump_logged_in = True
                    st.session_state.station_info = match.iloc[0].to_dict()
                    st.rerun()
                else:
                    st.error("Invalid ID or PIN!")
            else:
                st.error("Station database is empty. Please register first.")
        
        st.divider()
        if st.button("🔍 Check Rider Status Only (Visitor Mode)"):
            st.session_state.pump_logged_in = "VISITOR"
            st.rerun()

    with t_reg:
        with st.form("station_reg_form"):
            n_name = st.text_input("Pump Name")
            n_loc = st.selectbox("Location (District)", BD_DISTRICTS)
            if st.form_submit_button("Complete Registration"):
                if n_name:
                    new_id = f"PUMP-{len(df_stations) + 101}"
                    new_pin = str(random.randint(1000, 9999))
                    new_station = pd.DataFrame([{"StationID": new_id, "StationName": n_name, "Location": n_loc, "PIN": new_pin}])
                    spread.df_to_sheet(pd.concat([df_stations, new_station]), sheet='Stations', index=False, replace=True)
                    st.success(f"Success! ID: {new_id}, PIN: {new_pin}")
                    st.cache_data.clear()
                else:
                    st.error("Please enter pump name.")
    st.stop()

# --- 6. MAIN APP INTERFACE ---
station_name = st.session_state.station_info['StationName'] if st.session_state.station_info else 'Visitor Mode'
st.sidebar.title(f"🏪 {station_name}")
if st.sidebar.button("Log Out"):
    st.session_state.pump_logged_in = False
    st.session_state.station_info = None
    st.rerun()

st.title("⛽ FuelGuard Pro: Smart Monitoring")

scanned_id = st.text_input("🔍 Enter or Scan Rider ID", value=st.query_params.get("rider", ""))

if scanned_id:
    s_id = clean_id(scanned_id)
    if not df_riders.empty:
        mask = df_riders['RiderID'].apply(clean_id) == s_id
        rider_row = df_riders[mask]

        if rider_row.empty:
            st.warning("❌ ID not registered.")
        else:
            r_data = rider_row.iloc[0]
            st.header(f"👤 Rider: {r_data['Name']} ({r_data['RiderID']})")
            
            eligible = True
            unlock_time = None
            last_refill = str(r_data['Last_Refill']).strip()
            
            if last_refill != "":
                try:
                    last_dt = datetime.strptime(last_refill, "%Y-%m-%d %H:%M:%S")
                    unlock_time = last_dt + timedelta(hours=LOCKOUT_HOURS)
                    if datetime.now() < unlock_time:
                        eligible = False
                except: pass

            if not eligible:
                st.error(f"🚫 Locked! Next refill available at: {unlock_time.strftime('%b %d, %I:%M %p')}")
            else:
                st.success("✅ This rider is currently eligible for fuel.")
                
                if st.session_state.station_info:
                    with st.expander("🛠 Fuel Refill Form", expanded=True):
                        f_type = st.selectbox("Fuel Type", ["Octane", "Petrol", "Diesel"])
                        liters = st.number_input("Amount (Liters)", 1.0, 100.0, 5.0)
                        photo = st.camera_input("Take Photo for Security")
                        
                        if st.button("💾 Confirm and Save"):
                            if photo:
                                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                # Update Rider Sheet
                                df_riders.loc[mask, 'Last_Refill'] = now_str
                                spread.df_to_sheet(df_riders, sheet='Riders', index=False, replace=True)
                                
                                # Log Transaction
                                trans_data = pd.DataFrame([{
                                    "Timestamp": now_str,
                                    "StationID": st.session_state.station_info['StationID'],
                                    "StationName": st.session_state.station_info['StationName'],
                                    "RiderID": r_data['RiderID'],
                                    "FuelType": f_type,
                                    "Liters": liters
                                }])
                                spread.df_to_sheet(trans_data, sheet='Transactions', index=False, append=True)
                                st.success("Transaction Saved!")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error("⚠️ Photo is mandatory for security.")
                else:
                    st.warning("⚠️ Please login with Pump ID to confirm refill.")
    else:
        st.error("Rider database is empty.")

# --- 7. SIDEBAR UTILITIES ---
if st.session_state.station_info:
    with st.sidebar.expander("📝 Rider Registration"):
        with st.form("new_rider_reg"):
            dist = st.selectbox("District", BD_DISTRICTS)
            series = st.selectbox("Series", ["KA", "KHA", "GA", "GHA", "HA", "LA"])
            num = st.text_input("Vehicle Number")
            name = st.text_input("Rider Name")
            if st.form_submit_button("Register Rider"):
                f_id = f"{dist}-{series}-{num}".upper()
                new_entry = pd.DataFrame([{"RiderID": f_id, "Name": name, "Last_Refill": "", "Liters": 0}])
                spread.df_to_sheet(pd.concat([df_riders, new_entry]), sheet='Riders', index=False, replace=True)
                st.success("Registered!")
                st.cache_data.clear()
                st.rerun()

    with st.sidebar.expander("📥 Generate QR Code"):
        qr_input = st.text_input("Enter ID for QR")
        if st.button("Generate QR"):
            q_link = f"{APP_URL}?rider={qr_input.upper()}"
            img = qrcode.make(q_link)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            st.image(buf.getvalue())    4. **নিয়ম:** একবার তেল নিলে পরবর্তী **৭২ ঘণ্টা** ওই আইডি লক থাকবে.
    """)
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
        st.error(f"ডাটাবেজ কানেকশন ফেইলড: {e}")
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

# --- 5. LOGIN & REGISTRATION GATEWAY ---
if not st.session_state.pump_logged_in:
    st.title("⛽ FuelGuard: পাম্প স্টেশন এক্সেস")
    t_login, t_reg = st.tabs(["🔐 লগইন", "📝 নতুন স্টেশন নিবন্ধন"])

    with t_login:
        s_id_input = st.text_input("স্টেশন আইডি (যেমন: PUMP-101)")
        s_pin_input = st.text_input("পিন (PIN)", type="password")
        if st.button("প্রবেশ করুন"):
            if not df_stations.empty:
                match = df_stations[(df_stations['StationID'] == s_id_input.upper()) & (df_stations['PIN'] == s_pin_input)]
                if not match.empty:
                    st.session_state.pump_logged_in = True
                    st.session_state.station_info = match.iloc[0].to_dict()
                    st.rerun()
                else:
                    st.error("ভুল আইডি অথবা পিন!")
            else:
                st.error("স্টেশন ডাটাবেজ খালি. আগে নিবন্ধন করুন.")
        
        st.divider()
        if st.button("🔍 শুধুমাত্র রাইডার স্ট্যাটাস দেখুন (Visitor Mode)"):
            st.session_state.pump_logged_in = "VISITOR"
            st.rerun()

    with t_reg:
        with st.form("station_reg_form"):
            n_name = st.text_input("পাম্পের নাম")
            n_loc = st.selectbox("অবস্থান (জেলা)", BD_DISTRICTS)
            if st.form_submit_button("নিবন্ধন সম্পন্ন করুন"):
                if n_name:
                    new_id = f"PUMP-{len(df_stations) + 101}"
                    new_pin = str(random.randint(1000, 9999))
                    new_station = pd.DataFrame([{"StationID": new_id, "StationName": n_name, "Location": n_loc, "PIN": new_pin}])
                    spread.df_to_sheet(pd.concat([df_stations, new_station]), sheet='Stations', index=False, replace=True)
                    st.success(f"সফল! আইডি: {new_id}, পিন: {new_pin}")
                    st.cache_data.clear()
                else:
                    st.error("পাম্পের নাম লিখুন.")
    st.stop()

# --- 6. MAIN APP INTERFACE ---
st.sidebar.title(f"🏪 {st.session_state.station_info['StationName'] if st.session_state.station_info else 'Visitor Mode'}")
if st.sidebar.button("Log Out"):
    st.session_state.pump_logged_in = False
    st.session_state.station_info = None
    st.rerun()

st.title("⛽ FuelGuard Pro")

scanned_id = st.text_input("🔍 রাইডার আইডি লিখুন বা স্ক্যান করুন", value=st.query_params.get("rider", ""))

if scanned_id:
    s_id = clean_id(scanned_id)
    if not df_riders.empty:
        mask = df_riders['RiderID'].apply(clean_id) == s_id
        rider_row = df_riders[mask]

        if rider_row.empty:
            st.warning("❌ আইডি নিবন্ধিত নয়.")
        else:
            r_data = rider_row.iloc[0]
            st.header(f"👤 রাইডার: {r_data['Name']} ({r_data['RiderID']})")
            
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
                st.success("✅ এই রাইডার বর্তমানে তেল পাওয়ার যোগ্য.")
                
                if st.session_state.station_info:
                    with st.expander("🛠 তেল প্রদান ফরম", expanded=True):
                        f_type = st.selectbox("তেলের ধরন", ["Octane", "Petrol", "Diesel"])
                        liters = st.number_input("লিটার", 1.0, 100.0, 5.0)
                        photo = st.camera_input("গাড়ির ছবি তুলুন")
                        
                        if st.button("💾 কনফার্ম এবং সেভ"):
                            if photo:
                                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                # রাইডার আপডেট
                                df_riders.loc[mask, 'Last_Refill'] = now_str
                                spread.df_to_sheet(df_riders, sheet='Riders', index=False, replace=True)
                                
                                # ট্রানজেকশন আপডেট
                                trans_data = pd.DataFrame([{
                                    "Timestamp": now_str,
                                    "StationID": st.session_state.station_info['StationID'],
                                    "StationName": st.session_state.station_info['StationName'],
                                    "RiderID": r_data['RiderID'],
                                    "FuelType": f_type,
                                    "Liters": liters
                                }])
                                spread.df_to_sheet(trans_data, sheet='Transactions', index=False, append=True)
                                st.success("সেভ হয়েছে!")
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error("ছবি তোলা বাধ্যতামূলক.")
                else:
                    st.warning("⚠️ তেল প্রদান নিশ্চিত করতে পাম্প আইডি দিয়ে লগইন করুন.")
    else:
        st.error("রাইডার ডাটাবেজ খালি.")

# --- 7. SIDEBAR UTILITIES ---
if st.session_state.station_info:
    with st.sidebar.expander("📝 রাইডার রেজিস্ট্রেশন"):
        with st.form("new_rider_reg"):
            dist = st.selectbox("জেলা", BD_DISTRICTS)
            series = st.selectbox("সিরিজ", ["KA", "KHA", "GA", "GHA", "HA", "LA"])
            num = st.text_input("গাড়ির নম্বর")
            name = st.text_input("নাম")
            if st.form_submit_button("রেজিস্ট্রেশন সম্পন্ন"):
                f_id = f"{dist}-{series}-{num}".upper()
                new_entry = pd.DataFrame([{"RiderID": f_id, "Name": name, "Last_Refill": "", "Liters": 0}])
                spread.df_to_sheet(pd.concat([df_riders, new_entry]), sheet='Riders', index=False, replace=True)
                st.success("নিবন্ধিত!")
                st.cache_data.clear()
                st.rerun()

    with st.sidebar.expander("📥 কিউআর কোড"):
        qr_input = st.text_input("আইডি দিন")
        if st.button("QR তৈরি করুন"):
            q_link = f"{APP_URL}?rider={qr_input.upper()}"
            img = qrcode.make(q_link)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            st.image(buf.getvalue())    st.markdown("""
    ### ⛽ অ্যাপটি কীভাবে কাজ করে?
    1. **রাইডার:** আইডি সার্চ করে নিজের এলিজিবিলিটি চেক করতে পারবেন।
    2. **পাম্প:** তেল দিতে হলে অবশ্যই স্টেশন আইডি ও পিন দিয়ে লগইন করতে হবে।
    3. **নিরাপত্তা:** তেল দেওয়ার সময় গাড়ির ছবি তোলা এবং তেলের ধরন সিলেক্ট করা বাধ্যতামূলক।
    4. **নিয়ম:** একবার তেল নিলে পরবর্তী **৭২ ঘণ্টা** ওই আইডি লক থাকবে।
    """)
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
        st.error(f"ডাটাবেজ কানেকশন ফেইলড: {e}")
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

# --- 5. LOGIN & REGISTRATION GATEWAY ---
if not st.session_state.pump_logged_in:
    st.title("⛽ FuelGuard: পাম্প স্টেশন এক্সেস")
    t_login, t_reg = st.tabs(["🔐 লগইন", "📝 নতুন স্টেশন নিবন্ধন"])

    with t_login:
        s_id_input = st.text_input("স্টেশন আইডি (যেমন: PUMP-101)")
        s_pin_input = st.text_input("পিন (PIN)", type="password")
        if st.button("প্রবেশ করুন"):
            match = df_stations[(df_stations['StationID'] == s_id_input.upper()) & (df_stations['PIN'] == s_pin_input)]
            if not match.empty:
                st.session_state.pump_logged_in = True
                st.session_state.station_info = match.iloc[0].to_dict()
                st.rerun()
            else:
                st.error("ভুল আইডি অথবা পিন!")
        
        st.divider()
        if st.button("🔍 শুধুমাত্র রাইডার স্ট্যাটাস দেখুন (Visitor Mode)"):
            st.session_state.pump_logged_in = "VISITOR"
            st.rerun()

    with t_reg:
        with st.form("station_reg_form"):
            n_name = st.text_input("পাম্পের নাম")
            n_loc = st.selectbox("অবস্থান (জেলা)", BD_DISTRICTS)
            if st.form_submit_button("নিবন্ধন সম্পন্ন করুন"):
                if n_name:
                    new_id = f"PUMP-{len(df_stations) + 101}"
                    new_pin = str(random.randint(1000, 9999))
                    new_station = pd.DataFrame([{"StationID": new_id, "StationName": n_name, "Location": n_loc, "PIN": new_pin}])
                    spread.df_to_sheet(pd.concat([df_stations, new_station]), sheet='Stations', index=False, replace=True)
                    st.success(f"সফল! আইডি: {new_id}, পিন: {new_pin}")
                else:
                    st.error("পাম্পের নাম লিখুন।")
    st.stop()

# --- 6. MAIN APP INTERFACE ---
st.sidebar.title(f"🏪 {st.session_state.station_info['StationName'] if st.session_state.station_info else 'Visitor Mode'}")
if st.sidebar.button("Log Out"):
    st.session_state.pump_logged_in = False
    st.session_state.station_info = None
    st.rerun()

st.title("⛽ FuelGuard Pro")

scanned_id = st.text_input("🔍 রাইডার আইডি লিখুন বা স্ক্যান করুন", value=st.query_params.get("rider", ""))

if scanned_id:
    s_id = clean_id(scanned_id)
    mask = df_riders['RiderID'].apply(clean_id) == s_id
    rider_row = df_riders[mask]

    if rider_row.empty:
        st.warning("❌ আইডি নিবন্ধিত নয়।")
    else:
        r_data = rider_row.iloc[0]
        st.header(f"👤 রাইডার: {r_data['Name']} ({r_data['RiderID']})")
        
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
                            
                            trans_data = pd.DataFrame([{
                                "Timestamp": now_str,
                                "StationID": st.session_state.station_info['StationID'],
                                "StationName": st.session_state.station_info['StationName'],
                                "RiderID": r_data['RiderID'],
                                "FuelType": f_type,
                                "Liters": liters
                            }])
                            spread.df_to_sheet(trans_data, sheet='Transactions', index=False, append=True)
                            st.success("সেভ হয়েছে!")
                            st.rerun()
                        else:
                            st.error("ছবি তোলা বাধ্যতামূলক।")

# --- 7. SIDEBAR UTILITIES ---
if st.session_state.station_info:
    with st.sidebar.expander("📝 রাইডার রেজিস্ট্রেশন"):
        with st.form("new_rider_reg"):
            dist = st.selectbox("জেলা", BD_DISTRICTS)
            series = st.selectbox("সিরিজ", ["KA", "KHA", "GA", "GHA", "HA", "LA"])
            num = st.text_input("গাড়ির নম্বর")
            name = st.text_input("নাম")
            if st.form_submit_button("রেজিস্ট্রেশন সম্পন্ন"):
                f_id = f"{dist}-{series}-{num}".upper()
                new_entry = pd.DataFrame([{"RiderID": f_id, "Name": name, "Last_Refill": "", "Liters": 0}])
                spread.df_to_sheet(pd.concat([df_riders, new_entry]), sheet='Riders', index=False, replace=True)
                st.success("নিবন্ধিত!")
                st.cache_data.clear()
                st.rerun()

    with st.sidebar.expander("📥 কিউআর কোড"):
        qr_input = st.text_input("আইডি দিন")
        if st.button("QR তৈরি করুন"):
            q_link = f"{APP_URL}?rider={qr_input.upper()}"
            img = qrcode.make(q_link)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            st.image(buf.getvalue())
    **বি:দ্র:** ভুল পিন দিলে বা ছবি না তুললে ডাটা সেভ হবে না।
    """)
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
        st.error(f"ডাটাবেজ কানেকশন ফেইলড: {e}")
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

# --- 5. LOGIN & REGISTRATION GATEWAY ---
if not st.session_state.pump_logged_in:
    st.title("⛽ FuelGuard: পাম্প স্টেশন এক্সেস")
    t_login, t_reg = st.tabs(["🔐 লগইন", "📝 নতুন স্টেশন নিবন্ধন"])

    with t_login:
        s_id_input = st.text_input("স্টেশন আইডি (যেমন: PUMP-101)")
        s_pin_input = st.text_input("পিন (PIN)", type="password")
        if st.button("প্রবেশ করুন"):
            match = df_stations[(df_stations['StationID'] == s_id_input.upper()) & (df_stations['PIN'] == s_pin_input)]
            if not match.empty:
                st.session_state.pump_logged_in = True
                st.session_state.station_info = match.iloc[0].to_dict()
                st.rerun()
            else:
                st.error("ভুল আইডি অথবা পিন!")
        
        st.divider()
        if st.button("🔍 শুধুমাত্র রাইডার স্ট্যাটাস দেখুন (Visitor Mode)"):
            st.session_state.pump_logged_in = "VISITOR"
            st.rerun()

    with t_reg:
        with st.form("station_reg_form"):
            n_name = st.text_input("পাম্পের নাম")
            n_loc = st.selectbox("অবস্থান (জেলা)", BD_DISTRICTS)
            if st.form_submit_button("নিবন্ধন সম্পন্ন করুন"):
                if n_name:
                    new_id = f"PUMP-{len(df_stations) + 101}"
                    new_pin = str(random.randint(1000, 9999))
                    new_station = pd.DataFrame([{"StationID": new_id, "StationName": n_name, "Location": n_loc, "PIN": new_pin}])
                    spread.df_to_sheet(pd.concat([df_stations, new_station]), sheet='Stations', index=False, replace=True)
                    st.success(f"সফল! আইডি: {new_id}, পিন: {new_pin}")
                    st.info("এই পিনটি লিখে রাখুন, পরবর্তীতে লগইন করতে লাগবে।")
                else:
                    st.error("পাম্পের নাম লিখুন।")
    st.stop()

# --- 6. MAIN APP INTERFACE ---
st.sidebar.title(f"🏪 {st.session_state.station_info['StationName'] if st.session_state.station_info else 'Visitor Mode'}")
if st.sidebar.button("Log Out"):
    st.session_state.pump_logged_in = False
    st.session_state.station_info = None
    st.rerun()

st.title("⛽ FuelGuard Pro: স্মার্ট মনিটরিং")

# রাইডার সার্চ
scanned_id = st.text_input("🔍 রাইডার আইডি লিখুন বা স্ক্যান করুন", value=st.query_params.get("rider", ""))

if scanned_id:
    s_id = clean_id(scanned_id)
    mask = df_riders['RiderID'].apply(clean_id) == s_id
    rider_row = df_riders[mask]

    if rider_row.empty:
        st.warning("❌ এই আইডি নিবন্ধিত নয়।")
    else:
        r_data = rider_row.iloc[0]
        st.header(f"👤 রাইডার: {r_data['Name']} ({r_data['RiderID']})")
        
        eligible = True
        unlock_time = None
        if str(r_data['Last_Refill']).strip() != "":
            last_dt = datetime.strptime(str(r_data['Last_Refill']), "%Y-%m-%d %H:%M:%S")
            unlock_time = last_dt + timedelta(hours=LOCKOUT_HOURS)
            if datetime.now() < unlock_time:
                eligible = False

        if not eligible:
            st.error(f"🚫 লকড! পরবর্তীতে তেল পাবেন: {unlock_time.strftime('%b %d, %I:%M %p')}")
        else:
            st.success("✅ এই রাইডার বর্তমানে তেল পাওয়ার যোগ্য।")
            
            # পাম্প অপারেটর হলে এন্ট্রি ফর্ম দেখাবে
            if st.session_state.station_info:
                with st.expander("🛠 তেল প্রদান ফরম (অপারেটর প্যানেল)", expanded=True):
                    f_type = st.selectbox("তেলের ধরন (Fuel Type)", ["Octane", "Petrol", "Diesel"])
                    liters = st.number_input("লিটারের পরিমাণ", 1.0, 100.0, 5.0)
                    photo = st.camera_input("নিরাপত্তার জন্য গাড়ির ছবি তুলুন")
                    
                    if st.button("💾 কনফার্ম এবং সেভ"):
                        if photo:
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            # ১. রাইডার লিস্ট আপডেট
                            df_riders.loc[mask, 'Last_Refill'] = now_str
                            spread.df_to_sheet(df_riders, sheet='Riders', index=False, replace=True)
                            
                            # ২. ট্রানজেকশন লগ সেভ
                            trans_data = pd.DataFrame([{
                                "Timestamp": now_str,
                                "StationID": st.session_state.station_info['StationID'],
                                "StationName": st.session_state.station_info['StationName'],
                                "RiderID": r_data['RiderID'],
                                "FuelType": f_type,
                                "Liters": liters
                            }])
                            spread.df_to_sheet(trans_data, sheet='Transactions', index=False, append=True)
                            
                            st.success("সফলভাবে ট্রানজেকশন সেভ হয়েছে!")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error("⚠️ ছবি তোলা বাধ্যতামূলক।")
            else:
                st.warning("⚠️ তেল প্রদান নিশ্চিত করতে পাম্প আইডি দিয়ে লগইন করুন।")

# --- 7. SIDEBAR UTILITIES ---
if st.session_state.station_info:
    with st.sidebar.expander("📝 নতুন রাইডার রেজিস্ট্রেশন"):
        with st.form("new_rider_reg"):
            dist = st.selectbox("জেলা", BD_DISTRICTS)
            series = st.selectbox("সিরিজ", ["KA", "KHA", "GA", "GHA", "HA", "LA"])
            num = st.text_input("গাড়ির নম্বর (যেমন: 11-0101)")
            name = st.text_input("রাইডারের নাম")
            if st.form_submit_button("রেজিস্ট্রেশন সম্পন্ন"):
                f_id = f"{dist}-{series}-{num}".upper()
                new_entry = pd.DataFrame([{"RiderID": f_id, "Name": name, "Last_Refill": "", "Liters": 0}])
                spread.df_to_sheet(pd.concat([df_riders, new_entry]), sheet='Riders', index=False, replace=True)
                st.success("রাইডার নিবন্ধিত!")
                st.rerun()

    with st.sidebar.expander("📥 কিউআর কোড জেনারেটর"):
        qr_input = st.text_input("আইডি দিন (QR এর জন্য)")
        if st.button("QR তৈরি করুন"):
            q_link = f"{APP_URL}?rider={qr_input.upper()}"
            img = qrcode.make(q_link)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            st.image(buf.getvalue(), caption=qr_input.upper())

    # আজকের লাইভ রিপোর্ট (সংক্ষিপ্ত)
    st.sidebar.divider()
    if st.sidebar.button("🔄 ডাটা রিফ্রেশ"):
        st.cache_data.clear()
        st.rerun()if "gcp_service_account" in st.secrets:
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
