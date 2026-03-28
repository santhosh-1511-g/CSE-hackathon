from fpdf import FPDF
import io

try:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('helvetica', 'B', 16)
    pdf.cell(40, 10, 'Hello World!')
    out = pdf.output(dest='S')
    print(f"PDF generated successfully, size: {len(out)} bytes")
except Exception as e:
    print(f"PDF Generation Failed: {e}")
