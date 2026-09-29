import os
import random

def create_dummy_jpg(valid=True):
    header = b'\xFF\xD8\xFF\xE0\x00\x10\x4A\x46\x49\x46\x00\x01'
    footer = b'\xFF\xD9'
    body = os.urandom(1024 * 50) # 50 KB dummy body
    if valid:
        return header + body + footer
    return header + body # missing footer

def create_dummy_png(valid=True):
    header = b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'
    footer = b'\x49\x45\x4E\x44\xAE\x42\x60\x82'
    body = os.urandom(1024 * 80) # 80 KB
    if valid:
        return header + body + footer
    return header + body

def create_dummy_pdf(valid=True):
    header = b'%PDF-1.4\n'
    footer = b'\n%%EOF\n'
    body = b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n' + os.urandom(1024 * 30)
    if valid:
        return header + body + footer
    return header + body

def create_dummy_docx(valid=True):
    # DOCX is essentially a ZIP archive
    header = b'\x50\x4B\x03\x04\x14\x00\x06\x00\x08\x00\x00\x00\x21\x00'
    # Simplified end of central directory record
    footer = b'\x50\x4B\x05\x06' + b'\x00' * 18
    body = os.urandom(1024 * 120)
    if valid:
        return header + body + footer
    return header + body

def main():
    img_size = 5 * 1024 * 1024 # 5 MB
    img_path = 'evidence_drive.img'
    
    print(f"Generating test image: {img_path} ({img_size / 1024 / 1024} MB)")
    
    # Pre-fill with random noise to simulate a real drive
    with open(img_path, 'wb') as f:
        f.write(os.urandom(img_size))
        
    files_to_embed = [
        ("photo_01.jpg", create_dummy_jpg(valid=True)),
        ("photo_partial.jpg", create_dummy_jpg(valid=False)),
        ("screenshot.png", create_dummy_png(valid=True)),
        ("report.pdf", create_dummy_pdf(valid=True)),
        ("invoice_corrupt.pdf", create_dummy_pdf(valid=False)),
        ("presentation.docx", create_dummy_docx(valid=True))
    ]
    
    # Embed files at specific offsets
    with open(img_path, 'r+b') as f:
        offsets = [
            1024 * 100,             # 100 KB
            1024 * 800,             # 800 KB
            1024 * 1500,            # 1.5 MB
            1024 * 2400,            # 2.4 MB
            1024 * 3100,            # 3.1 MB
            1024 * 4000             # 4.0 MB
        ]
        
        for i, (name, data) in enumerate(files_to_embed):
            offset = offsets[i]
            f.seek(offset)
            f.write(data)
            print(f"Embedded {name} at offset {offset} (Size: {len(data)} bytes)")
            
    print("Done generating test image.")
    print("Please run this against the dashboard.")

if __name__ == "__main__":
    main()
