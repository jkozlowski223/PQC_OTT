# PQC OTT - Post-Quantum Cryptography Over-The-Top Streaming System

## Przegląd Projektu

**PQC OTT** to nowoczesny system przesyłania video w sieci (Over-The-Top) zbudowany na architekturze Post-Quantum Cryptography (PQC). Projekt łączy:

- **Post-Quantum Cryptography** - Algorytmy odporne na ataki komputerów kwantowych (Kyber768 KEM, ML-DSA-65)
- **Szyfrowanie AES-256 z rotacją kluczy** - Dynamiczna zmiana kluczy szyfrowania co 10 segmentów wideo
- **Zarządzanie sesją i autoryzacją** - System logowania z kontrolą dostępu
- **Segmentacja wideo** - Porcjonowanie pliku video do transmisji (HLS)
- **REST API** - FastAPI dla wszystkich operacji

### Cel Projektu

Zademonstrowanie, jak łączyć post-kwantowe mechanizmy kryptograficzne z praktyczną infrastrukturą przesyłania video, aby zapewnić bezpieczeństwo przed przyszłymi atakami komputerów kwantowych.

---

## Architektura Projektu

```
PQC_OTT/
├── main.py                 # FastAPI aplikacja główna i API endpoints
├── kms_pqc.py             # Key Management System (KMS) z post-quantum crypto
├── streaming_service.py    # Zarządzanie sesjami i dostarczanie segmentów wideo
├── video_processor.py      # Przetwarzanie video (segmentacja, szyfrowanie)
├── cdn_storage/           # Przechowywanie zaszyfrowanych segmentów wideo
│   ├── playlist.m3u8      # Manifest playlisty HLS
│   ├── segment_000.ts ... # Zaszyfrowane segmenty video (TS)
│   └── .content_keys.json # Mapa rotacyjnych kluczy AES-256
├── vault.enc              # Zaszyfrowany magazyn kluczy (przechowuje ML-DSA klucze)
├── req.txt                # Wymagane biblioteki Python
└── install.sh             # Skrypt instalacji liboqs
```

---

## Komponenty Systemu

### 1. **main.py** - Główna Aplikacja FastAPI

Odpowiadająca za:
- Obsługę żądań HTTP
- Prezentację dashboard'u logowania
- Inicjalizację systemu przy starcie
- Maszerowanie do endpointów autoryzacji i streamingu

#### Kluczowe Funkcje:

| Funkcja | Opis |
|---------|------|
| `startup_event()` | Inicjalizuje system: sprawdza segmenty, generuje/ładuje klucze AES, szyfruje wideo |
| `dashboard()` | Zwraca HTML stronę logowania z interfejsem użytkownika |
| `login_user(req)` | Autoryzuje użytkownika i tworzy sesję streamingu (admin/admin lub guest/guest) |
| `get_watermark(session_id)` | Generuje token wodny na bazie ID sesji i klucza AES |
| `get_session_info(session_id)` | Zwraca szczegóły aktualnej sesji |
| `get_video_stream(session_id)` | Generator streamowania video - iteruje przez segmenty z rotacją kluczy |

#### Główne Zmienne:
- `ROTATION_INTERVAL = 10` - Rotacja klucza AES co 10 segmentów wideo
- `app` - Instancja FastAPI
- `kms` - Instancja Key Management System (post-quantum)
- `video_proc` - Instancja procesora video
- `streaming_service` - Instancja serwisu streamingu

---

### 2. **kms_pqc.py** - Post-Quantum Key Management System

Zarządza wszystkimi kluczami kryptograficznymi przy użyciu algorytmów post-kwantowych.

#### Klasa: `PQCReadyVault`

Magazyn kluczy zaszyfrowany AES-256. Przechowuje wrażliwe dane kryptograficzne.

| Metoda | Opis |
|--------|------|
| `__init__(master_key)` | Inicjalizuje magazyn z głównym kluczem AES |
| `_encrypt_data(data)` | Szyfruje dane przy użyciu AES-256-CTR z losowym IV |
| `_decrypt_data(encrypted_data)` | Deszyfruje dane zaszyfrowane przez `_encrypt_data` |
| `save_key(key_id, key_data)` | Zapisuje klucz w magazynie (JSON, szyfrowany w pliku `vault.enc`) |

