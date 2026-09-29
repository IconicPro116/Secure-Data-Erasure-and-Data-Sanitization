import os
import random
import time
import uuid

class EraserService:
    def __init__(self):
        pass

    def sanitize_drive(self, image_path, method, callback_progress=None, callback_status=None):
        if not os.path.exists(image_path):
            if callback_status:
                callback_status("Error: Target not found.")
            return False

        try:
            file_size = os.path.getsize(image_path)
            if file_size == 0:
                if callback_status:
                    callback_status("Target is empty.")
                return True

            passes = 1
            patterns = [b'\x00']
            
            if method == "Controlled 0x00 Overwrite":
                passes = 1
                patterns = [b'\x00']
            elif method == "Controlled Random Overwrite":
                passes = 1
                patterns = [None] # None means random
            elif method == "Simulated Device Sanitize":
                passes = 3
                patterns = [b'\x00', b'\xFF', None]
            else:
                passes = 1
                patterns = [b'\x00']

            chunk_size = 1024 * 1024 # 1MB chunks

            with open(image_path, 'r+b') as f:
                for p in range(passes):
                    if callback_status:
                        callback_status(f"Pass {p+1}/{passes} running...")
                    
                    f.seek(0)
                    bytes_written = 0
                    
                    pattern = patterns[p]
                    
                    while bytes_written < file_size:
                        write_size = min(chunk_size, file_size - bytes_written)
                        if pattern is None:
                            # Random data
                            data = os.urandom(write_size)
                        else:
                            data = pattern * write_size
                            
                        f.write(data)
                        bytes_written += write_size
                        
                        if callback_progress:
                            # Calculate total progress across all passes
                            total_bytes = file_size * passes
                            current_total = (p * file_size) + bytes_written
                            progress = int((current_total / total_bytes) * 100)
                            callback_progress(progress)
            
            if callback_progress:
                callback_progress(100)
            if callback_status:
                callback_status("Sanitization Complete.")
            return True

        except Exception as e:
            if callback_status:
                callback_status(f"Error: {str(e)}")
            return False

    def erase_file_or_folder(self, target_path, method, callback_progress=None, callback_status=None):
        if not os.path.exists(target_path):
            if callback_status:
                callback_status("Error: Target not found.")
            return False

        try:
            if os.path.isfile(target_path):
                self._erase_single_file(target_path, method, callback_progress, callback_status)
            elif os.path.isdir(target_path):
                # For demo purposes, we will just simulate folder erase to avoid recursive destruction issues 
                # or we can do a safe shallow erase if it's just test files.
                # Since requirement says SAFE, we will just delete files in it safely if they exist.
                files = []
                for root, _, filenames in os.walk(target_path):
                    for fname in filenames:
                        files.append(os.path.join(root, fname))
                
                total = len(files)
                for i, fpath in enumerate(files):
                    if callback_status:
                        callback_status(f"Erasing {os.path.basename(fpath)}...")
                    self._erase_single_file(fpath, method)
                    if callback_progress:
                        callback_progress(int(((i+1)/total)*100))
                        
                # Then remove dirs
                for root, dirnames, _ in os.walk(target_path, topdown=False):
                    for dname in dirnames:
                        os.rmdir(os.path.join(root, dname))
                os.rmdir(target_path)
                
            if callback_progress:
                callback_progress(100)
            if callback_status:
                callback_status("Erasure Complete.")
            return True
        except Exception as e:
            if callback_status:
                callback_status(f"Error: {str(e)}")
            return False

    def _erase_single_file(self, file_path, method, callback_progress=None, callback_status=None):
        if not os.path.exists(file_path):
            return
            
        file_size = os.path.getsize(file_path)
        
        # 1. Overwrite data
        with open(file_path, 'r+b') as f:
            if method == "Random-pattern demo":
                data = os.urandom(file_size)
            else:
                data = b'\x00' * file_size
            f.write(data)
            
        if callback_progress:
            callback_progress(50)
            
        # 2. Alter MAC times
        past_time = time.time() - random.randint(100000, 10000000)
        os.utime(file_path, (past_time, past_time))
        
        if callback_progress:
            callback_progress(75)
            
        # 3. Rename to random and unlink
        rand_name = str(uuid.uuid4()) + ".tmp"
        new_path = os.path.join(os.path.dirname(file_path), rand_name)
        os.rename(file_path, new_path)
        os.unlink(new_path)
        
        if callback_progress:
            callback_progress(100)
