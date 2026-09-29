import os
import subprocess
import json
import hashlib
import zipfile
import io

class RecoveryService:
    def __init__(self, c_engine_path="secera_carver.exe"):
        self.c_engine_path = c_engine_path

    def calculate_sha256(self, filepath):
        sha256_hash = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception:
            return "Hash calculation failed"

    def format_size(self, size_in_bytes):
        if size_in_bytes > 1024 * 1024:
            return f"{size_in_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_in_bytes / 1024:.1f} KB"

    def validate_file(self, filepath, file_type):
        """
        Validates the file structure and calculates a confidence score (0-100).
        """
        score = 0
        status = "Invalid"
        
        if not os.path.exists(filepath):
            return 0, "Invalid"
            
        file_size = os.path.getsize(filepath)
        if file_size == 0:
            return 0, "Invalid"

        try:
            with open(filepath, 'rb') as f:
                file_data = f.read(min(file_size, 1024 * 1024)) # read up to 1MB for validation
        except Exception:
            return 0, "Invalid"

        # 1. Size plausible (+15)
        if file_size > 300:
            score += 15
            
        # 2. File successfully saved (+10)
        score += 10

        # Signature detected (+40) and Footer found (+20) and Basic structure valid (+15)
        if file_type == 'JPG':
            if file_data.startswith(b'\xFF\xD8'):
                score += 40
            
            # Simple footer check
            with open(filepath, 'rb') as f:
                f.seek(max(0, file_size - 1024))
                tail = f.read()
                if b'\xFF\xD9' in tail:
                    score += 20
                    
            if b'\xFF\xC0' in file_data or b'\xFF\xC4' in file_data or b'\xFF\xDA' in file_data:
                score += 15

        elif file_type == 'PNG':
            if file_data.startswith(b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'):
                score += 40
                
            with open(filepath, 'rb') as f:
                f.seek(max(0, file_size - 1024))
                tail = f.read()
                if b'\x49\x45\x4E\x44' in tail:
                    score += 20
                    
            if b'IHDR' in file_data[:100]:
                score += 15

        elif file_type == 'PDF':
            if file_data.startswith(b'%PDF-'):
                score += 40
                
            with open(filepath, 'rb') as f:
                f.seek(max(0, file_size - 2048))
                tail = f.read()
                if b'%%EOF' in tail:
                    score += 20
                if b'trailer' in tail or b'xref' in tail:
                    score += 15

        elif file_type == 'DOCX':
            if file_data.startswith(b'\x50\x4B\x03\x04'):
                score += 40
            
            with open(filepath, 'rb') as f:
                f.seek(max(0, file_size - 1024))
                tail = f.read()
                if b'\x50\x4B\x05\x06' in tail:
                    score += 20
                    
            try:
                with zipfile.ZipFile(filepath) as zf:
                    namelist = zf.namelist()
                    if 'word/document.xml' in namelist or '[Content_Types].xml' in namelist:
                        score += 15
            except zipfile.BadZipFile:
                pass

        if score >= 90:
            status = "Valid"
        elif score >= 60:
            status = "Partially Valid"
        else:
            status = "Invalid"

        return min(100, score), status

    def run_recovery(self, image_path, output_dir, callback_progress=None, callback_file=None, callback_status=None):
        """
        Executes the C++ carving engine as a subprocess, reads JSON Lines from stdout,
        and yields normalized Python dictionaries or calls the respective callbacks.
        """
        if not os.path.exists(image_path):
            if callback_status:
                callback_status("Error: Input image not found")
            return

        os.makedirs(output_dir, exist_ok=True)
        
        if not os.path.exists(self.c_engine_path):
            # Fallback for testing or if not found
            candidate_paths = [
                self.c_engine_path,
                os.path.join(os.path.dirname(__file__), "..", "..", "cpp_engine", "secera_carver.exe"),
                os.path.join(os.path.dirname(__file__), "..", "..", "secera_carver.exe"),
            ]
            
            found = False
            for path in candidate_paths:
                if os.path.exists(path):
                    self.c_engine_path = path
                    found = True
                    break
                    
            if not found:
                if callback_status:
                    callback_status(f"Error: C++ Engine not found at {self.c_engine_path}")
                return

        if callback_status:
            callback_status(f"Scanning {os.path.basename(image_path)} using C++ engine...")

        try:
            # Launch C++ engine
            process = subprocess.Popen(
                [self.c_engine_path, image_path, output_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            total_found = 0
            
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    # Ignore non-JSON output
                    continue
                
                msg_type = data.get("type")
                
                if msg_type == "progress":
                    if callback_progress:
                        callback_progress(data.get("progress", 0))
                
                elif msg_type == "candidate":
                    file_path = data.get("output")
                    file_type = data.get("file_type")
                    size = data.get("size", 0)
                    offset = data.get("offset", 0)
                    
                    sha256 = self.calculate_sha256(file_path)
                    confidence_score, validation_status = self.validate_file(file_path, file_type)
                    
                    result_dict = {
                        "name": os.path.basename(file_path),
                        "type": file_type,
                        "size": self.format_size(size),
                        "offset": offset,
                        "confidence": f"{confidence_score}%",
                        "status": validation_status,
                        "sha256": sha256,
                        "path": os.path.abspath(file_path)
                    }
                    
                    if callback_file:
                        callback_file(result_dict)
                        
                elif msg_type == "complete":
                    total_found = data.get("files_found", 0)
                    break
            
            process.wait()
            
            if callback_progress:
                callback_progress(100)
                
            return total_found

        except Exception as e:
            if callback_status:
                callback_status(f"Error executing C++ engine: {str(e)}")
            return 0
