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

# Secrets থেকে পিন আনা (সেট করা না থাকলে ডিফল্ট '1234')
try:
    OPERATOR_PIN = st.secrets["PUMP_SECRET_PIN"]
except:
    OPERATOR_PIN = "1234"

# জেলা ও সিরিজ তালিকা
BD_DISTRICTS = ["BAGERHAT", "BANDARBAN", "BARGUNA", "BARISHAL", "BHOLA", "BOGURA", "BRAHMANBARIA", "CHANDPUR", "CHATTOGRAM", "CHATTOGRAM METRO", "CHUADANGA", "COMILLA", "COXS BAZAR", "DHAKA", "DHAKA METRO", "DINAJPUR", "FARIDPUR", "FENI", "GAIBANDHA", "GAZIPUR", "GOPALGANJ", "HABIGANJ", "JAMALPUR", "JASHORE", "JHALOKATHI", "JHENAIDAH", "JOYPURHAT", "KHAGRACHHARI", "KHULNA", "KHULNA METRO", "KISHOREGANJ", "KURIGRAM", "KUSHTIA", "LAKSHMIPUR", "LALMONIRHAT", "MADARIPUR", "MAGURA", "MANIKGANJ", "MEHERPUR", "MOULVIBAZAR", "MUNSHIGANJ", "MYMENSINGH", "NAOGAON", "NARAIL", "NARAYANGANJ", "NARSINGDI", "NATORE", "NETROKONA", "NILPHAMARI", "NOAKHALI", "PABNA", "PANCHAGARH", "PATUAKHALI", "PIROJPUR", "RAJBARI", "RAJSHAHI", "RAJSHAHI METRO", "RANGAMATI", "RANGPUR", "SATKHIRA", "SHARIATPUR", "SHERPUR", "SIRAJGANJ", "SUNAMGANJ", "SYLHET", "SYLHET METRO", "TANGAIL", "THAKURGAON"]
SERIES_LIST = ["KA", "KHA", "GA", "GHA", "CHA", "THA", "HA", "LA", "MA", "BA"]

# --- ২. ডাটাবেজ কানেকশন ---
@st.cache_data(ttl=5)
def fetch_data(_spread_obj):
    try:
        data = _spread_obj.sheet_to_df(index=0)
        data.columns = data.columns.str.strip()
        return data
    except Exception:
        return pd.DataFrame(columns=["RiderID", "Name", "Last_Refill", "Liters"])

if "gcp_service_account" in st.secrets:
    creds = dict(st.secrets["gcp_service_account"])
    try:
        spread = Spread("FuelTracker", config=creds)
        df = fetch_data(spread)
    except Exception as e:
        st.error(f"কানেকশন সমস্যা: {e}"); st.stop()
else:
    st.error("Credentials missing in Streamlit Secrets!"); st.stop()

def clean_id(text):
    return str(text).lower().replace(" ", "").replace("-", "").strip()

# --- ৩. মেইন ইন্টারফেস (ট্যাব সিস্টেম) ---
st.title("⛽ FuelGuard Pro")
tab1, tab2, tab3 = st.tabs(["🔍 স্ট্যাটাস ও রিফিল", "📝 নতুন রেজিস্ট্রেশন", "📊 রিপোর্ট"])

