import os
import subprocess
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

class VideoProcessor:
    def __init__(self, input_file: str, output_dir: str):
        self.input_file = input_file
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def segment_video(self):
        print("[VideoProcessor] Transkodowanie i cięcie wideo na równe segmenty...")
        segment_pattern = os.path.join(self.output_dir, "segment_%03d.ts")
        m3u8_file = os.path.join(self.output_dir, "playlist.m3u8")
        
        cmd = [
            "ffmpeg", "-y", "-i", self.input_file,
            "-c:v", "libx264", "-preset", "ultrafast", 
            "-c:a", "aac",
            "-force_key_frames", "expr:gte(t,n_forced*5)",
            "-f", "segment",
            "-segment_time", "5",
            "-segment_list", m3u8_file,
            segment_pattern
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            print("[VideoProcessor] Cięcie zakończone sukcesem.")
        except subprocess.CalledProcessError as e:
            print(f"[VideoProcessor] Błąd FFmpeg podczas cięcia wideo: {e}")
            if e.stderr:
                print(f"[VideoProcessor] FFmpeg stderr: {e.stderr.strip()}")

    def encrypt_segments(self, keys_map: dict, interval: int = 10):
        print(f"[VideoProcessor] Szyfrowanie segmentów wideo. Rotacja AES-256 co {interval} segmentów...")
        
        for filename in sorted(os.listdir(self.output_dir)):
            if not filename.endswith(".ts"):
                continue

            filepath = os.path.join(self.output_dir, filename)
            seg_idx = int(filename.split("_")[1].split(".")[0])
            current_interval = (seg_idx // interval) * interval
            aes_key = keys_map.get(current_interval)
            if not aes_key:
                aes_key = keys_map[0]

            with open(filepath, "rb") as f:
                data = f.read()

            iv = os.urandom(16)
            cipher = Cipher(algorithms.AES(aes_key), modes.CTR(iv))
            encryptor = cipher.encryptor()
            encrypted_data = encryptor.update(data) + encryptor.finalize()

            with open(filepath, "wb") as f:
                f.write(iv + encrypted_data)
                    
        print("[VideoProcessor] Szyfrowanie zakończone.")