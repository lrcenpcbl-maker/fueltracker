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

# পিন সেটআপ
try:
    OPERATOR_PIN = st.secrets["PUMP_SECRET_PIN"]
except:
    OPERATOR_PIN = "1234"

# জেলা ও সিরিজ তালিকা
BD_DISTRICTS = ["BAGERHAT", "BANDARBAN", "BARGUNA", "BARISHAL", "BHOLA", "BOGURA", "BRAHMANBARIA", "CHANDPUR", "CHATTOGRAM", "CHATTOGRAM METRO", "CHUADANGA", "COMILLA", "COXS BAZAR", "DHAKA", "DHAKA METRO", "DINAJPUR", "FARIDPUR", "FENI", "GAIBANDHA", "GAZIPUR", "GOPALGANJ", "HABIGANJ", "JAMALPUR", "JASHORE", "JHALOKATHI", "JHENAIDAH", "JOYPURHAT", "KHAGRACHHARI", "KHULNA", "KHULNA METRO", "KISHOREGANJ", "KURIGRAM", "KUSHTIA", "LAKSHMIPUR", "LALMONIRHAT", "MADARIPUR", "MAGURA", "MANIKGANJ", "MEHERPUR", "MOULVIBAZAR", "MUNSHIGANJ", "MYMENSINGH", "NAOGAON", "NARAIL", "NARAYANGANJ", "NARSINGDI", "NATORE", "NETROKONA", "NILPHAMARI", "NOAKHALI", "PABNA", "PANCHAGARH", "PATUAKHALI", "PIROJPUR", "RAJBARI", "RAJSHAHI", "RAJSHAHI METRO", "RANGAMATI", "RANGPUR", "SATKHIRA", "SHARIATPUR", "SHERPUR", "SIRAJGANJ", "SUNAMGANJ", "SYLHET", "SYLHET METRO", "TANGAIL", "THAKURGAON"]
SERIES_LIST = ["KA", "KHA", "GA", "GHA", "CHA", "THA", "HA", "LA", "MA", "BA"]

# --- ২. পপ-আপ নির্দেশিকা (Instruction Pop-up) ---
@st.dialog("📖 ফুয়েলগার্ড ইউজার গাইড ও আপডেট")
def show_instruction_popup():
    st.markdown("""
    ### ⛽ FuelGuard Pro এ আপনাকে স্বাগতম!
    সিস্টেমের নিরাপত্তা ও সহজলভ্যতা নিশ্চিতে কিছু পরিবর্তন আনা হয়েছে:

    ---
    #### 🆕 নতুন পরিবর্তনসমূহ:
    1. **উন্মুক্ত রেজিস্ট্রেশন:** এখন যেকোনো রাইডার নিজে **'নতুন রেজিস্ট্রেশন'** ট্যাব থেকে আইডি তৈরি করতে পারবেন। কোনো পিন লাগবে না।
    2. **পিন প্রটেক্টড ইনপুট:** তেল দেওয়ার রেকর্ড সেভ করতে শুধুমাত্র পাম্প অপারেটরের **গোপন পিন** প্রয়োজন।
    3. **ঐচ্ছিক ছবি:** গাড়ির ছবি তোলা এখন আর বাধ্যতামূলক নয়।
    4. **অটো-রিফ্রেশ:** ট্রানজ্যাকশন শেষ হলে অ্যাপটি নিজে থেকেই পরবর্তী ইউজার চেক করার জন্য তৈরি হয়ে যাবে।

    ---
    #### 🛠 ব্যবহারবিধি:
    * **রাইডার:** রেজিস্ট্রেশন ট্যাব থেকে আইডি তৈরি করুন এবং কিউআর কোড সংগ্রহ করুন।
    * **অপারেটর:** আইডি সার্চ করে যদি **Eligible** দেখায়, তবে পিন দিয়ে ডাটা এন্ট্রি সম্পন্ন করুন।
    """)
    if st.button("ঠিক আছে, শুরু করি"):
        st.session_state.show_manual = False
        st.rerun()

if "show_manual" not in st.session_state:
    st.session_state.show_manual = True

