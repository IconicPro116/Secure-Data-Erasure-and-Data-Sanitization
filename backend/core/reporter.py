import os
import hashlib
from datetime import datetime
import json

class ReportService:
    def __init__(self, output_dir="reports"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def generate_report(self, audit_records):
        """
        Generates a forensic/sanitization report.
        For P0, we generate a structured text report (or HTML) and hash it.
        We can use HTML for better presentation in a browser/viewer.
        """
        if not audit_records:
            return None
            
        latest_record = audit_records[-1]
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"SecEra_AuditReport_{timestamp_str}.html"
        report_path = os.path.join(self.output_dir, report_filename)
        
        html_content = f"""
        <html>
        <head>
            <title>SecEra Forensic & Sanitization Report</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; color: #333; }}
                h1 {{ color: #0F1F36; border-bottom: 2px solid #2F80ED; padding-bottom: 10px; }}
                h2 {{ color: #2F80ED; margin-top: 30px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #F4F7FB; color: #0F1F36; }}
                .meta {{ background: #f9f9f9; padding: 15px; border-radius: 5px; margin-bottom: 20px; border-left: 4px solid #2F80ED; }}
                .footer {{ margin-top: 50px; font-size: 12px; color: #777; text-align: center; border-top: 1px solid #ddd; padding-top: 20px; }}
            </style>
        </head>
        <body>
            <h1>SecEra Audit & Integrity Report</h1>
            
            <div class="meta">
                <p><strong>Generated on:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                <p><strong>System Status:</strong> VERIFIED PROTOTYPE</p>
                <p><strong>Latest Operation:</strong> {latest_record.get('operation', 'N/A')}</p>
            </div>

            <h2>Operation Log History</h2>
            <table>
                <tr>
                    <th>Timestamp</th>
                    <th>Operation</th>
                    <th>Target</th>
                    <th>Method</th>
                    <th>Result</th>
                </tr>
        """
        
        for record in reversed(audit_records):
            html_content += f"""
                <tr>
                    <td>{record.get('timestamp', '')}</td>
                    <td>{record.get('operation', '')}</td>
                    <td>{record.get('target', '')}</td>
                    <td>{record.get('method', '')}</td>
                    <td>{record.get('result', '')}</td>
                </tr>
            """
            
        html_content += """
            </table>
            
            <div class="footer">
                SecEra Digital Forensics & Data Sanitization Platform &copy; 2026<br>
                <em>This report is cryptographically hashed to ensure tamper evidence.</em>
            </div>
        </body>
        </html>
        """
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        # Calculate SHA-256 of the report for integrity
        sha256_hash = hashlib.sha256()
        with open(report_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
                
        report_hash = sha256_hash.hexdigest()
        
        return report_path, report_hash
