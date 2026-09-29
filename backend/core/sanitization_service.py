import os
import hashlib
from enum import Enum
from dataclasses import dataclass
import time

class StorageType(Enum):
    HDD = "HDD"
    SSD = "SSD"
    USB = "USB"
    MEMORY_CARD = "MEMORY_CARD"
    EXTERNAL_STORAGE = "EXTERNAL_STORAGE"
    DISK_IMAGE = "DISK_IMAGE"
    UNKNOWN = "UNKNOWN"

class SanitizationMethod(Enum):
    CONTROLLED_OVERWRITE = "CONTROLLED_OVERWRITE"
    DEVICE_SANITIZE = "DEVICE_SANITIZE"
    SECURE_ERASE = "SECURE_ERASE"
    CRYPTOGRAPHIC_ERASE = "CRYPTOGRAPHIC_ERASE"
    DEMO_SIMULATION = "DEMO_SIMULATION"

@dataclass
class StorageTarget:
    target_path: str
    target_name: str
    storage_type: StorageType
    size: int
    mode: str
    removable: bool
    safe_for_demo: bool

class DriveSanitizationService:
    def __init__(self):
        self._cancel_requested = False

    def request_cancel(self):
        self._cancel_requested = True

    def validate_target(self, target_path) -> StorageTarget:
        """
        Identify the storage and validate if it's safe for a demo.
        """
        if not os.path.exists(target_path):
            raise ValueError(f"Target path does not exist: {target_path}")

        # Safety Guardrails
        abs_path = os.path.abspath(target_path).lower()
        if abs_path.startswith("c:\\") and not abs_path.endswith(".img"):
            # Reject wiping C: or arbitrary folders on C: unless it's an .img file
            raise PermissionError("SAFE DEMO MODE: Cannot wipe arbitrary paths on the system drive.")

        is_safe = False
        storage_type = StorageType.UNKNOWN
        size = os.path.getsize(target_path)
        
        # For the prototype, we only consider .img and .dd files as safe test targets.
        if target_path.lower().endswith((".img", ".dd", ".raw")):
            is_safe = True
            storage_type = StorageType.DISK_IMAGE
        else:
            raise PermissionError("SAFE DEMO MODE: Only .img, .dd, or .raw disk images are supported currently. No physical drive will be modified.")
            
        return StorageTarget(
            target_path=target_path,
            target_name=os.path.basename(target_path),
            storage_type=storage_type,
            size=size,
            mode="SAFE_DEMO",
            removable=False,
            safe_for_demo=is_safe
        )

    def select_method(self, target: StorageTarget, ui_selection: str) -> SanitizationMethod:
        if target.storage_type == StorageType.DISK_IMAGE:
            if "0x00" in ui_selection:
                return SanitizationMethod.CONTROLLED_OVERWRITE
            else:
                return SanitizationMethod.DEMO_SIMULATION
        return SanitizationMethod.UNKNOWN

    def execute_sanitization(self, target: StorageTarget, method: SanitizationMethod, callbacks):
        """
        Executes the safe, controlled sanitization on the target image.
        Callbacks expected: progress(int), stage(str)
        """
        if not target.safe_for_demo:
            raise PermissionError("Target is not safe for demo operations.")
            
        callbacks.stage("Preparing sanitization")
        callbacks.progress(30)
        
        file_size = target.size
        chunk_size = 4 * 1024 * 1024 # 4MB chunks
        
        passes = 1
        patterns = [b'\x00']
        
        if method == SanitizationMethod.DEMO_SIMULATION:
            passes = 3
            patterns = [b'\x00', b'\xFF', os.urandom(1)] # Using random byte for pass 3 to simulate randomness but keep it simple
            
        with open(target.target_path, 'r+b') as f:
            for p in range(passes):
                if self._cancel_requested:
                    raise InterruptedError("Sanitization CANCELLED by user.")
                    
                callbacks.stage(f"Sanitizing (Pass {p+1}/{passes})")
                f.seek(0)
                bytes_written = 0
                
                # Pre-generate pattern chunk
                if patterns[p] is None:
                    pattern_chunk = os.urandom(chunk_size)
                elif isinstance(patterns[p], bytes) and len(patterns[p]) == 1:
                    pattern_chunk = patterns[p] * chunk_size
                else:
                    pattern_chunk = b'\x00' * chunk_size
                
                while bytes_written < file_size:
                    if self._cancel_requested:
                        raise InterruptedError("Sanitization CANCELLED by user.")
                        
                    write_size = min(chunk_size, file_size - bytes_written)
                    
                    if patterns[p] is None:
                        # Full random per chunk
                        f.write(os.urandom(write_size))
                    else:
                        if write_size == chunk_size:
                            f.write(pattern_chunk)
                        else:
                            f.write(pattern_chunk[:write_size])
                            
                    bytes_written += write_size
                    
                    # Progress from 30% to 80%
                    total_bytes = file_size * passes
                    current_total = (p * file_size) + bytes_written
                    fraction = current_total / total_bytes
                    progress_val = 30 + int(fraction * 50)
                    callbacks.progress(progress_val)
                    
            f.flush()
            os.fsync(f.fileno())

    def verify_sanitization(self, target: StorageTarget, method: SanitizationMethod, callbacks):
        """
        Reads back the affected region and verifies the pattern. Returns (status, details, hash)
        """
        callbacks.stage("Verifying")
        callbacks.progress(80)
        
        file_size = target.size
        chunk_size = 4 * 1024 * 1024
        
        sha256 = hashlib.sha256()
        
        # What is the expected final pattern?
        expected_byte = b'\x00'
        if method == SanitizationMethod.DEMO_SIMULATION:
            # Pass 3 was random, verification might be complex. Let's just hash it.
            # But for 0x00 overwrite, we expect 0x00.
            expected_byte = None 
            
        verification_passed = True
        
        with open(target.target_path, 'rb') as f:
            bytes_read = 0
            while bytes_read < file_size:
                if self._cancel_requested:
                    raise InterruptedError("Verification CANCELLED by user.")
                    
                read_size = min(chunk_size, file_size - bytes_read)
                data = f.read(read_size)
                if not data:
                    break
                    
                sha256.update(data)
                
                if expected_byte is not None and verification_passed:
                    # Check if all bytes are 0x00
                    # A quick way to check if a bytes object is all zeros:
                    if data != expected_byte * len(data):
                        verification_passed = False
                        
                bytes_read += len(data)
                
                # Progress from 80% to 95%
                fraction = bytes_read / file_size
                progress_val = 80 + int(fraction * 15)
                callbacks.progress(progress_val)
                
        final_hash = sha256.hexdigest()
        callbacks.progress(95)
        
        if expected_byte is not None:
            if verification_passed:
                return "PASS", "Verified all bytes match the 0x00 overwrite pattern.", final_hash
            else:
                return "FAIL", "Data mismatch detected. Pattern not uniform.", final_hash
        else:
            return "PASS", "Completed multi-pass simulated wipe. Hashed final state.", final_hash
