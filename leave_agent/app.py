from fastapi import FastAPI
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup
import os

app = FastAPI(title="Corporate HR Live Action Agent")

# GÜVENLİK: Şirket portalları ortam değişkeninden okunur
HR_PORTAL_SESSION_ID = os.getenv("HR_PORTAL_SESSION_ID", "")
HR_PORTAL_URL = os.getenv("HR_PORTAL_URL", "https://hr-portal.company.internal/leave-management/")

class LeaveQuery(BaseModel):
    employee_id: str = "emp_101"

@app.get("/")
def health():
    return {"status": "ok", "service": "Corporate HR Live Action Agent"}

def fetch_live_puantaj():
    if not HR_PORTAL_SESSION_ID:
        return None, "HR_PORTAL_SESSION_ID tanımlanmamış."
        
    cookies = {"sessionid": HR_PORTAL_SESSION_ID}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    with httpx.Client(verify=False, cookies=cookies, headers=headers, timeout=10) as client:
        resp = client.get(HR_PORTAL_URL)
        if resp.status_code != 200:
            return None, f"HR Portal Bağlantı Hatası: HTTP {resp.status_code}"
            
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.find_all("tr", class_="accordion-header-row")
        
        gunler = []
        toplam_calisilan_gun = 0
        
        for r in rows:
            tarih = r.get("data-date", "")
            tds = [td.get_text(strip=True) for td in r.find_all("td")]
            if len(tds) >= 4:
                gun_metni = tds[1]
                giris = tds[2]
                cikis = tds[3]
                
                if giris and cikis and giris != "-" and cikis != "-":
                    toplam_calisilan_gun += 1
                    
                gunler.append({
                    "tarih": tarih,
                    "bilgi": gun_metni,
                    "giris": giris,
                    "cikis": cikis
                })
                
        return {
            "toplam_gun_kaydi": len(gunler),
            "aktif_calisilan_gun": toplam_calisilan_gun,
            "ornek_gunler": gunler[:5],
            "son_gun": gunler[-1] if gunler else None
        }, None

@app.post("/get-balance")
def get_balance(query: LeaveQuery):
    puantaj_data, err = fetch_live_puantaj()
    
    if err or not puantaj_data:
        return {
            "employee_id": query.employee_id,
            "ad_soyad": "Rabia Şenlik",
            "departman": "Yapay Zeka & ML Mühendisliği",
            "kalan_yillik_izin": 14,
            "mazeret_izni": 3,
            "canli_durum": "Demo Fallback Modu",
            "handled_by": "HR Leave Action Agent (Port 8001)"
        }
        
    return {
        "employee_id": query.employee_id,
        "ad_soyad": "Rabia Şenlik",
        "departman": "Yapay Zeka & ML Mühendisliği",
        "donem": "Kasım 2026",
        "toplam_is_gunu": puantaj_data["toplam_gun_kaydi"],
        "calisilan_gun": puantaj_data["aktif_calisilan_gun"],
        "son_mesai": f"{puantaj_data['ornek_gunler'][0]['tarih']} ({puantaj_data['ornek_gunler'][0]['giris']} - {puantaj_data['ornek_gunler'][0]['cikis']})",
        "kalan_yillik_izin": 14,
        "mazeret_izni": "Mazeret İzni Ücretli Günlük / Saatlik (Aktif)",
        "canli_kaynak": "Şirket İK Portalı (Canlı Puantaj)",
        "handled_by": "Live HR Portal Integration Agent (Port 8001)"
    }
