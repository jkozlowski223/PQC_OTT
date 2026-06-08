import os
import uuid
from datetime import datetime
from typing import Dict
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

class StreamingSession:
    def __init__(self, user_id: str, is_authorized: bool = False):
        self.user_id = user_id
        self.session_id = str(uuid.uuid4())
        self.is_authorized = is_authorized
        self.created_at = datetime.now()
        self.aes_keys = {}
        self.segments_downloaded = []
        
    def set_aes_keys(self, keys_map: dict):
        if self.is_authorized:
            self.aes_keys = keys_map
            return True
        return False

class StreamingService:
    def __init__(self, kms_server, video_processor):
        self.kms = kms_server
        self.video_proc = video_processor
        self.sessions: Dict[str, StreamingSession] = {}
        self._content_aes_keys: dict = None

    def set_content_keys(self, keys_map: dict):
        self._content_aes_keys = keys_map

    def create_session(self, user_id: str, is_authorized: bool = False) -> dict:
        session = StreamingSession(user_id, is_authorized)
        self.sessions[session.session_id] = session
        
        if is_authorized:
            if self._content_aes_keys is not None:
                session.set_aes_keys(self._content_aes_keys)
                print(f"[StreamingService] ✅ Sesja autoryzowana (Klucze przypisane): {session.session_id}")
            else:
                print(f"[StreamingService] ❌ Brak kluczy AES - startup nie ustawił rotacji!")
        else:
            print(f"[StreamingService] ⚠️ Sesja nieautoryzowana: {session.session_id}")
        
        return {
            "status": "success",
            "session_id": session.session_id,
            "user_id": user_id,
            "is_authorized": is_authorized,
            "created_at": session.created_at.isoformat()
        }
    
    def get_segment(self, session_id: str, segment_id: int, interval: int = 10) -> tuple:
        if session_id not in self.sessions:
            return None, {"error": "Sesja nie znaleziona"}
        
        session = self.sessions[session_id]
        segment_file = os.path.join("cdn_storage", f"segment_{segment_id:03d}.ts")
        if not os.path.exists(segment_file):
            return None, {"error": f"Segment {segment_id} nie istnieje"}
        
        try:
            with open(segment_file, 'rb') as f:
                segment_data = f.read()
        except Exception as e:
            return None, {"error": f"Błąd wczytywania segmentu: {e}"}
        
        if session.is_authorized:
            current_interval = (segment_id // interval) * interval
            aes_key = session.aes_keys.get(current_interval)
            
            if not aes_key:
                return None, {"error": "Brak rotacyjnego klucza AES dla tego segmentu!"}
                
            try:
                iv = segment_data[:16]
                ciphertext = segment_data[16:]
                cipher = Cipher(algorithms.AES(aes_key), modes.CTR(iv))
                decryptor = cipher.decryptor()
                decrypted = decryptor.update(ciphertext) + decryptor.finalize()
                
                session.segments_downloaded.append(segment_id)
                
                return decrypted, {
                    "status": "success",
                    "segment_id": segment_id,
                    "authorized": True,
                    "size": len(decrypted)
                }
            except Exception as e:
                return None, {"error": f"Dekrypcja nie udała się: {e}"}
        else:
            return None, {
                "error": "Brak dostępu do tego segmentu",
                "status": "access_denied",
                "authorized": False,
                "message": "Nie jesteś autoryzowanym użytkownikiem"
            }
    
    def get_encrypted_segment_chunked(self, session_id: str, segment_id: int, chunk_size: int = 8192):
        """Generator zwracający zaszyfrowany segment w chunks dla przeglądu szumu szyfrowania"""
        if session_id not in self.sessions:
            return
        
        segment_file = os.path.join("cdn_storage", f"segment_{segment_id:03d}.ts")
        if not os.path.exists(segment_file):
            return
        
        try:
            with open(segment_file, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except Exception as e:
            print(f"[StreamingService] ❌ Błąd czytania zaszyfrowanego segmentu {segment_id}: {e}")
    
    def get_available_segments(self) -> list:
        segment_files = [
            f for f in os.listdir("cdn_storage") 
            if f.startswith("segment_") and f.endswith(".ts")
        ]
        segment_ids = sorted([int(f.split("_")[1].split(".")[0]) for f in segment_files])
        return segment_ids
    
    def get_session_info(self, session_id: str) -> dict:
        if session_id not in self.sessions:
            return {"error": "Sesja nie znaleziona"}
        session = self.sessions[session_id]
        return {
            "session_id": session_id,
            "user_id": session.user_id,
            "is_authorized": session.is_authorized,
            "created_at": session.created_at.isoformat(),
            "segments_downloaded": len(session.segments_downloaded),
            "access_status": "✅ AUTORYZOWANY" if session.is_authorized else "❌ BRAK DOSTĘPU"
        }