#### Klasa: `KMSServer`

Serwer zarządzający kluczami z post-quantum cryptography. Odpowiadający za:
- Generowanie i weryfikowanie tokenów przy użyciu ML-DSA-65 (post-quantum signature)
- Enkapsulację AES-klucza za pomocą Kyber768 (post-quantum KEM)

| Metoda | Opis |
|--------|------|
| `__init__()` | Inicjalizuje serwer: generuje ML-DSA-65 klucze, przechowuje je w Vault |
| `sign_token(payload)` | Podpisuje payload ML-DSA-65, koduje jako base64 JSON token |
| `verify_token(b64_token)` | Weryfikuje token podpisany ML-DSA-65 - zwraca True/False |
| `encapsulate_aes_key(client_kem_public_key)` | Enkapsuluje AES-klucz za pomocą Kyber768 KEM |

#### Algorytmy Kryptograficzne:

| Algorytm | Typ | Przeznaczenie | Post-Quantum |
|----------|-----|---------------|-------------|
| **AES-256** | Symetryczny (CTR mode) | Szyfrowanie kluczy w vault'cie i segmentów video | Nie |  
| **Kyber768** | KEM (Asymetryczny) | Enkapsulacja sesyjnych kluczy AES | Tak - Quantum-safe |
| **ML-DSA-65** | Podpis (Asymetryczny) | Cyfrowe podpisy tokenów sesji | Tak - Quantum-safe |

---

### 3. **streaming_service.py** - Serwis Streamingu

Zarządza sesjami użytkownika i dostarczaniem zaszyfrowanych segmentów wideo.

#### Klasa: `StreamingSession`

Reprezentuje sesję jednego użytkownika.

| Atrybut | Opis |
|---------|------|
| `user_id` | Identyfikator użytkownika |
| `session_id` | Unikalny UUID sesji |
| `is_authorized` | Czy użytkownik ma dostęp do video |
| `created_at` | Timestamp utworzenia sesji |
| `aes_keys` | Słownik rotacyjnych kluczy AES (tylko dla autoryzowanych) |
| `segments_downloaded` | Lista pobranych ID segmentów |

| Metoda | Opis |
|--------|------|
| `__init__(user_id, is_authorized)` | Tworzy nową sesję dla użytkownika |
| `set_aes_keys(keys_map)` | Przypisuje klucze AES (tylko jeśli autoryzowany) |

#### Klasa: `StreamingService`

Główny serwis zarządzający wszystkimi sesjami i dostarczaniem video.

| Metoda | Opis |
|--------|------|
| `__init__(kms_server, video_processor)` | Inicjalizuje serwis z KMS i procesorem video |
| `set_content_keys(keys_map)` | Ustawia mapę rotacyjnych kluczy AES na starcie |
| `create_session(user_id, is_authorized)` | Tworzy nową sesję, przypisuje klucze jeśli autoryzowana |
| `get_segment(session_id, segment_id, interval)` | Pobiera i deszyfruje segment video, lub zwraca błąd dostępu |
| `get_available_segments()` | Zwraca listę dostępnych ID segmentów wideo |
| `get_session_info(session_id)` | Zwraca informacje o sesji (status, liczba pobranych segmentów) |

#### Logika `get_segment()`:

1. Sprawdza, czy sesja istnieje
2. Wczytuje fizyczny plik segmentu z `cdn_storage`
3. **Jeśli autoryzowany:**
   - Oblicza `current_interval = (segment_id // interval) * interval`
   - Pobiera odpowiedni AES-klucz dla tego interwału
   - Deszyfruje segment (IV + CTR mode)
   - Zwraca odszyfrowane dane
4. **Jeśli nieuautoryzowany:**
   - Zwraca błąd dostępu bez zdeszyfrowywania

---

### 4. **video_processor.py** - Procesor Video

Odpowiada za segmentację i szyfrowanie pliku video.

#### Klasa: `VideoProcessor`

| Atrybut | Opis |
|---------|------|
| `input_file` | Ścieżka do źródłowego pliku video (np. `vid.webm`) |
| `output_dir` | Katalog wyjściowy dla segmentów (np. `cdn_storage`) |