# --- ট্যাব ১: স্ট্যাটাস চেক ও ফুয়েল ইনপুট (পিন প্রোটেক্টেড) ---
with tab1:
    st.subheader("রাইডার ভেরিফিকেশন")
    query_params = st.query_params
    url_id = query_params.get("rider", "")
    
    scanned_id = st.text_input("🔍 রাইডার আইডি লিখুন বা স্ক্যান করুন", value=url_id, placeholder="যেমন: PABNA HA 11-0101")
    
    if scanned_id:
        s_id = clean_id(scanned_id)
        mask = df['RiderID'].apply(clean_id) == s_id
        rider_row = df[mask]

        if rider_row.empty:
            st.warning(f"❌ আইডি '{scanned_id}' পাওয়া যায়নি।")
        else:
            r_data = rider_row.iloc[0]
            st.info(f"👤 রাইডার: **{r_data['Name']}** | আইডি: **{r_data['RiderID']}**")

            # এলিজিবিলিটি চেক
            eligible = True
            last_val = r_data['Last_Refill']
            if not (pd.isna(last_val) or str(last_val).strip() == ""):
                last_dt = datetime.strptime(str(last_val), "%Y-%m-%d %H:%M:%S")
                unlock_time = last_dt + timedelta(hours=LOCKOUT_HOURS)
                if datetime.now() < unlock_time:
                    eligible = False

            if not eligible:
                st.error(f"🚫 রিফিল লকড! পরবর্তীতে পাবেন: {unlock_time.strftime('%b %d, %I:%M %p')}")
                diff = unlock_time - datetime.now()
                st.write(f"অপেক্ষা করতে হবে: {diff.days} দিন {diff.seconds//3600} ঘণ্টা।")
            else:
                st.success("✅ রাইডার জ্বালানি পাওয়ার যোগ্য।")
                
                # --- পিন শুধুমাত্র এখানে লাগবে ---
                st.markdown("---")
                st.subheader("⛽ পাম্প অপারেটর প্যানেল")
                with st.expander("🔓 ডাটা এন্ট্রি করতে ক্লিক করুন (পিন প্রয়োজন)"):
                    op_pin = st.text_input("অপারেশন পিন (Operator PIN)", type="password", key="fuel_pin")
                    
                    if op_pin == OPERATOR_PIN:
                        col1, col2 = st.columns(2)
                        with col1:
                            liters = st.number_input("লিটার পরিমাণ", 1.0, 100.0, 5.0)
                            confirm = st.button("💾 Confirm & Save")
                        with col2:
                            photo = st.camera_input("গাড়ির ছবি (বাধ্যতামূলক)")
                        
                        if confirm:
                            if photo:
                                df.loc[mask, 'Last_Refill'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                df.loc[mask, 'Liters'] = liters
                                try:
                                    spread.df_to_sheet(df, index=False, replace=True)
                                    st.cache_data.clear()
                                    st.success("সাফল্যজনকভাবে আপডেট হয়েছে!")
                                    st.balloons(); st.rerun()
                                except Exception as e:
                                    st.error(f"Sync error: {e}")
                            else:
                                st.warning("⚠️ ছবি তোলা ছাড়া কনফার্ম করা যাবে না।")
                    elif op_pin != "":
                        st.error("ভুল পিন! আপনি ইনপুট দিতে পারবেন না।")

# --- ট্যাব ২: রেজিস্ট্রেশন (সবার জন্য উন্মুক্ত - পিন লাগবে না) ---
with tab2:
    st.subheader("📝 নতুন রাইডার রেজিস্ট্রেশন")
    with st.form("reg_form"):
        c1, c2 = st.columns(2)
        with c1:
            dist = st.selectbox("জেলা", sorted(BD_DISTRICTS))
            series = st.selectbox("গাড়ির শ্রেণী (Series)", SERIES_LIST)
        with c2:
            num = st.text_input("গাড়ির নাম্বার (যেমন: 11-0101)")
            name = st.text_input("রাইডারের নাম")
        
        if st.form_submit_button("রেজিস্ট্রেশন সম্পন্ন করুন"):
            if num and name:
                f_id = f"{dist}-{series}-{num}".upper()
                if clean_id(f_id) in df['RiderID'].apply(clean_id).values:
                    st.error("এই আইডিটি ইতিমধ্যে নিবন্ধিত!")
                else:
                    new_row = pd.DataFrame([{"RiderID": f_id, "Name": name, "Last_Refill": "", "Liters": 0}])
                    updated_df = pd.concat([df, new_row], ignore_index=True)
                    spread.df_to_sheet(updated_df, index=False, replace=True)
                    st.cache_data.clear()
                    st.success(f"অভিনন্দন! {f_id} সফলভাবে নিবন্ধিত হয়েছে।")
                    st.rerun()
            else:
                st.warning("সবগুলো ঘর পূরণ করুন।")

# --- ট্যাব ৩: সাধারণ রিপোর্ট ---
with tab3:
    st.subheader("📊 আজকের বণ্টন চিত্র")
    try:
        df_rep = df.copy()
        df_rep['Last_Refill'] = pd.to_datetime(df_rep['Last_Refill'], errors='coerce')
        today_data = df_rep[df_rep['Last_Refill'].dt.date == datetime.now().date()]
        
        m1, m2 = st.columns(2)
        m1.metric("আজকের মোট বাইক", len(today_data))
        m2.metric("আজকের মোট লিটার", f"{pd.to_numeric(today_data['Liters'], errors='coerce').sum()} L")
        st.dataframe(today_data[['RiderID', 'Name', 'Liters', 'Last_Refill']], use_container_width=True)
    except:
        st.write("এখনো কোনো ডাটা নেই।")

# --- সাইডবার: QR জেনারেটর ---
st.sidebar.title("⚙️ টুলস")
with st.sidebar.expander("📥 QR কোড তৈরি করুন"):
    qr_id = st.text_input("আইডি দিন (QR এর জন্য)")
    if qr_id:
        qr_link = f"{APP_URL}?rider={qr_id.upper().replace(' ', '%20')}"
        qr_img = qrcode.make(qr_link)
        buf = io.BytesIO(); qr_img.save(buf, format="PNG")
        st.image(buf.getvalue(), caption=qr_id.upper())
