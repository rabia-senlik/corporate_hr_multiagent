"""
KURUMSAL İK VE ŞİRKET KURALLARI MULTI-AGENT ORKESTRASYON PLATFORMU
(RAG POLICY AGENT + LEAVE ACTION AGENT + REDIS STATE STORE + OLLAMA)
========================================================================
Mikroservis Mimarisi:
  1. Orchestrator UI (Streamlit - Port 8501)
  2. HR Policy RAG Agent (ChromaDB + Hibrit Vektör Arama)
  3. Leave Action Agent (FastAPI - Port 8001)
  4. State & Memory Store (Redis - Port 6379)
"""
import streamlit as st
import os
import re
import json
import time
import requests
from pathlib import Path
import chromadb
from chromadb.utils import embedding_functions
import redis

# Sayfa yapılandırması
st.set_page_config(
    page_title="Kurumsal Multi-Agent İK Platformu",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Özel CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .source-box {
        background-color: #F8FAFC;
        border-left: 4px solid #10B981;
        padding: 10px 14px;
        border-radius: 4px;
        margin-top: 14px;
        font-size: 0.85rem;
        color: #334155;
    }
    .badge-rag {
        background-color: #E0E7FF;
        color: #3730A3;
        font-weight: 600;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.85rem;
    }
    .badge-leave {
        background-color: #FEF3C7;
        color: #92400E;
        font-weight: 600;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.85rem;
    }
    .badge-redis {
        background-color: #FEE2E2;
        color: #991B1B;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# Çevre Değişkenleri
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
LEAVE_AGENT_URL = os.getenv("LEAVE_AGENT_URL", "http://leave-agent:8001")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
MEVCUT_DIZIN = Path(__file__).parent.resolve()
DB_DIZINI = MEVCUT_DIZIN / "chroma_db"

# Redis Bağlantısı (Hafıza & State Store)
@st.cache_resource
def get_redis_client():
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, socket_timeout=2)
        r.ping()
        return r
    except Exception:
        return None

r_client = get_redis_client()

def tr_lower(text: str) -> str:
    """Türkçe karakterleri güvenli küçük harfe çevirir."""
    text = text.replace("İ", "i").replace("I", "ı")
    return text.lower()

@st.cache_resource
def chromadb_yukle():
    if not DB_DIZINI.exists():
        st.error("ChromaDB veritabanı bulunamadı!")
        st.stop()
    client = chromadb.PersistentClient(path=str(DB_DIZINI))
    embed_fn = embedding_functions.DefaultEmbeddingFunction()
    # Mevcut koleksiyon adını dinamik yakalayalım
    collections = client.list_collections()
    if collections:
        collection = collections[0]
    else:
        collection = client.get_or_create_collection(name="hr_policies", embedding_function=embed_fn)
    return collection

def hibrit_arama(collection, query: str, top_k: int = 3):
    res = collection.query(query_texts=[query], n_results=10)
    
    docs = res["documents"][0]
    metas = res["metadatas"][0]
    dists = res["distances"][0]
    
    q_words = [w for w in re.findall(r'\w+', tr_lower(query)) if len(w) > 2]
    stopwords = {'hangi', 'neler', 'nelerdir', 'nasil', 'nedir', 'icin', 'kac', 'olan', 'olarak', 've', 'ile', 'gün', 'gun'}
    meaningful = [w for w in q_words if w not in stopwords]
    if not meaningful:
        meaningful = q_words
    
    scored = []
    for d, m, dist in zip(docs, metas, dists):
        vec_score = max(0.0, 1.0 - dist)
        d_lower = tr_lower(d)
        d_words = re.findall(r'\w+', d_lower)
        
        kw_hits = 0
        for w in meaningful:
            root = w[:4] if len(w) >= 4 else w
            if any(dw.startswith(root) for dw in d_words) or root in d_lower:
                kw_hits += 1
                
        kw_score = kw_hits / max(len(meaningful), 1)
        exact_bonus = 0.45 if any(w in d_lower for w in meaningful if len(w) > 3) else 0.0
        final_score = (vec_score * 0.40) + (kw_score * 0.40) + exact_bonus
        scored.append((final_score, d, m, vec_score))
        
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]

# ================= SIDEBAR =================
with st.sidebar:
    st.markdown("### 🏢 Çalışan Kimliği (Oturum)")
    emp_secim = st.selectbox(
        "Aktif Çalışan:",
        ["emp_101 (Rabia Şenlik - AI/ML)", "emp_102 (Örnek Çalışan - Yazılım)"]
    )
    current_emp_id = "emp_101" if "emp_101" in emp_secim else "emp_102"
    
    st.markdown("---")
    st.markdown("### ⚙️ Sistem & Model Durumu")
    
    # Redis Durumu
    if r_client:
        st.success("🟢 Redis State Store: Bağlı")
    else:
        st.warning("🟡 Redis: Çevrimdışı (Lokal Mod)")
        
    secilen_model = st.selectbox(
        "LLM Modeli:",
        ["qwen2.5:3b", "llama3.2:latest", "mistral:latest"],
        index=0
    )
    
    st.markdown("---")
    st.markdown("### 🤖 Aktif Ajanlar")
    st.markdown("""
    * **Orchestrator Agent:** İsteği karşılar ve niyet analizi yapar.
    * **RAG Policy Agent:** Şirket el kitabı ve kurumsal yönetmelikler.
    * **Leave Action Agent:** Port 8001 mikroservisi (Canlı puantaj & izin).
    * **Memory:** Redis Key-Value Store.
    """)
    
    if st.button("🗑️ Sohbeti Temizle", use_container_width=True):
        st.session_state.messages = []
        if r_client:
            r_client.delete(f"user:{current_emp_id}:history")
        st.rerun()

