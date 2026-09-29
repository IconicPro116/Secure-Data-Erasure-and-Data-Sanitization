import os
import io
import zipfile
# pyrefly: ignore [missing-import]
from PIL import Image, ImageDraw, ImageFont

def create_valid_jpg():
    # Create an actual readable JPEG image with text
    img = Image.new('RGB', (600, 400), color=(24, 76, 120))
    d = ImageDraw.Draw(img)
    d.rectangle([(20, 20), (580, 380)], outline=(255, 255, 255), width=3)
    d.text((40, 160), "SecEra Digital Evidence [RECOVERED]", fill=(255, 255, 255))
    d.text((40, 200), "File: photo_01.jpg | Status: Valid & Authentic", fill=(180, 220, 255))
    d.text((40, 240), "Algorithm: C++ Raw Signature Carver + Python Scorer", fill=(180, 220, 255))
    
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=95)
    return buf.getvalue()

def create_valid_png():
    # Create an actual readable PNG image
    img = Image.new('RGB', (600, 400), color=(39, 110, 80))
    d = ImageDraw.Draw(img)
    d.rectangle([(20, 20), (580, 380)], outline=(255, 255, 255), width=3)
    d.text((40, 160), "SecEra Recovered Screenshot [PNG]", fill=(255, 255, 255))
    d.text((40, 200), "Hash Verified: SHA-256 Intact", fill=(200, 255, 200))
    d.text((40, 240), "Target Artifact: screenshot.png", fill=(200, 255, 200))
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

def create_valid_pdf():
    # Valid minimal PDF document with readable text
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog /Pages 2 0 R >>\n"
        b"endobj\n"
        b"2 0 obj\n"
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n"
        b"endobj\n"
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\n"
        b"endobj\n"
        b"4 0 obj\n"
        b"<< /Length 130 >>\n"
        b"stream\n"
        b"BT\n"
        b"/F1 22 Tf\n"
        b"50 700 Td\n"
        b"(SecEra Digital Forensics & File Recovery) Tj\n"
        b"/F1 14 Tf\n"
        b"0 -40 Td\n"
        b"(Status: Successfully recovered report.pdf) Tj\n"
        b"ET\n"
        b"endstream\n"
        b"endobj\n"
        b"5 0 obj\n"
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n"
        b"endobj\n"
        b"xref\n"
        b"0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000240 00000 n \n"
        b"0000000421 00000 n \n"
        b"trailer\n"
        b"<< /Size 6 /Root 1 0 R >>\n"
        b"startxref\n"
        b"503\n"
        b"%%EOF\n"
    )
    return pdf_content

def create_valid_docx():
    # Valid DOCX document structure (OpenXML Zip)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>'
        ))
        z.writestr('_rels/.rels', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>'
        ))
        z.writestr('word/document.xml', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body>'
            '<w:p><w:r><w:rPr><w:b/><w:sz w:val="36"/></w:rPr><w:t>SecEra Forensic Recovery Report</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>This DOCX document was successfully carved from the raw storage partition and reconstructed intact.</w:t></w:r></w:p>'
            '</w:body>'
            '</w:document>'
        ))
    return buf.getvalue()

def main():
    img_size = 50 * 1024 * 1024 # 50 MB
    
    os.makedirs('data', exist_ok=True)
    img_path = 'data/evidence_drive.img'
    
    print(f"Generating test image with authentic files: {img_path} ({img_size / 1024 / 1024} MB)")
    
    # Pre-fill with random noise / zeroes
    with open(img_path, 'wb') as f:
        # Use 0x00 and zeroes with some noise to realistically simulate an unallocated partition
        zero_block = b'\x00' * (1024 * 1024)
        for _ in range(50):
            f.write(zero_block)
        
    files_to_embed = [
        ("photo_01.jpg", create_valid_jpg()),
        ("screenshot.png", create_valid_png()),
        ("report.pdf", create_valid_pdf()),
        ("presentation.docx", create_valid_docx())
    ]
    
    # Embed files at specific offsets
    with open(img_path, 'r+b') as f:
        offsets = [
            1024 * 1024 * 5,   # 5 MB
            1024 * 1024 * 15,  # 15 MB
            1024 * 1024 * 25,  # 25 MB
            1024 * 1024 * 35   # 35 MB
        ]
        
        for i, (name, data) in enumerate(files_to_embed):
            offset = offsets[i]
            f.seek(offset)
            f.write(data)
            print(f"Embedded genuine {name} at offset {offset} (Size: {len(data)} bytes)")
            
    print("Done generating authentic test image.")

if __name__ == "__main__":
    main()