if st.session_state.show_manual:
    show_instruction_popup()

# --- ৩. ডাটাবেজ কানেকশন ও হেল্পারস ---
@st.cache_data(ttl=5)
def fetch_data(_spread_obj):
    try:
        data = _spread_obj.sheet_to_df(index=0)
        data.columns = data.columns.str.strip()
        # কলামের নামগুলো কনসিস্টেন্ট রাখা
        return data
    except:
        return pd.DataFrame(columns=["RiderID", "Name", "Last_Refill", "Liters"])

if "gcp_service_account" in st.secrets:
    creds = dict(st.secrets["gcp_service_account"])
    try:
        spread = Spread("FuelTracker", config=creds)
        df = fetch_data(spread)
    except Exception as e:
        st.error(f"Google Sheet Connection Failed: {e}"); st.stop()
else:
    st.error("GCP Credentials missing in Streamlit Secrets!"); st.stop()

def clean_id(text):
    return str(text).lower().replace(" ", "").replace("-", "").strip()

# --- ৪. মেইন ইন্টারফেস (ট্যাব সিস্টেম) ---
st.title("⛽ FuelGuard Pro")
tab1, tab2, tab3 = st.tabs(["🔍 স্ট্যাটাস ও রিফিল", "📝 নতুন রেজিস্ট্রেশন", "📊 রিপোর্ট"])

with tab1:
    st.subheader("🔍 রাইডার ভেরিফিকেশন")
    q_params = st.query_params
    url_id = q_params.get("rider", "")
    scanned_id = st.text_input("আইডি লিখুন বা স্ক্যান করুন", value=url_id, placeholder="যেমন: PABNA HA 11-0101")

    if scanned_id:
        s_id = clean_id(scanned_id)
        # ডাটাফ্রেমের ইনডেক্স খুঁজে বের করা
        df['temp_id'] = df['RiderID'].apply(clean_id)
        rider_indices = df.index[df['temp_id'] == s_id].tolist()

        if not rider_indices:
            st.warning(f"❌ আইডি '{scanned_id}' ডাটাবেজে পাওয়া যায়নি।")
        else:
            idx = rider_indices[0]
            r_data = df.iloc[idx]
            st.info(f"👤 রাইডার: **{r_data['Name']}** | আইডি: **{r_data['RiderID']}**")

            # --- ৭২ ঘণ্টা লক লজিক (Stronger Fix) ---
            eligible = True
            unlock_time = None
            last_refill_val = str(df.at[idx, 'Last_Refill']).strip()

            if last_refill_val and last_refill_val.lower() != "nan" and last_refill_val != "":
                try:
                    last_dt = datetime.strptime(last_refill_val, "%Y-%m-%d %H:%M:%S")
                    unlock_time = last_dt + timedelta(hours=LOCKOUT_HOURS)
                    if datetime.now() < unlock_time:
                        eligible = False
                except Exception as e:
                    st.error(f"Date Error: {e}. ফরম্যাট সমস্যা হতে পারে।")

            if not eligible:
                st.error(f"🚫 রিফিল লকড! পরবর্তীতে জ্বালানি পাবেন:")
                st.subheader(f"📅 {unlock_time.strftime('%b %d, %Y - %I:%M %p')}")
                diff = unlock_time - datetime.now()
                st.write(f"অপেক্ষা করতে হবে: {diff.days} দিন {diff.seconds//3600} ঘণ্টা।")
            else:
                st.success("### ✅ রাইডার জ্বালানি পাওয়ার যোগ্য।")
                st.markdown("---")
                with st.expander("🔓 পাম্প অপারেটর প্যানেল (ইনপুট দিতে ক্লিক করুন)"):
                    op_pin = st.text_input("অপারেশন পিন দিন", type="password", key="op_pin_tab1")
                    if op_pin == OPERATOR_PIN:
                        c1, c2 = st.columns(2)
                        with c1:
                            liters_to_save = st.number_input("লিটারের পরিমাণ", 1.0, 100.0, 5.0)
                            confirm_save = st.button("💾 Confirm & Save to Cloud")
                        with c2:
                            photo = st.camera_input("গাড়ির ছবি (ঐচ্ছিক)")
                        
                        if confirm_save:
                            # ডাটা আপডেট করা
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            # টেম্পোরারি কলাম সরিয়ে ডাটা আপডেট
                            final_df = df.drop(columns=['temp_id'])
                            final_df.at[idx, 'Last_Refill'] = now_str
                            final_df.at[idx, 'Liters'] = liters_to_save
                            
                            try:
                                spread.df_to_sheet(final_df, index=False, replace=True)
                                st.cache_data.clear() # ক্যাশ ক্লিয়ার করা খুব জরুরি
                                st.success("✅ ডাটাবেজ আপডেট হয়েছে!")
                                st.balloons()
                                st.rerun() # অটো রিফ্রেশ
                            except Exception as e:
                                st.error(f"Sync failed: {e}")
                    elif op_pin != "":
                        st.error("ভুল পিন! আপনি ইনপুট দিতে পারবেন না।")