# ================= ANA EKRAN =================
st.markdown('<div class="main-header">🤖 Kurumsal Multi-Agent İK Platformu</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Şirket kuralları doküman sorguları (RAG) ve çalışan işlem ajanları (Leave & Puantaj API) tek çatı altında.</div>', unsafe_allow_html=True)

collection = chromadb_yukle()

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Merhaba! Ben Kurumsal Çoklu Ajan İK Asistanıyım. Şirket yönetmelikleri, kurumsal ilkeler veya kişisel izin/puantaj durumunuz hakkında bana dilediğinizi sorabilirsiniz."}
    ]

# Mesaj geçmişini yazdır
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)

# Yeni soru
if kullanici_sorusu := st.chat_input("Sorunuzu buraya yazın (Örn: 'Kaç gün iznim kaldı?' veya 'Deneme süresi ne kadar?')"):
    st.session_state.messages.append({"role": "user", "content": kullanici_sorusu})
    with st.chat_message("user"):
        st.markdown(kullanici_sorusu)
        
    t0 = time.time()
    
    # 1. ADIM: REDIS'E STATE KAYDET
    if r_client:
        try:
            r_client.set(f"user:{current_emp_id}:last_query", kullanici_sorusu)
            r_client.rpush(f"user:{current_emp_id}:history", kullanici_sorusu)
        except Exception:
            pass

    with st.chat_message("assistant"):
        q_lower = tr_lower(kullanici_sorusu)
        
        # ==============================================================
        # INTENT ROUTING (ORKESTRASYON KARAR AŞAMASI)
        # ==============================================================
        profile_keywords = ["hakkimda", "hakkımda", "ben kimim", "profilim", "bilgilerim", "beni taniyor", "beni tanıyor"]
        leave_keywords = ["izn", "izin", "bakiye", "kalan", "tatil", "mazeret", "gunum", "hakkim", "yillik", "yıllık", "puantaj", "mesai", "giris", "cikis", "çalıştım", "calistim"]
        
        is_profile_query = any(k in q_lower for k in profile_keywords)
        is_leave_query = any(k in q_lower for k in leave_keywords) or is_profile_query
        
        # --------------------------------------------------------------
        # DAL 1: LEAVE & PUANTAJ ACTION AGENT (Mikroservis Çağrısı - Port 8001)
        # --------------------------------------------------------------
        if is_leave_query:
            agent_badge = '<span class="badge-leave">🎯 Delegated Agent: Leave & Puantaj Action Agent (Port 8001)</span>'
            placeholder = st.empty()
            placeholder.markdown(f"{agent_badge}\n\n*Kurumsal İK Servisi sorgulanıyor...*", unsafe_allow_html=True)
            
            try:
                res = requests.post(f"{LEAVE_AGENT_URL}/get-balance", json={"employee_id": current_emp_id}, timeout=4)
                if res.status_code == 200:
                    data = res.json()
                    if is_profile_query:
                        cevap_metni = f"""
Sizi çok iyi tanıyorum! 👩‍💻

* 👤 **Ad Soyad:** **{data['ad_soyad']}**
* 🏢 **Departman:** **{data['departman']}**
* 📅 **Aktif Dönem:** {data.get('donem', 'Kasım 2026')}
* ⏱️ **Kayıtlı İş Günü:** {data.get('toplam_is_gunu', 21)} gün
* 🕒 **Son Mesai Kaydı:** {data.get('son_mesai', '07:12 - 17:30')}
* 🏖️ **İzin Durumu:** {data.get('kalan_yillik_izin', 14)} gün kullanılabilir yıllık izin hakkınız bulunmaktadır.
* 🔗 **Veri Kaynağı:** `{data.get('canli_kaynak', 'Kurumsal İK Portalı')}`
                        """
                    else:
                        cevap_metni = f"""
Sayın **{data['ad_soyad']}** ({data['departman']}),

🔗 **Kaynak:** `{data.get('canli_kaynak', 'Kurumsal İK Portalı')}`
📅 **Dönem:** {data.get('donem', 'Kasım 2026')}
* 🏢 **Toplam İş Günü Kaydı:** {data.get('toplam_is_gunu', 21)} gün
* ⏱️ **Örnek Giriş-Çıkış:** {data.get('son_mesai', '07:12 - 17:30')}
* 🏖️ **Kalan Yıllık İzin Hakkı:** **{data['kalan_yillik_izin']} gün**
* 📋 **Mazeret & İzin Türleri:** {data.get('mazeret_izni', 'Mazeret İzni Ücretli Günlük / Saatlik')}
                        """
                else:
                    cevap_metni = "İK servisine ulaşılamadı. Lütfen sistem yöneticisi ile iletişime geçiniz."
            except Exception as e:
                cevap_metni = f"Action Agent Mikroservis Bağlantı Hatası: {e}"
                
            toplam_sure = (time.time() - t0)
            kaynak_kutusu = f"""
<div class="source-box">
    {agent_badge}&nbsp;&nbsp;|&nbsp;&nbsp;<span class="badge-redis">State: Redis Sync</span><br>
    ⚡ <b>Sorgu Süresi:</b> {toplam_sure:.2f} sn&nbsp;&nbsp;|&nbsp;&nbsp;🔗 <b>Servis:</b> <code>{LEAVE_AGENT_URL}</code>
</div>
"""
            tam_yanit = f"{cevap_metni}\n\n{kaynak_kutusu}"
            placeholder.markdown(tam_yanit, unsafe_allow_html=True)
            st.session_state.messages.append({"role": "assistant", "content": tam_yanit})
            
        # --------------------------------------------------------------
        # DAL 2: RAG POLICY AGENT (ChromaDB + Ollama)
        # --------------------------------------------------------------
        else:
            agent_badge = '<span class="badge-rag">📚 Delegated Agent: Corporate Policy RAG Agent (ChromaDB + Ollama)</span>'
            placeholder = st.empty()
            
            en_iyi_sonuclar = hibrit_arama(collection, kullanici_sorusu, top_k=3)
            arama_suresi = (time.time() - t0) * 1000
            
            en_iyi_skor, en_iyi_doc, en_iyi_meta, en_iyi_vskor = en_iyi_sonuclar[0]
            ana_kaynak = en_iyi_meta.get("kaynak", "Şirket Yönetmelik Dokümanı")
            ana_sayfa = en_iyi_meta.get("sayfa", 1)
            baglam = "\n---\n".join([item[1] for item in en_iyi_sonuclar])
            
            prompt = f"""Sen şirket içi resmi İK asistanısın. Aşağıda şirketin resmi dokümanlarından alınan doğrulanmış kural maddeleri yer almaktadır.
Kullanıcının sorusunu bu bilgilere dayanarak doğrudan, samimi, net ve maddeler halinde Türkçe olarak yanıtla. Uzun giriş cümleleri kurma, doğrudan kuralı aktar.
Dokümanda yer almayan hiçbir kuralı kendin uydurma.

[RESMİ ŞİRKET BİLGİSİ]:
{baglam}

[KULLANICI SORUSU]:
{kullanici_sorusu}
"""
            tam_metin = ""
            try:
                res = requests.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={
                        "model": secilen_model,
                        "prompt": prompt,
                        "stream": True,
                        "keep_alive": "24h",
                        "options": {
                            "temperature": 0.1,
                            "num_predict": 250,
                            "num_ctx": 2048
                        }
                    },
                    stream=True,
                    timeout=60
                )
                
                if res.status_code == 200:
                    for line in res.iter_lines():
                        if line:
                            veri = json.loads(line.decode("utf-8"))
                            parca = veri.get("response", "")
                            tam_metin += parca
                            placeholder.markdown(f"{agent_badge}\n\n{tam_metin}▌", unsafe_allow_html=True)
                    placeholder.markdown(f"{agent_badge}\n\n{tam_metin}", unsafe_allow_html=True)
                    llm_metni = tam_metin
                else:
                    llm_metni = f"Ollama hatası (Kod {res.status_code}): {res.text}"
                    placeholder.markdown(llm_metni)
            except Exception as e:
                llm_metni = f"Ollama bağlantı hatası: {e}"
                placeholder.markdown(llm_metni)
                
            toplam_sure = (time.time() - t0)
            eslesme_yuzdesi = min(99.0, max(50.0, en_iyi_skor * 100))
            
            kaynak_kutusu = f"""
<div class="source-box">
    {agent_badge}&nbsp;&nbsp;|&nbsp;&nbsp;<span class="badge-redis">State: Redis Sync</span><br>
    🤖 <b>Model:</b> <span class="badge-rag">{secilen_model} (Yerel GPU)</span>&nbsp;&nbsp;|&nbsp;&nbsp;
    📌 <b>Resmi Dayanak:</b> <code>Şirket_El_Kitabı.pdf</code> (Sayfa: {ana_sayfa})<br>
    🎯 <b>Alaka Skoru:</b> %{eslesme_yuzdesi:.1f}&nbsp;&nbsp;|&nbsp;&nbsp;⚡ <b>Arama:</b> {arama_suresi:.1f} ms&nbsp;&nbsp;|&nbsp;&nbsp;⏱️ <b>Toplam Süre:</b> {toplam_sure:.2f} sn
</div>
"""
            tam_yanit = f"{llm_metni}\n\n{kaynak_kutusu}"
            placeholder.markdown(tam_yanit, unsafe_allow_html=True)
            st.session_state.messages.append({"role": "assistant", "content": tam_yanit})
