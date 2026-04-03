import streamlit as st
from gspread_pandas import Spread
import pandas as pd
from datetime import datetime, timedelta
import qrcode
import io

# --- ১. কনফিগারেশন ও সিক্রেটস ---
st.set_page_config(page_title="FuelGuard Pro", page_icon="⛽", layout="wide")

LOCKOUT_HOURS = 72
APP_URL = "https://fuel-tracker.streamlit.app" 

try:
    OPERATOR_PIN = st.secrets["PUMP_SECRET_PIN"]
except:
    OPERATOR_PIN = "1234"

BD_DISTRICTS = ["BAGERHAT", "BANDARBAN", "BARGUNA", "BARISHAL", "BHOLA", "BOGURA", "BRAHMANBARIA", "CHANDPUR", "CHATTOGRAM", "CHATTOGRAM METRO", "CHUADANGA", "COMILLA", "COXS BAZAR", "DHAKA", "DHAKA METRO", "DINAJPUR", "FARIDPUR", "FENI", "GAIBANDHA", "GAZIPUR", "GOPALGANJ", "HABIGANJ", "JAMALPUR", "JASHORE", "JHALOKATHI", "JHENAIDAH", "JOYPURHAT", "KHAGRACHHARI", "KHULNA", "KHULNA METRO", "KISHOREGANJ", "KURIGRAM", "KUSHTIA", "LAKSHMIPUR", "LALMONIRHAT", "MADARIPUR", "MAGURA", "MANIKGANJ", "MEHERPUR", "MOULVIBAZAR", "MUNSHIGANJ", "MYMENSINGH", "NAOGAON", "NARAIL", "NARAYANGANJ", "NARSINGDI", "NATORE", "NETROKONA", "NILPHAMARI", "NOAKHALI", "PABNA", "PANCHAGARH", "PATUAKHALI", "PIROJPUR", "RAJBARI", "RAJSHAHI", "RAJSHAHI METRO", "RANGAMATI", "RANGPUR", "SATKHIRA", "SHARIATPUR", "SHERPUR", "SIRAJGANJ", "SUNAMGANJ", "SYLHET", "SYLHET METRO", "TANGAIL", "THAKURGAON"]
SERIES_LIST = ["KA", "KHA", "GA", "GHA", "CHA", "THA", "HA", "LA", "MA", "BA"]

# --- ২. পপ-আপ নির্দেশিকা ---
@st.dialog("📖 ফুয়েলগার্ড ইউজার গাইড")
def show_instruction_popup():
    st.markdown("""
    ### ⛽ FuelGuard Pro এ আপনাকে স্বাগতম!
    সিস্টেমের নিরাপত্তা ও সহজলভ্যতা নিশ্চিতে কিছু পরিবর্তন আনা হয়েছে:

    ---
    #### 🆕 নতুন পরিবর্তনসমূহ (Key Changes):
    1. **উন্মুক্ত রেজিস্ট্রেশন:** এখন যেকোনো রাইডার নিজে **'নতুন রেজিস্ট্রেশন'** ট্যাব থেকে আইডি তৈরি করতে পারবেন। কোনো পিন লাগবে না।
    2. **পিন প্রটেক্টড ইনপুট:** তেল দেওয়ার রেকর্ড সেভ করতে শুধুমাত্র পাম্প অপারেটরের **গোপন পিন** প্রয়োজন।
    3. **স্মার্ট ভেরিফিকেশন:** এখন আইডি চেক করা সবার জন্য উন্মুক্ত।

    ---
    #### 🛠 ব্যবহারবিধি (Pros & Usage):
    * **রাইডার:** রেজিস্ট্রেশন ট্যাব থেকে আইডি তৈরি করুন। কিউআর কোড ডাউনলোড করে সাথে রাখুন।
    * **অপারেটর:** রাইডার এলিজিবল হলে পিন দিয়ে লগার আনলক করুন এবং গাড়ির ছবি তুলে কনফার্ম করুন।
    * **নিরাপত্তা:** প্রতিটি ট্রানজ্যাকশনে ছবি বাধ্যতামূলক নয় তবে করা যাবে, যা জালিয়াতি রোধ করবে।
    """)
    if st.button("ঠিক আছে, শুরু করি"):
        st.session_state.show_manual = False
        st.rerun()

if "show_manual" not in st.session_state:
    st.session_state.show_manual = True

if st.session_state.show_manual:
    show_instruction_popup()

# --- ৩. ডাটাবেজ কানেকশন ---
@st.cache_data(ttl=5)
def fetch_data(_spread_obj):
    try:
        data = _spread_obj.sheet_to_df(index=0)
        data.columns = data.columns.str.strip()
        return data
    except:
        return pd.DataFrame(columns=["RiderID", "Name", "Last_Refill", "Liters"])

if "gcp_service_account" in st.secrets:
    creds = dict(st.secrets["gcp_service_account"])
    try:
        spread = Spread("FuelTracker", config=creds)
        df = fetch_data(spread)
    except Exception as e:
        st.error(f"কানেকশন সমস্যা: {e}"); st.stop()