with tab2:
    st.subheader("📝 নতুন রাইডার রেজিস্ট্রেশন")
    with st.form("public_reg_form"):
        col1, col2 = st.columns(2)
        with col1:
            dist = st.selectbox("জেলা/মেট্রো এরিয়া", sorted(BD_DISTRICTS))
            series = st.selectbox("সিরিজ", SERIES_LIST)
        with col2:
            num = st.text_input("গাড়ির নাম্বার (যেমন: 11-0101)")
            name = st.text_input("রাইডারের পূর্ণ নাম")
        
        if st.form_submit_button("নিবন্ধন সম্পন্ন করুন"):
            if num and name:
                f_id = f"{dist}-{series}-{num}".upper()
                # ডুপ্লিকেট চেক
                df_for_check = fetch_data(spread)
                if clean_id(f_id) in df_for_check['RiderID'].apply(clean_id).values:
                    st.error("এই আইডি ইতিমধ্যে নিবন্ধিত!")
                else:
                    new_row = pd.DataFrame([{"RiderID": f_id, "Name": name, "Last_Refill": "", "Liters": 0}])
                    updated_df = pd.concat([df_for_check, new_row], ignore_index=True)
                    try:
                        spread.df_to_sheet(updated_df, index=False, replace=True)
                        st.cache_data.clear()
                        st.success(f"সফল! আইডি: {f_id}")
                        st.rerun()
                    except:
                        st.error("রেজিস্ট্রেশন ব্যর্থ হয়েছে।")
            else:
                st.warning("নাম এবং গাড়ির নাম্বার দেওয়া বাধ্যতামূলক।")

with tab3:
    st.subheader("📊 আজকের লাইভ রিপোর্ট")
    try:
        report_df = df.copy()
        if 'temp_id' in report_df.columns: report_df = report_df.drop(columns=['temp_id'])
        
        report_df['Last_Refill'] = pd.to_datetime(report_df['Last_Refill'], errors='coerce')
        today_data = report_df[report_df['Last_Refill'].dt.date == datetime.now().date()]
        
        m1, m2 = st.columns(2)
        m1.metric("আজকের মোট বাইক", len(today_data))
        m2.metric("আজকের মোট জ্বালানি (L)", f"{pd.to_numeric(today_data['Liters'], errors='coerce').sum()} L")
        
        st.dataframe(today_data[['RiderID', 'Name', 'Liters', 'Last_Refill']], use_container_width=True)
    except:
        st.write("রিপোর্ট জেনারেট করা যাচ্ছে না।")

# --- সাইডবার টুলস ---
st.sidebar.title("⚙️ অপশন")
with st.sidebar.expander("📥 QR কোড তৈরি"):
    qr_id_input = st.sidebar.text_input("আইডি দিন (QR কোডের জন্য)")
    if qr_id_input:
        qr_url = f"{APP_URL}?rider={qr_id_input.upper().replace(' ', '%20')}"
        qr_gen = qrcode.make(qr_url)
        buf = io.BytesIO()
        qr_gen.save(buf, format="PNG")
        st.sidebar.image(buf.getvalue(), caption=qr_id_input.upper())
