import os
import time
import zipfile
import io
from PySide6.QtCore import QThread, Signal

class CarvingEngine(QThread):
    progress_updated = Signal(int)
    file_recovered = Signal(dict)
    scan_completed = Signal(int, int) # total found, total valid
    scan_status = Signal(str)

    SIGNATURES = {
        'JPG': {
            'header': b'\xFF\xD8\xFF\xE0',
            'footer': b'\xFF\xD9',
            'ext': '.jpg',
            'max_size': 5 * 1024 * 1024 # 5 MB
        },
        'PNG': {
            'header': b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A',
            'footer': b'\x49\x45\x4E\x44\xAE\x42\x60\x82',
            'ext': '.png',
            'max_size': 5 * 1024 * 1024
        },
        'PDF': {
            'header': b'%PDF-1.',
            'footer': b'%%EOF',
            'ext': '.pdf',
            'max_size': 10 * 1024 * 1024
        },
        'DOCX': {
            'header': b'\x50\x4B\x03\x04',
            'footer': b'\x50\x4B\x05\x06', # end of central directory
            'ext': '.docx',
            'max_size': 10 * 1024 * 1024
        }
    }

    def __init__(self, target_file, output_dir="recovery_output"):
        super().__init__()
        self.target_file = target_file
        self.output_dir = output_dir
        self.is_running = True
        
    def run(self):
        if not os.path.exists(self.target_file):
            self.scan_status.emit("Error: Target file not found")
            return

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        file_size = os.path.getsize(self.target_file)
        bytes_processed = 0
        files_found = 0
        valid_files = 0
        
        chunk_size = 1024 * 1024 # 1 MB chunk for scanning
        
        self.scan_status.emit(f"Scanning {os.path.basename(self.target_file)}...")
        
        with open(self.target_file, 'rb') as f:
            while self.is_running and bytes_processed < file_size:
                # Read a chunk, plus some overlap to avoid missing signatures at chunk boundaries
                overlap = max(len(sig['header']) for sig in self.SIGNATURES.values())
                f.seek(bytes_processed)
                chunk = f.read(chunk_size + overlap)
                if not chunk:
                    break

                # Scan for signatures in this chunk
                for ftype, sig_data in self.SIGNATURES.items():
                    header = sig_data['header']
                    start_idx = 0
                    while True:
                        idx = chunk.find(header, start_idx)
                        if idx == -1:
                            break
                            
                        # Found a header! Calculate absolute offset
                        absolute_offset = bytes_processed + idx
                        
                        # Now try to extract the file
                        f.seek(absolute_offset)
                        # Read up to max_size to find footer
                        potential_data = f.read(sig_data['max_size'])
                        
                        footer = sig_data['footer']
                        footer_idx = potential_data.find(footer)
                        
                        validation_status = "Invalid"
                        confidence = 0
                        extracted_size = 0
                        
                        if footer_idx != -1:
                            # Found footer
                            extracted_size = footer_idx + len(footer)
                            # Additional check for DOCX (ZIP end of central dir is actually 22 bytes min)
                            if ftype == 'DOCX':
                                extracted_size += 18 # Add the rest of the EOCD record
                                
                            file_data = potential_data[:extracted_size]
                            has_footer = True
                        else:
                            # No footer found, extract a fixed chunk for partial recovery
                            extracted_size = min(len(potential_data), 1024 * 100) # 100 KB partial
                            file_data = potential_data[:extracted_size]
                            has_footer = False
                            
                        # Phase 2 & 3: Meaningful Confidence Scoring and Validation
                        confidence, validation_status = self.validate_file(ftype, file_data, has_footer)
                        
                        if validation_status == "Valid":
                            valid_files += 1
                            
                        # Save the carved file
                        files_found += 1
                        out_name = f"recovered_{files_found:03d}_{ftype}{sig_data['ext']}"
                        out_path = os.path.join(self.output_dir, out_name)
                        
                        with open(out_path, 'wb') as out_f:
                            out_f.write(file_data)
                            
                        # Size string
                        if extracted_size > 1024 * 1024:
                            size_str = f"{extracted_size / (1024 * 1024):.1f} MB"
                        else:
                            size_str = f"{extracted_size / 1024:.1f} KB"
                            
                        # Emit result
                        self.file_recovered.emit({
                            "name": out_name,
                            "type": ftype,
                            "size": size_str,
                            "confidence": f"{confidence}%",
                            "status": validation_status,
                            "path": os.path.abspath(out_path)
                        })
                        
                        # Advance start_idx past this header to find others
                        start_idx = idx + 1
                        
                bytes_processed += chunk_size
                progress = int((min(bytes_processed, file_size) / file_size) * 100)
                self.progress_updated.emit(progress)
                
                # Small sleep to allow UI to update and simulate intensive process
                time.sleep(0.05)
                
        self.progress_updated.emit(100)
        self.scan_completed.emit(files_found, valid_files)
        
    def stop(self):
        self.is_running = False

    def validate_file(self, ftype, file_data, has_footer):
        score = 0
        
        # 1. Header detected (+20) -> If we are here, carving engine found the header
        score += 20
        
        # 2. Footer detected (+20)
        if has_footer:
            score += 20
            
        # 3. Expected structure (+20) & 4. Valid file parsing (+30)
        structure_score = 0
        parsing_score = 0
        
        if ftype == 'DOCX':
            # DOCX is a ZIP. Try parsing it.
            try:
                with zipfile.ZipFile(io.BytesIO(file_data)) as zf:
                    structure_score = 20
                    # Check if standard word contents exist
                    if 'word/document.xml' in zf.namelist() or '[Content_Types].xml' in zf.namelist():
                        parsing_score = 30
                    else:
                        parsing_score = 10
            except zipfile.BadZipFile:
                structure_score = 0
                parsing_score = 0
        
        elif ftype == 'PNG':
            if file_data.startswith(b'\x89PNG\r\n\x1a\n'):
                structure_score = 20
                if b'IHDR' in file_data[:100]:
                    parsing_score += 15
                if b'IEND' in file_data[-100:]:
                    parsing_score += 15
                    
        elif ftype == 'JPG':
            if file_data.startswith(b'\xFF\xD8'):
                structure_score = 20
                # Look for common JPEG markers (e.g. SOF0, DHT, SOS)
                if b'\xFF\xC0' in file_data or b'\xFF\xC4' in file_data or b'\xFF\xDA' in file_data:
                    parsing_score = 30
                    
        elif ftype == 'PDF':
            if file_data.startswith(b'%PDF-'):
                structure_score = 20
                # Look for trailer / xref in the last portion
                tail = file_data[-2048:]
                if b'trailer' in tail or b'xref' in tail or b'%%EOF' in tail:
                    parsing_score = 30

        score += structure_score
        score += parsing_score
        
        # 5. Size consistency (+10)
        # Check if the extracted size is somewhat plausible (e.g., > 1KB and not just a fragment)
        if len(file_data) > 1024:
            score += 10
            
        # Determine classification
        if score >= 90:
            status = "Valid"
        elif score >= 60:
            status = "Partially Valid"
        else:
            status = "Invalid"
            
        return score, status