| Metoda | Opis |
|--------|------|
| `__init__(input_file, output_dir)` | Inicjalizuje procesor, tworzy katalog `output_dir` |
| `segment_video()` | Segmentuje video przy użyciu FFmpeg na 5-sekundowe fragmenty |
| `encrypt_segments(keys_map, interval)` | Szyfruje każdy segment właściwym AES-256 kluczem z rotacją |

#### Logika `segment_video()`:

1. Uruchamia komendę FFmpeg z parametrami:
   - `-c:v libx264` - Kodek video H.264
   - `-c:a aac` - Kodek audio AAC
   - `-segment_time 5` - Każdy segment trwa 5 sekund
   - `-f segment` - Format wyjściowy: HLS segment
2. Generuje pliki `segment_000.ts`, `segment_001.ts`, etc.
3. Tworzy plik `playlist.m3u8` (manifest HLS)

#### Logika `encrypt_segments()`:

```
Dla każdego segmentu:
  1. Wydobądź index segmentu z nazwy pliku (segment_042 → 42)
  2. Oblicz current_interval = (42 // 10) * 10 = 40
  3. Pobierz AES-klucz dla interwału 40
  4. Wygeneruj losowy IV (16 bajtów)
  5. Zaszyfruj dane z użyciem AES-256-CTR
  6. Zapisz IV + ciphertext do pliku (IV prepend)
```

**Rotacja kluczy:**
- Segmenty 0-9 → klucz[0]
- Segmenty 10-19 → klucz[10]
- Segmenty 20-29 → klucz[20]
- Segmenty 30-39 → klucz[30]
- itd.

Dzięki temu, nawet jeśli klucz zostanie skompromitowany, tylko 10 segmentów wideo będzie zagrożone.

---

## Logika Bezpieczeństwa

### Przepływ Autoryzacji

```
1. Użytkownik loguje się (admin/admin lub guest/guest)
        ↓
2. login_user() tworzy sesję w StreamingService
        ↓
3. Jeśli admin: sesja jest AUTORYZOWANA (is_authorized=True)
   - AES-klucze są przypisane sesji
   
   Jeśli guest: sesja jest NIEAUTORYZOWANA (is_authorized=False)
   - Żadne klucze nie są przypisane
        ↓
4. Żądanie segmentu: get_segment(session_id, segment_id)
        ↓
5. Jeśli AUTORYZOWANA:
   - Pobierz segment z CDN
   - Odszyfruj za pomocą odpowiedniego AES-klucza
   - Zwróć dane audio/video
   
   Jeśli NIEAUTORYZOWANA:
   - Zwróć błąd dostępu (bez deszyfrowywania)
```

### Ruch Danych Video

```
Original Video (vid.webm)
        ↓
[FFmpeg] - segmentacja na 5-sekundowe fragmenty
        ↓
Segmenty (surowe dane)
        ↓
[AES-256-CTR] - szyfrowanie z rotacją co 10 segmentów
        ↓
cdn_storage/segment_000.ts (zaszyfrowany)
cdn_storage/segment_001.ts (zaszyfrowany)
... 
cdn_storage/segment_117.ts (zaszyfrowany)
        ↓
[Client Request] - GET /streaming/video/stream?session_id=xxx
        ↓
Jeśli autoryzowany:
  [Deszyfrowanie AES-256-CTR] → Oryginalny segment
  ↓ (transmisja)
  Video odtwarzane w przeglądarce

Jeśli nieuautoryzowany:
  ❌ Błąd: "Brak dostępu"
```

---

## 🚀 Jak System Działa - Szczegółowy Przebieg

### Faza 1: Startup (inicjalizacja)

```python
1. FastAPI app.on_event("startup") uruchomiony
2. Tworzy katalog cdn_storage (jeśli nie istnieje)
3. Sprawdza czy istnieją segmenty wideo
   ├─ TAK: Ładuje istniejące klucze z .content_keys.json
   └─ NIE: 
       ├─ Uruchamia video_proc.segment_video()
       │   └─ FFmpeg tnie video na segmenty 5-sekundowe
       ├─ Generuje 12 zestawów kluczy AES-256 (rotacja co 10 seg)
       ├─ Uruchamia video_proc.encrypt_segments(keys_map)
       │   └─ Każdy segment szyfrowany odpowiednim kluczem AES
       └─ Zapisuje keys_map do .content_keys.json (base64)
```

