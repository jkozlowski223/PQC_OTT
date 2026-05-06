import os
import json
import base64
import oqs
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

class PQCReadyVault:
    def __init__(self, master_key: bytes):
        self.master_key = master_key # Klucz AES-256 do szyfrowania bazy "at rest"
        self.vault_file = "vault.enc"

    def _encrypt_data(self, data: bytes) -> bytes:
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(self.master_key), modes.CTR(iv))
        encryptor = cipher.encryptor()
        return iv + encryptor.update(data) + encryptor.finalize()

    def _decrypt_data(self, encrypted_data: bytes) -> bytes:
        iv = encrypted_data[:16]
        cipher = Cipher(algorithms.AES(self.master_key), modes.CTR(iv))
        decryptor = cipher.decryptor()
        return decryptor.update(encrypted_data[16:]) + decryptor.finalize()

    def save_key(self, key_id: str, key_data: bytes):
        vault_content = {}
        if os.path.exists(self.vault_file):
            try:
                with open(self.vault_file, 'rb') as f:
                    encrypted = f.read()
                    if encrypted:  # Only decrypt if file has content
                        vault_content = json.loads(self._decrypt_data(encrypted).decode())
            except Exception as e:
                # If decryption fails, start fresh
                print(f"[Vault] Warning: Could not read vault ({e}), starting fresh")
                vault_content = {}
        
        vault_content[key_id] = base64.b64encode(key_data).decode()
        
        with open(self.vault_file, 'wb') as f:
            f.write(self._encrypt_data(json.dumps(vault_content).encode()))

class KMSServer:
    def __init__(self):
        # Symulacja głównego klucza zabezpieczającego serwer
        self.vault = PQCReadyVault(os.urandom(32))
        
        # Algorytmy postkwantowe
        # UWAGA: W zależności od wersji liboqs, nazwy mogą to być np. "Kyber768" i "Dilithium3"
        self.kem_alg = "Kyber768" 
        self.sig_alg = "ML-DSA-65"
        
        # Generowanie pary kluczy do podpisów ML-DSA (Dilithium)
        with oqs.Signature(self.sig_alg) as signer:
            self.sig_public_key = signer.generate_keypair()
            self.sig_secret_key = signer.export_secret_key()
            # Bezpieczne przechowywanie klucza prywatnego w PQC-Ready Vault
            self.vault.save_key("ml_dsa_private", self.sig_secret_key)

    def sign_token(self, payload: dict) -> str:
        """Podpisywanie krótkotrwałych tokenów dostępu algorytmem ML-DSA[cite: 1]"""
        message = json.dumps(payload).encode()
        with oqs.Signature(self.sig_alg) as signer:
            signer.import_secret_key(self.sig_secret_key)
            signature = signer.sign(message)
        
        token = {
            "payload": payload,
            "signature": base64.b64encode(signature).decode()
        }
        return base64.b64encode(json.dumps(token).encode()).decode()

    def verify_token(self, b64_token: str) -> bool:
        """Weryfikacja podpisów w systemie kontroli dostępu[cite: 1]"""
        try:
            token = json.loads(base64.b64decode(b64_token).decode())
            message = json.dumps(token["payload"]).encode()
            signature = base64.b64decode(token["signature"])
            
            with oqs.Signature(self.sig_alg) as verifier:
                return verifier.verify(message, signature, self.sig_public_key)
        except Exception:
            return False

    def encapsulate_aes_key(self, client_kem_public_key: bytes):
        """Enkapsulacja kluczy sesyjnych AES z wykorzystaniem ML-KEM[cite: 1]"""
        with oqs.KeyEncapsulation(self.kem_alg) as kem:
            # Tworzy zaszyfrowaną paczkę (ciphertext) i współdzielony sekret (klucz sesyjny)
            ciphertext, shared_secret_aes_key = kem.encap_secret(client_kem_public_key)
            
            # shared_secret_aes_key posłuży jako klucz AES-256 dla Grupy 1
            # Zwracamy ciphertext, który klient zdekoduje u siebie[cite: 1]
            return ciphertext, shared_secret_aes_key[:32] # AES-256 wymaga 32 bajtów