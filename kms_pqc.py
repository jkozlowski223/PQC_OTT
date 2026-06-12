import os
import json
import base64
import oqs
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

class PQCReadyVault:
    def __init__(self, master_key: bytes):
        self.master_key = master_key
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
                    if encrypted:
                        vault_content = json.loads(self._decrypt_data(encrypted).decode())
            except (IOError, OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"[Vault] Ostrzeżenie: Nie można odczytać magazynu ({e}), uruchamianie od nowa")
                vault_content = {}
        
        vault_content[key_id] = base64.b64encode(key_data).decode()
        
        with open(self.vault_file, 'wb') as f:
            f.write(self._encrypt_data(json.dumps(vault_content).encode()))

class KMSServer:
    def __init__(self):
        self.vault = PQCReadyVault(os.urandom(32))
        self.kem_alg = "Kyber768" 
        self.sig_alg = "ML-DSA-65"
        with oqs.Signature(self.sig_alg) as signer:
            self.sig_public_key = signer.generate_keypair()
            self.sig_secret_key = signer.export_secret_key()
            self.vault.save_key("ml_dsa_private", self.sig_secret_key)

    def sign_token(self, payload: dict) -> str:
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
        try:
            token = json.loads(base64.b64decode(b64_token).decode())
            message = json.dumps(token["payload"]).encode()
            signature = base64.b64decode(token["signature"])
            
            with oqs.Signature(self.sig_alg) as verifier:
                return verifier.verify(message, signature, self.sig_public_key)
        except (ValueError, KeyError, UnicodeDecodeError, json.JSONDecodeError, Exception):
            return False

    def encapsulate_aes_key(self, client_kem_public_key: bytes):
        with oqs.KeyEncapsulation(self.kem_alg) as kem:
            ciphertext, shared_secret_aes_key = kem.encap_secret(client_kem_public_key)
            return ciphertext, shared_secret_aes_key[:32]