### Faza 2: Logowanie

```python
1. Użytkownik wpisuje login na stronie /
2. JavaScript wysyła POST do /auth/login-user
   {username: "admin", password: "admin"}
3. login_user() weryfikuje kredencjały:
   ├─ admin/admin → create_session(..., is_authorized=True)
   └─ guest/guest → create_session(..., is_authorized=False)
4. Session tworzy UUID session_id
5. Zwraca JSON z session_id i is_authorized
6. JavaScript zapisuje session_id w localStorage
7. Przekierowuje do /streaming/video
```

### Faza 3: Streamowanie

```python
1. Strona /streaming/video renderuje HTML player'a
2. Player inicjalizuje stream z query parametrem:
   GET /streaming/video/stream?session_id=<UUID>
3. Serwer StreamingResponse zwraca generator:
   
   def stream_generator():
       for segment_id in [0, 1, 2, ..., 117]:
           segment_interval = (segment_id // 10) * 10
           
           # Wypisz rotację klucza co 10 segmentów
           if interwał się zmienił:
               print("ROTACJA KLUCZA")
           
           # Pobierz segment
           data, metadata = get_segment(session_id, segment_id)
           
           if data:
               yield data  # Prześlij audio/wideo
           else:
               # Błąd dostępu (guest)
               break
4. Player odbiera stream i wyświetla wideo
```

---

## Konta Testowe

| Nazwa użytkownika | Hasło | Dostęp | Opis |
|------------------|-------|--------|------|
| `admin` | `admin` | PEŁNY | Może oglądać całe wideo z decyzją danych |
| `guest` | `guest` | BRAK | Nie może oglądać - błąd dostępu |

---

## Instalacja i Uruchomienie

### Wymagania

- Python 3.8+
- FFmpeg (do segmentacji video)
- liboqs (Post-Quantum Cryptography library)

### Kroki Instalacji

#### 1. Zainstaluj liboqs (post-quantum library)

```bash
bash install.sh
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib
export OQS_INSTALL_PATH=/usr/local/lib  # lub twoja ścieżka
```

#### 2. Zainstaluj zależności Python

```bash
pip install -r req.txt
```

#### 3. Przygotuj plik video

Umieść plik `vid.webm` w głównym katalogu projektu.

#### 4. Uruchom aplikację

```bash
python main.py
```

lub bardziej prosto:

```bash
uvicorn main:app --reload
```

Aplikacja będzie dostępna pod adresem:
```
http://localhost:8000/
```

---

## Struktura Danych

### `.content_keys.json` (Mapa Kluczy)

```json
{
  "0": "base64_encoded_32_byte_aes_key",
  "10": "base64_encoded_32_byte_aes_key",
  "20": "base64_encoded_32_byte_aes_key",
  ...
}
```

Każdy klucz to losowe 32 bajty (256 bitów) w formacie base64.

### `vault.enc` (Zaszyfrowany Magazyn Kluczy)

```
[16 bajtów IV][N bajtów AES-256-CTR(JSON)]
```

Zawiera JSON:
```json
{
  "ml_dsa_private": "base64_private_key",
  ...
}
```

---

## Post-Quantum Cryptography (PQC) w Projekcie

### Dlaczego Post-Quantum?

Komputery kwantowe będą w stanie złamać dzisiejszą kryptografię (RSA, ECDSA). Projekt demonstruje jak się przygotować:

### Użyte Algorytmy PQC

| Algorytm | Typ | Standard | Funkcja |
|----------|-----|----------|---------|
| **Kyber768** | KEM | NIST PQC | Bezpieczna wymiana kluczy sesji AES |
| **ML-DSA-65** | Podpis | NIST PQC | Weryfikacja autentyczności tokenów |

### Implementacja

```python
import oqs

# Generowanie ML-DSA-65 keypair
with oqs.Signature("ML-DSA-65") as signer:
    public_key = signer.generate_keypair()
    secret_key = signer.export_secret_key()

# Podpisywanie wiadomości
with oqs.Signature("ML-DSA-65") as signer:
    signer.import_secret_key(secret_key)
    signature = signer.sign(message)

# Weryfikacja podpisu
with oqs.Signature("ML-DSA-65") as verifier:
    is_valid = verifier.verify(message, signature, public_key)
```

