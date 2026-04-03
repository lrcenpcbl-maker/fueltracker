import streamlit as st
from gspread_pandas import Spread
import pandas as pd
from datetime import datetime, timedelta
import qrcode
from PIL import Image
import io

# --- 1. CONFIGURATION & SECRETS ---
st.set_page_config(page_title="FuelGuard Pro", page_icon="⛽", layout="wide")

# ৭২ ঘণ্টার নিয়ম
LOCKOUT_HOURS = 72
APP_URL = "https://fuel-tracker.streamlit.app" 

# Secrets থেকে পিন নিয়ে আসা (না থাকলে ডিফল্ট '1234')
try:
    OPERATOR_PIN = st.secrets["PUMP_SECRET_PIN"]
except:
    OPERATOR_PIN = "1234"

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

# --- 2. DATABASE CONNECTION ---
@st.cache_data(ttl=5)
def fetch_data(_spread_obj):
    try:
        data = _spread_obj.sheet_to_df(index=0)
        data.columns = data.columns.str.strip()
        return data
    except Exception:
        return pd.DataFrame(columns=["RiderID", "Name", "Last_Refill", "Liters"])

# Google Sheets কানেকশন
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

# --- 3. HELPER FUNCTIONS ---
def clean_id(text):
    """আইডি থেকে স্পেস ও ড্যাশ সরিয়ে ছোট হাতের অক্ষরে রূপান্তর করে।"""
    return str(text).lower().replace(" ", "").replace("-", "").strip()

# --- 4. MAIN INTERFACE ---
st.title("⛽ FuelGuard Pro: স্মার্ট ফুয়েল মনিটরিং")
st.markdown("---")

# হ্যান্ডেল কিউআর স্ক্যান বা ম্যানুয়াল ইনপুট
query_params = st.query_params
scanned_id = query_params.get("rider", "")

if not scanned_id:
    scanned_id = st.text_input("🔍 রাইডার আইডি চেক করুন (Status Check)", placeholder="যেমন: PABNA HA 11-0101")

if scanned_id:
    s_id = clean_id(scanned_id)
    mask = df['RiderID'].apply(clean_id) == s_id
    rider_row = df[mask]

    if rider_row.empty:
        st.warning(f"❌ আইডি '{scanned_id}' ডাটাবেজে পাওয়া যায়নি।")
    else:
        r_data = rider_row.iloc[0]
        rider_name = r_data['Name']
        last_val = r_data['Last_Refill']
        actual_id = r_data['RiderID']
        
        st.header(f"👤 রাইডার: {rider_name}")
        st.info(f"গাড়ির রেজিস্ট্রেশন: {actual_id}")

        # চেক এলিজিবিলিটি (৭২ ঘণ্টা লজিক)
        eligible = True
        unlock_time = None
        if not (pd.isna(last_val) or str(last_val).strip() == ""):
            try:
                last_dt = datetime.strptime(str(last_val), "%Y-%m-%d %H:%M:%S")
                unlock_time = last_dt + timedelta(hours=LOCKOUT_HOURS)
                if datetime.now() < unlock_time:
                    eligible = False
            except:
                st.error("তারিখের ফরম্যাটে ইন্টারনাল সমস্যা।")

        if not eligible:
            st.error(f"### 🚫 রিফিল রিজেক্ট (Locked)")
            diff = unlock_time - datetime.now()
            st.subheader(f"অপেক্ষা করুন: {diff.days} দিন {diff.seconds//3600} ঘণ্টা")
            st.info(f"পরবর্তীতে জ্বালানি পাবেন: {unlock_time.strftime('%b %d, %I:%M %p')}")
        
        else:
            st.success("### ✅ রিফিল অনুমোদিত")
            st.write("রাইডার বর্তমানে জ্বালানি পাওয়ার যোগ্য। পাম্প অপারেটর ট্রানজ্যাকশন সম্পন্ন করবেন।")
            
            # --- ৫. পাম্প অপারেটর ভেরিফিকেশন (পিন প্রোটেকটেড) ---
            st.markdown("---")
            with st.expander("🔓 পাম্প অপারেটর এক্সেস (শুধুমাত্র পাম্পের জন্য)"):
                op_pin = st.text_input("অপারেশন পিন দিন (Operator PIN)", type="password", key="main_op_pin")
                
                if op_pin == OPERATOR_PIN:
                    st.success("অপারেটর মোড আনলক হয়েছে!")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        liters_to_issue = st.number_input("লিটারের পরিমাণ (Liters)", 1.0, 100.0, 5.0)
                        photo = st.camera_input("নিরাপত্তার জন্য গাড়ির ছবি তুলুন")
                        confirm_btn = st.button("💾 Confirm & Save to Cloud")
                    
                    if confirm_btn:
                        if photo is not None:
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            df.loc[mask, 'Last_Refill'] = now_str
                            df.loc[mask, 'Liters'] = liters_to_issue
                            
                            try:
                                spread.df_to_sheet(df, index=False, replace=True)
                                st.cache_data.clear() 
                                st.success(f"✅ সফল! {rider_name}-কে {liters_to_issue} লিটার তেল দেওয়া হয়েছে।")
                                st.balloons()
                                st.rerun() 
                            except Exception as e:
                                st.error(f"Sync Failed: {e}")
                        else:
                            st.warning("⚠️ ছবি তোলা বাধ্যতামূলক।")
                elif op_pin != "":
                    st.error("ভুল পিন! আপনি ডাটা এন্ট্রি দিতে পারবেন না।")

