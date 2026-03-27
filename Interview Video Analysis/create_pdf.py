from fpdf import FPDF
pdf = FPDF()
pdf.add_page()
pdf.set_font("Arial", size=12)
pdf.cell(200, 10, txt="Candidate: Test User", ln=1, align='C')
pdf.cell(200, 10, txt="Skills: Python, Javascript, Flask, React", ln=2, align='L')
pdf.output("e:/CSE-hackathon/Interview Video Analysis/test_resume.pdf")
print("PDF created successfully at e:/CSE-hackathon/Interview Video Analysis/test_resume.pdf")