---

## Praktyczne Przykłady

### Przykład 1: Admin loguje się i oglądać wideo

```
1. admin → login z admin/admin
   Sesja autoryzowana
   Przydzielone AES-klucze do wszystkich interwałów

2. Player żąda segment 0
   → StreamingService pobiera segment_000.ts
   → Deszyfruje z kluczem[0]
   → Zwraca surowy H.264/AAC stream
   → Przeglądarka wyświetla wideo

3. Player żąda segment 10
   → Segment_010.ts
   → Rotacja! Teraz używamy klucza[10]
   → [Wydruk: ROTACJA KLUCZA]
   → Deszyfrowanie z klucza[10]
   → Odtwarzanie trwa
```

### Przykład 2: Guest próbuje oglądać wideo

```
1. guest → login z guest/guest
   Sesja NIEAUTORYZOWANA
   Brak przydzielonych kluczy

2. Player żąda segment 0
   → StreamingService sprawdza is_authorized
   → FALSE
   → Zwraca błąd: "Brak dostępu"
   → Gracz zatrzymuje się, wyświetla komunikat błędu
```

---

## Endpointy API

| Metoda | Ścieżka | Parametry | Opis |
|--------|--------|-----------|------|
| GET | `/` | - | Dashboard logowania (HTML) |
| POST | `/auth/login-user` | username, password | Autoryzacja użytkownika |
| GET | `/streaming/video` | session_id | Strona playera wideo |
| GET | `/streaming/video/stream` | session_id | Stream segmentów (binary) |
| GET | `/streaming/watermark` | session_id | Generuj token wodny |
| GET | `/streaming/session-info` | session_id | Informacje o sesji |

---

## Analiza Bezpieczeństwa

### Mocne Strony

- Post-Quantum Cryptography - Bezpieczeństwo przed atakami kwantowymi
- Rotacja Kluczy - Kompromitacja jednego klucza = max 10 segmentów zagrożone
- Autoryzacja na poziomie sesji - Użytkownicy bez uprawnień nie otrzymają kluczy
- Magazyn Kluczy - ML-DSA klucze przechowywane zaszyfrowane w vault.enc

### Potencjalne Ulepszenia

- Dynamiczne przydzielanie kluczy (zamiast wszystko na startup)
- Realne hasła zamiast hardkodowanych (admin/guest)
- Baza danych użytkowników (zamiast in-memory sessions)
- HTTPS/TLS (zamiast HTTP)
- Refresh tokenów i wygasanie sesji
- Rate limiting i protecja przed brute-force
- Auditowanie dostępu (logi kto co widział)

---

## Dokumentacja Bibliotek

- [FastAPI](https://fastapi.tiangolo.com/) - REST API framework
- [liboqs-python](https://github.com/open-quantum-safe/liboqs-python) - Post-Quantum Cryptography
- [cryptography](https://cryptography.io/) - AES, CTR mode
- [FFmpeg-python](https://github.com/kkroening/ffmpeg-python) - Video processing

---

## Wnioski

Projekt **PQC OTT** pokazuje praktyczne zastosowanie post-quantum cryptography w systemach przesyłania treści. Łączy nowoczesne algorytmy kryptograficzne z realną infrastrukturą OTT, tworząc system odporny na przyszłe ataki komputerów kwantowych.

**Klucze do Sukcesu:**
1. Rotacja kluczy zmniejsza powierzchnię ataku
2. Post-quantum podpisy (ML-DSA) zapewniają autentyczność
3. Kontrola dostępu na poziomie sesji chroni nieautoryzowanych użytkowników
4. AES-256 pozostaje bezpiecznym standardem dla szyfrowania contentu

---

## Kontakt i Wspólpraca

Projekt jest demonstracją edukacyjną post-quantum cryptography. Do użytku produkcyjnego wymagane są dodatkowe stwierdzenia bezpieczeństwa i audyty.

---

**Ostatnia aktualizacja:** Maj 2026
**Wersja:** 1.1