# --- ৬. SIDEBAR: ADMIN & REGISTRATION ---
st.sidebar.title("⚙️ এডমিন প্যানেল")
admin_pin_input = st.sidebar.text_input("প্যানেল আনলক পিন", type="password")

if admin_pin_input == OPERATOR_PIN:
    # নতুন রাইডার রেজিস্ট্রেশন
    with st.sidebar.expander("📝 নতুন রাইডার রেজিস্ট্রেশন", expanded=False):
        with st.form("reg_form"):
            sel_dist = st.selectbox("জেলা/মেট্রো এরিয়া", sorted(BD_DISTRICTS))
            sel_series = st.selectbox("গাড়ির শ্রেণী", ["KA", "KHA", "GA", "GHA", "CHA", "THA", "HA", "LA", "MA", "BA"])
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

    # কিউআর কোড জেনারেটর
    with st.sidebar.expander("📥 কিউআর কোড তৈরি"):
        qr_input = st.text_input("আইডি লিখুন (QR এর জন্য)")
        if st.button("QR তৈরি করুন"):
            if qr_input:
                qr_link = f"{APP_URL}?rider={qr_input.upper().replace(' ', '%20')}"
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(qr_link)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                st.image(buf.getvalue(), caption=f"QR for: {qr_input.upper()}")

    # লাইভ রিপোর্ট
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 আজকের লাইভ রিপোর্ট")
    try:
        df_rep = df.copy()
        df_rep['Last_Refill'] = pd.to_datetime(df_rep['Last_Refill'], errors='coerce')
        today_df = df_rep[df_rep['Last_Refill'].dt.date == datetime.now().date()]
        st.sidebar.metric("আজকের মোট রিফিল", len(today_df))
        total_liters = pd.to_numeric(today_df['Liters'], errors='coerce').sum()
        st.sidebar.metric("মোট লিটার বিতরণ", f"{total_liters} L")
    except:
        st.sidebar.write("রিপোর্ট লোড করা যাচ্ছে না।")

else:
    if admin_pin_input != "":
        st.sidebar.error("ভুল পিন! এডমিন সেকশন লকড।")
    else:
        st.sidebar.info("এডমিন ফিচার ব্যবহার করতে পিন দিন।")

if st.sidebar.button("🔄 ডাটা রিফ্রেশ করুন"):
    st.cache_data.clear()
    st.rerun()