else:
    st.error("Credentials missing!"); st.stop()

def clean_id(text):
    return str(text).lower().replace(" ", "").replace("-", "").strip()

# --- ৪. মেইন ইন্টারফেস ---
st.title("⛽ FuelGuard Pro")
tab1, tab2, tab3 = st.tabs(["🔍 স্ট্যাটাস ও রিফিল", "📝 নতুন রেজিস্ট্রেশন", "📊 রিপোর্ট"])

with tab1:
    st.subheader("রাইডার ভেরিফিকেশন")
    query_params = st.query_params
    url_id = query_params.get("rider", "")
    scanned_id = st.text_input("🔍 আইডি লিখুন বা স্ক্যান করুন", value=url_id)

    if scanned_id:
        s_id = clean_id(scanned_id)
        mask = df['RiderID'].apply(clean_id) == s_id
        rider_row = df[mask]

        if rider_row.empty:
            st.warning(f"❌ আইডি পাওয়া যায়নি।")
        else:
            r_data = rider_row.iloc[0]
            st.info(f"👤 রাইডার: **{r_data['Name']}**")

            eligible = True
            last_val = r_data['Last_Refill']
            if not (pd.isna(last_val) or str(last_val).strip() == ""):
                last_dt = datetime.strptime(str(last_val), "%Y-%m-%d %H:%M:%S")
                unlock_time = last_dt + timedelta(hours=LOCKOUT_HOURS)
                if datetime.now() < unlock_time:
                    eligible = False

            if not eligible:
                st.error(f"🚫 রিফিল লকড! পরবর্তী সময়: {unlock_time.strftime('%b %d, %I:%M %p')}")
            else:
                st.success("✅ রাইডার যোগ্য।")
                with st.expander("🔓 অপারেটর প্যানেল (পিন দিন)"):
                    op_pin = st.text_input("Operator PIN", type="password", key="op_pin_field")
                    if op_pin == OPERATOR_PIN:
                        c1, c2 = st.columns(2)
                        with c1:
                            liters = st.number_input("লিটার পরিমাণ", 1.0, 100.0, 5.0)
                            confirm = st.button("💾 Confirm & Save")
                        with c2:
                            # ছবি তোলা এখন ঐচ্ছিক (Optional)
                            photo = st.camera_input("গাড়ির ছবি (ঐচ্ছিক)")
                        
                        if confirm:
                            # ছবি তোলা বাধ্যতামূলক নয়, তাই সরাসরি সেভ হবে
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            df.loc[mask, 'Last_Refill'] = now_str
                            df.loc[mask, 'Liters'] = liters
                            try:
                                spread.df_to_sheet(df, index=False, replace=True)
                                st.cache_data.clear()
                                st.success("সাফল্যজনকভাবে ডাটা সেভ হয়েছে!")
                                st.balloons()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Sync error: {e}")

with tab2:
    st.subheader("📝 নতুন রেজিস্ট্রেশন")
    with st.form("reg_form"):
        col1, col2 = st.columns(2)
        with col1:
            dist = st.selectbox("জেলা", sorted(BD_DISTRICTS))
            series = st.selectbox("সিরিজ", SERIES_LIST)
        with col2:
            num = st.text_input("নাম্বার (যেমন: 11-0101)")
            name = st.text_input("নাম")
        
        if st.form_submit_button("রেজিস্ট্রেশন সম্পন্ন করুন"):
            if num and name:
                f_id = f"{dist}-{series}-{num}".upper()
                if clean_id(f_id) in df['RiderID'].apply(clean_id).values:
                    st.error("আইডি অলরেডি আছে!")
                else:
                    new_row = pd.DataFrame([{"RiderID": f_id, "Name": name, "Last_Refill": "", "Liters": 0}])
                    updated_df = pd.concat([df, new_row], ignore_index=True)
                    spread.df_to_sheet(updated_df, index=False, replace=True)
                    st.cache_data.clear()
                    st.success(f"সফলভাবে নিবন্ধিত: {f_id}"); st.rerun()

with tab3:
    st.subheader("📊 আজকের রিপোর্ট")
    try:
        df_rep = df.copy()
        df_rep['Last_Refill'] = pd.to_datetime(df_rep['Last_Refill'], errors='coerce')
        today_data = df_rep[df_rep['Last_Refill'].dt.date == datetime.now().date()]
        st.metric("আজকের মোট বাইক", len(today_data))
        st.dataframe(today_data[['RiderID', 'Name', 'Liters', 'Last_Refill']], use_container_width=True)
    except: st.write("এখনো কোনো ডাটা নেই।")

# --- সাইডবার ---
st.sidebar.title("⚙️ টুলস")
with st.sidebar.expander("📥 QR কোড তৈরি"):
    qr_id = st.text_input("আইডি দিন (QR এর জন্য)")
    if qr_id:
        qr_link = f"{APP_URL}?rider={qr_id.upper().replace(' ', '%20')}"
        qr_img = qrcode.make(qr_link)
        buf = io.BytesIO(); qr_img.save(buf, format="PNG")
        st.image(buf.getvalue(), caption=qr_id.upper())
