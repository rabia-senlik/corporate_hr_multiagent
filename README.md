# 🤖 Kurumsal Şirket Kuralları & Multi-Agent İK Platformu

Bu proje; kurumsal İnsan Kaynakları süreçlerini otomatize etmek, şirket yönetmeliklerini semantik arama ile yanıtlamak ve canlı puantaj/izin verilerini anlık sorgulamak amacıyla geliştirilmiş **Production-Grade Multi-Agent AI & RAG Platformudur**.

Tekil monolitik yapılar yerine; bağımsız konteynerlerden oluşan mikroservis mimarisi, in-memory durum yönetimi (Redis) ve hibrit vektör arama motoru (ChromaDB + Ollama) prensipleriyle tasarlanmıştır.

---

## 🏗️ Sistem Mimarisi

```
                                [ KULLANICI / ÇALIŞAN ]
                                           │
                                           ▼ (Port: 8501)
┌──────────────────────────────────────────────────────────────────────────────────┐
│ DOCKER BRIDGE NETWORK (hr-network)                                               │
│                                                                                  │
│    ┌────────────────────────────────────────────────────────┐                    │
│    │  CONTAINER 1: STREAMLIT UI & MASTER ORCHESTRATOR       │                    │
│    │  (Kullanıcıyı karşılar, niyet analizi/routing yapar)   │                    │
│    └─────────────┬──────────────────────────┬───────────────┘                    │
│                  │                          │                                    │
│             State│                     State│             ┌───────────────────┐  │
│                  ▼                          ▼             │ CONTAINER 2:      │  │
│         ┌───────────────────────────────────────────────┐ │ REDIS             │  │
│         │              REDIS STATE STORE                ├─┤ (Session State &  │  │
│         │ (Oturum hafızası & ajanlar arası kara tahta)  │ │ Short-Term Memory)│  │
│         └───────────────────────────────────────────────┘ └───────────────────┘  │
│                  ▲                          ▲                                    │
│                  │                          │                                    │
│                  │ (Doküman Sorusu)         │ (İşlemsel Soru)                    │
│                  ▼                          ▼                                    │
│    ┌──────────────────────────────┐ ┌──────────────────────────────────────┐     │
│    │ CONTAINER 1 (Dahili Modül):  │ │ CONTAINER 3: LEAVE & PUANTAJ AGENT   │     │
│    │ RAG POLICY AGENT             │ │ (FastAPI - Port: 8001)               │     │
│    │ • ChromaDB Hibrit Vektör     │ │ • Canlı Kurumsal İK Portalı Köprüsü  │     │
│    │ • Qwen 2.5 (3B) Yerel GPU    │ │ • Otomatik Puantaj & İzin Ayrıştırıcı│     │
│    └──────────────────────────────┘ └──────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Öne Çıkan Özellikler

1. **Akıllı Niyet Yönlendirme (Intent Routing):**
   * Kullanıcının sorusundaki kök kelimeleri ve Türkçe morfolojik yapıları (`izin -> iznim`, `puantaj`, `mesai`) analiz ederek isteği doğru uzman ajana yönlendirir.
2. **Canlı Puantaj & İzin Entegrasyonu (Action Agent):**
   * Dahili İK yönetim portalı ile konuşarak çalışanın anlık çalışma saatlerini, giriş-çıkış kayıtlarını ve kalan izin haklarını canlı olarak ayrıştırıp sunar.
3. **Hibrit Vektör RAG Motoru (Policy Agent):**
   * Şirket yönetmeliği, deneme süresi ve sağlık sigortası kurallarını ChromaDB hibrit arama (Dense Vector + Keyword BM25 mantığı) ve yerel Ollama GPU çıkarımı ile sıfır veri sızıntısıyla yanıtlar.
4. **Dağıtık Hafıza ve Durum Yönetimi (Redis):**
   * LLM'lerin durumsuz (stateless) yapısını çözmek için konuşma geçmişini ve oturum durumunu mikroservisler arasında paylaşılan Redis RAM belleğinde saklar.
5. **Konteyner Orkestrasyonu (Docker & Docker Compose):**
   * Tüm sistem tek bir `docker compose up -d` komutuyla, bağımsız ağlar ve port yönlendirmeleriyle dakikalar içinde ayağa kaldırılabilir.

---

## 🛠️ Teknoloji Yığını

* **Orchestration & Backend:** Python 3.11, FastAPI, Uvicorn, Streamlit
* **LLM & Embedding:** Ollama (`qwen2.5:3b` / `llama3.2`), ChromaDB
* **State & Caching:** Redis 7 (Alpine)
* **Veri Kazıma & İstemci:** HTTPX (Async), BeautifulSoup4
* **DevOps & Altyapı:** Docker, Docker Compose, Linux Bridge Networking

---

## 💻 Kurulum ve Çalıştırma

### 1. Depoyu Klonlayın
```bash
git clone https://github.com/rabia-senlik/enterprise_hr_assistant.git
cd enterprise_hr_assistant
```

### 2. Ortam Değişkenlerini Tanımlayın
```bash
cp .env.example .env
# .env dosyasını açıp kendi kurumsal İK portalı oturum anahtarınızı tanımlayın
```

### 3. Docker Compose ile Başlatın
```bash
docker compose up -d --build
```

### 4. Arayüze Erişin
Tarayıcınızdan **`http://localhost:8501`** adresine giderek platformu kullanmaya başlayabilirsiniz!

* **Streamlit UI:** `http://localhost:8501`
* **Leave Action Agent API (Docs):** `http://localhost:8001/docs`
* **Redis Port:** `6379`

---

## 🔐 Güvenlik ve Gizlilik
* Şirket yönetmelik PDF'leri ve canlı kimlik doğrulama anahtarları `.gitignore` kapsamındadır ve depoda yer almaz.
* Üretim ortamında şirket verileri dış API'lara gönderilmez, yerel açık kaynaklı modeller üzerinde izole olarak işlenir.
