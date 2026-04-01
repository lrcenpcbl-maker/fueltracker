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
    ### ⛽ ফুয়েলগার্ড (FuelGuard) এ স্বাগতম
    এই অ্যাপটি জ্বালানি বণ্টন ব্যবস্থা স্বচ্ছ এবং নিরপেক্ষ রাখার জন্য তৈরি করা হয়েছে।
    
    **নিয়মাবলী:**
    1. **৭২ ঘণ্টার নিয়ম:** একবার তেল নেওয়ার পর পরবর্তী **৭২ ঘণ্টা** পর্যন্ত ওই আইডি দিয়ে পুনরায় তেল নেওয়া যাবে না।
    2. **কিউআর কোড স্ক্যান:** রাইডারের আইডি কার্ডের QR কোড স্ক্যান করুন অথবা ম্যানুয়ালি আইডি ইনপুট দিন।
    3. **স্ট্যাটাস চেক:** - ✅ **সবুজ সংকেত:** রাইডার তেল পাওয়ার যোগ্য। লিটার লিখে 'Confirm' বাটনে চাপ দিন।
        - 🚫 **লাল সংকেত:** রাইডার লকড। স্ক্রিনে প্রদর্শিত সময় শেষ না হওয়া পর্যন্ত অপেক্ষা করতে হবে।
    4. **ডেটা সেভ:** প্রতিবার তেল দেওয়ার পর অবশ্যই **'Confirm & Save'** বাটনে ক্লিক করবেন।

    **নতুন ফিচারসমূহ:**
    1. **ছবি ভেরিফিকেশন:** তেল দেওয়ার সময় নিরাপত্তার জন্য গাড়ির ছবি তোলা বাধ্যতামূলক।
    2. **সেন্ট্রাল ডাটাবেজ:** যেকোনো পাম্প থেকে তেল নিলেই এই সিস্টেম আপডেট হবে।
    3. **লাইভ রিপোর্ট:** অ্যাডমিন প্যানেলে আজকের মোট রিফিলের হিসাব দেখা যাবে।

    *যেকোনো সমস্যায় অ্যাডমিনের সাথে যোগাযোগ করুন: **vpersonal1123@gmail.com***
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
    """আইডি থেকে স্পেস ও ড্যাশ সরিয়ে ছোট হাতের অক্ষরে রূপান্তর করে।"""
    return str(text).lower().replace(" ", "").replace("-", "").strip()

# --- 5. MAIN INTERFACE ---
st.title("⛽ FuelGuard Pro: স্মার্ট ফুয়েল মনিটরিং")

# হ্যান্ডেল কিউআর স্ক্যান (URL ?rider=ID)
query_params = st.query_params
scanned_id = query_params.get("rider", st.text_input("🔍 রাইডার আইডি লিখুন বা কিউআর স্ক্যান করুন", placeholder="যেমন: pabna ha 11 0101"))

if scanned_id:
    s_id = clean_id(scanned_id)
    mask = df['RiderID'].apply(clean_id) == s_id
    rider_row = df[mask]

    if rider_row.empty:
        st.warning(f"❌ আইডি '{scanned_id}' পাওয়া যায়নি।")
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
            st.info(f"পরবর্তীতে পাওয়া যাবে: {unlock_time.strftime('%b %d, %I:%M %p')}")
        
        else:
            st.success("### ✅ রিফিল অনুমোদিত")
            col1, col2 = st.columns(2)
            with col1:
                liters_to_issue = st.number_input("লিটারের পরিমাণ (Liters)", 1.0, 100.0, 5.0)
                confirm_btn = st.button("💾 Confirm & Save to Cloud")
            
            with col2:
                photo = st.camera_input("নিরাপত্তার জন্য গাড়ির ছবি তুলুন")
            
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

# --- 6. SIDEBAR: ADMIN, REGISTRATION & QR ---
st.sidebar.title("⚙️ এডমিন প্যানেল")

# নতুন রাইডার রেজিস্ট্রেশন (৬৪ জেলা ভিত্তিক)
with st.sidebar.expander("📝 নতুন রাইডার রেজিস্ট্রেশন", expanded=False):
    with st.form("reg_form"):
        sel_dist = st.selectbox("জেলা/মেট্রো এরিয়া", sorted(BD_DISTRICTS))
        sel_series = st.selectbox("গাড়ির শ্রেণী (Series)", ["KA", "KHA", "GA", "GHA", "CHA", "THA", "HA", "LA", "MA", "BA"])
        sel_num = st.text_input("গাড়ির নাম্বার (যেমন: 11-0101)")
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
