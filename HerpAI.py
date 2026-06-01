import sys
import subprocess

# =======================================================
# KUTUBXONALARNI AVTOMATIK TEKSHIRISH VA O'RNATISH
# =======================================================
REQUIRED_PACKAGES = {
    "streamlit": "streamlit",
    "google.genai": "google-genai",
    "pydantic": "pydantic",
    "PIL": "pillow"
}

for module_name, pip_name in REQUIRED_PACKAGES.items():
    try:
        __import__(module_name)
    except ImportError:
        print(f"📦 {pip_name} kutubxonasi topilmadi. Avtomatik o'rnatilmoqda...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])

import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from PIL import Image
import time
import os
import json
import shutil
from datetime import datetime

# ==========================================
# 1. PYDANTIC STRUKTURASI
# ==========================================
class HerpAnalysisSchema(BaseModel):
    top1_name: str = Field(description="Eng ehtimoliy sudraluvchi nomi (O'zbekcha va Lotincha).")
    top1_pct: int = Field(description="Birinchi turning nisbiy ehtimolligi (0-100).")
    top2_name: str = Field(description="Ikkinchi ehtimoliy tur nomi.")
    top2_pct: int = Field(description="Ikkinchi turning nisbiy ehtimolligi.")
    top3_name: str = Field(description="Uchinchi ehtimoliy tur nomi.")
    top3_pct: int = Field(description="Uchinchi turning nisbiy ehtimolligi.")
    danger_level: str = Field(description="Faqat: 'ZAHARLI' yoki 'ZAHARSIZ'.")
    ai_confidence: int = Field(description="AI ishonch darajasi (0-100).")
    expert_report: str = Field(description="Batafsil gerpetologik ekspertiza hisoboti (Sabab va belgilar).")
    quality_warning: str = Field(description="Rasm sifati past bo'lsa ogohlantirish, aks holda bo'sh satr.")

# ==========================================
# 2. TIZIM SOZLAMALARI
# ==========================================
st.set_page_config(page_title="Ilon AI — Ekspert Tizimi", page_icon="🐍", layout="wide")

if "parsed_data" not in st.session_state:
    st.session_state.parsed_data = None

DEFAULT_FOLDER = os.path.join(os.path.expanduser('~'), 'HerpAI_Dataset')

# ==========================================
# 3. YORDAMCHI FUNKSIYALAR
# ==========================================
def load_statistics(folder_path):
    stats = {"total": 0, "zaharli": 0, "zaharsiz": 0, "species_count": {}, "history": []}
    if not os.path.exists(folder_path):
        return stats

    for file in os.listdir(folder_path):
        if file.startswith("meta_") and file.endswith(".json"):
            try:
                with open(os.path.join(folder_path, file), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    stats["total"] += 1
                    danger = str(data.get("danger_level", "")).upper()
                    if "ZAHARLI" in danger and "ZAHARSIZ" not in danger:
                        stats["zaharli"] += 1
                    elif "ZAHARSIZ" in danger:
                        stats["zaharsiz"] += 1
                        
                    top1 = data.get("top1_name", "Noma'lum tur")
                    stats["species_count"][top1] = stats["species_count"].get(top1, 0) + 1
                    stats["history"].append({
                        "Sana/Vaqt": data.get("timestamp", ""),
                        "Asosiy Taxmin": top1,
                        "Ehtimollik": f"{data.get('top1_pct', 0)}%",
                        "Xavflilik": danger
                    })
            except Exception:
                continue
    stats["history"] = sorted(stats["history"], key=lambda x: x["Sana/Vaqt"], reverse=True)[:100]
    return stats

def save_analysis_data(folder_path, image, parsed_json):
    os.makedirs(folder_path, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    img_filename = f"img_{timestamp}.png"
    image.save(os.path.join(folder_path, img_filename))
    
    metadata = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "image_file": img_filename,
        "model_version": "gemini-2.5-flash",
        "analysis_version": "V6-Ultimate",
        **parsed_json
    }
    
    meta_filename = f"meta_{timestamp}.json"
    with open(os.path.join(folder_path, meta_filename), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)

# ==========================================
# 4. INTERFEYS (UI)
# ==========================================
with st.sidebar:
    st.header("⚙️ Tizim Sozlamalari")
    api_key = st.text_input("🔑 Gemini API Kalit:", type="password")
    st.write("---")
    st.subheader("📁 Ma'lumotlarni Saqlash Joyi")
    
    save_folder = st.text_input("Papka to'liq manzili:", value=DEFAULT_FOLDER)
    st.info("💡 Barcha rasm va natijalar ushbu manzilda xavfsiz lokal saqlanadi.")

st.title("🐍 Sudraluvchilarni Aniqlash — Ekspert Diagnostika Tizimi")
st.error("**🛑 QAT'IY OGOHLANTIRISH:** Noma'lum ilonlarga ASLO yaqinlashmang! Dastur faqat ilmiy tadqiqotlar va ma'lumot yig'ish uchun mo'ljallangan.")

tab1, tab2 = st.tabs(["🔍 Diagnostika Markazi", "📊 Tizim Statistikasi & Eksport"])

with tab1:
    input_method = st.radio("Tasvir manbasini tanlang:", ["Kameradan rasmga olish", "Fayllar orasidan yuklash"], horizontal=True)
    
    uploaded_file = None
    if input_method == "Kameradan rasmga olish":
        uploaded_file = st.camera_input("📸 To'g'ridan-to'g'ri rasmga oling")
    else:
        uploaded_file = st.file_uploader("📂 Sudraluvchi rasmini yuklang", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        
        if input_method == "Fayllar orasidan yuklash":
            st.image(image, caption="Tahlil qilinayotgan tasvir", use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1: start = st.button("🔍 Ekspertiza Boshlash", type="primary", use_container_width=True)
        with col2: reset = st.button("🔄 Yangi Tahlil", use_container_width=True)
            
        if reset:
            st.session_state.parsed_data = None
            st.rerun()
            
        if start:
            if not api_key:
                st.error("⚠️ Iltimos, tahlilni boshlashdan oldin chap paneldan API kalitni kiriting!")
            else:
                # 📝 Vizual status va progress bar tayyorlash
                status_text = st.empty()
                p_bar = st.progress(0)
                
                try:
                    # 1-Bosqich
                    status_text.info("📸 **[20%]** Tasvir qabul qilindi. Format tekshirilmoqda...")
                    p_bar.progress(20)
                    time.sleep(0.5)
                    
                    # 2-Bosqich
                    status_text.info("🌐 **[40%]** Google Gemini 2.5 Flash serverlari bilan aloqa o'rnatilmoqda...")
                    client = genai.Client(api_key=api_key)
                    p_bar.progress(40)
                    
                    prompt = """
                    Sen O'zbekiston sudraluvchilari bo'yicha professional zoolog-gerpetologsan.
                    Rasmni vizual tahlil qil va JSON sxemasidagi maydonlarni o'zbek tilida to'ldir.
                    Top-1, Top-2 va Top-3 ehtimollik foizlarining yig'indisi aniq 100 bo'lishini ta'minlang.
                    """
                    
                    max_retries = 3
                    response = None
                    
                    # 3-Bosqich (Tahlil va Himoya)
                    for attempt in range(max_retries):
                        try:
                            current_pct = 50 + attempt * 10
                            status_text.info(f"🧠 **[{current_pct}%]** Sun'iy intellekt tahlil qilmoqda (Urinish: {attempt + 1}/{max_retries})...")
                            p_bar.progress(current_pct)
                            
                            response = client.models.generate_content(
                                model='gemini-2.5-flash',
                                contents=[prompt, image],
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json",
                                    response_schema=HerpAnalysisSchema,
                                ),
                            )
                            break
                        except Exception as server_error:
                            error_msg = str(server_error).lower()
                            if "503" in error_msg or "high demand" in error_msg:
                                if attempt < max_retries - 1:
                                    status_text.warning(f"⏳ **[{current_pct}%]** Server band (503). {attempt + 2}-urinish 3 soniyadan so'ng...")
                                    time.sleep(3)
                                    continue
                                else:
                                    raise Exception("503_TIMEOUT")
                            elif "api_key" in error_msg or "400" in error_msg:
                                raise Exception("BAD_API_KEY")
                            else:
                                raise server_error
                    
                    # 4-Bosqich
                    status_text.info("✅ **[90%]** Tahlil yakunlandi! Natijalar xotiraga yozilmoqda...")
                    p_bar.progress(90)
                    parsed_json = json.loads(response.text)
                    
                    # Matematik normallashtirish
                    total = parsed_json.get("top1_pct", 0) + parsed_json.get("top2_pct", 0) + parsed_json.get("top3_pct", 0)
                    if total > 0 and total != 100:
                        parsed_json["top1_pct"] = round(parsed_json["top1_pct"] * 100 / total)
                        parsed_json["top2_pct"] = round(parsed_json["top2_pct"] * 100 / total)
                        parsed_json["top3_pct"] = 100 - parsed_json["top1_pct"] - parsed_json["top2_pct"]

                    st.session_state.parsed_data = parsed_json
                    save_analysis_data(save_folder, image, parsed_json)
                    
                    # 5-Bosqich
                    status_text.success("🎉 **[100%]** Barcha jarayonlar muvaffaqiyatli yakunlandi!")
                    p_bar.progress(100)
                    time.sleep(1.5)
                    
                    status_text.empty()
                    p_bar.empty()
                    
                except Exception as e:
                    # ❌ MAXSUS O'ZBEKCHA XATOLIKLARNI USHLASH
                    status_text.empty()
                    p_bar.empty()
                    error_str = str(e)
                    
                    if "503_TIMEOUT" in error_str:
                        st.error("❌ **Tarmoq xatoligi (503):** Google Gemini serverlarida hozircha juda ko'p yuklama mavjud. Dastur bir necha marta qayta urinib ko'rdi, ammo ulanib bo'lmadi. Iltimos, 1 daqiqadan so'ng qayta urinib ko'ring.")
                    elif "BAD_API_KEY" in error_str:
                        st.error("🔑 **API Kalit xatosi:** Kiritilgan Gemini API kaliti noto'g'ri, eskirgan yoki noto'g'ri nusxalangan. Iltimos, kalitni tekshirib qaytadan kiriting.")
                    elif "connection" in error_str.lower() or "network" in error_str.lower():
                        st.error("🌐 **Internet xatoligi:** Kompyuteringizda internet aloqasi uzilgan yoki Google serverlariga kirish bloklangan. Iltimos, tarmog'ingizni tekshiring.")
                    else:
                        st.error(f"⚠️ **Kutilmagan texnik xatolik:**\nBu rasm formatining buzilganligi yoki kutilmagan API xatosi bo'lishi mumkin.\n\n**Texnik xulosa:** `{error_str}`")

        # NATIJALAR EKRANI
        if st.session_state.parsed_data:
            data = st.session_state.parsed_data
            if data.get("quality_warning"): st.warning(f"⚠️ {data.get('quality_warning')}")
            
            v1, v2 = st.columns([1, 2])
            with v1:
                if "ZAHARLI" in str(data.get("danger_level", "")).upper() and "ZAHARSIZ" not in str(data.get("danger_level", "")).upper():
                    st.error("☠️ **XAVFLILIK:**\n\n## **ZAHARLI**")
                else:
                    st.success("🛡️ **XAVFLILIK:**\n\n## **ZAHARSIZ**")
                
                st.write(f"🎯 **AI Ishonchi:** {data.get('ai_confidence', 50)}%")
                    
            with v2:
                st.subheader("📊 Turlarning nisbiy ehtimolligi:")
                t1, p1 = data.get("top1_name", ""), data.get("top1_pct", 0)
                t2, p2 = data.get("top2_name", ""), data.get("top2_pct", 0)
                t3, p3 = data.get("top3_name", ""), data.get("top3_pct", 0)
                
                st.write(f"1. **{t1}** — {p1}%"); st.progress(p1)
                st.write(f"2. **{t2}** — {p2}%"); st.progress(p2)
                st.write(f"3. **{t3}** — {p3}%"); st.progress(p3)
                
            st.write("---")
            st.info(data.get("expert_report"))

with tab2:
    st.header("📊 Tizim Statistikasi va Datasetni Eksport Qilish")
    stats = load_statistics(save_folder)
    
    if stats["total"] > 0:
        m1, m2, m3 = st.columns(3)
        m1.metric("Jami tasvirlar", stats["total"])
        m2.metric("Zaharli", stats["zaharli"])
        m3.metric("Zaharsiz", stats["zaharsiz"])
        
        st.write("---")
        st.subheader("📦 Datasetni Eksport Qilish (Arxivlash)")
        
        zip_filename = f"HerpAI_Dataset_{datetime.now().strftime('%Y%m%d')}"
        _, col_zip, _ = st.columns([1, 2, 1])
        
        with col_zip:
            shutil.make_archive(zip_filename, 'zip', save_folder)
            with open(f"{zip_filename}.zip", "rb") as fp:
                st.download_button(
                    label="⬇️ Yig'ilgan bazani ZIP formatida yuklab olish",
                    data=fp,
                    file_name=f"{zip_filename}.zip",
                    mime="application/zip",
                    type="primary",
                    use_container_width=True
                )
        
        st.write("---")
        c1, c2 = st.columns([1, 1])
        with c1:
            st.subheader("🗂 Turlar reytingi")
            st.table(list(stats["species_count"].items()))
        with c2:
            st.subheader("🕒 Oxirgi faolliklar")
            st.dataframe(stats["history"], use_container_width=True)
    else:
        st.info("Omborda hozircha ma'lumot yo'q. Tahlilni boshlang!")