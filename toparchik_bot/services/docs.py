import os
import tempfile
import asyncio
from pdf2docx import Converter

def convert_pdf_to_docx(pdf_path: str) -> str:
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    docx_path = os.path.join(tempfile.gettempdir(), f"{base_name}.docx")
    cv = Converter(pdf_path)
    cv.convert(docx_path)
    cv.close()
    return docx_path

def convert_docx_to_pdf(docx_path: str) -> str:
    base_name = os.path.splitext(os.path.basename(docx_path))[0]
    pdf_path = os.path.join(tempfile.gettempdir(), f"{base_name}.pdf")
    
    if os.name == 'nt':
        # Windows OS
        try:
            from docx2pdf import convert
            convert(docx_path, pdf_path)
        except Exception as exc:
            raise Exception(f"Kompyuteringizda Microsoft Word dasturi topilmadi yoki litsenziya muammosi bor: {exc}")
    else:
        # Linux OS (HuggingFace Spaces)
        import subprocess
        try:
            subprocess.run([
                "libreoffice", "--headless", "--convert-to", "pdf",
                docx_path, "--outdir", tempfile.gettempdir()
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            raise Exception("Linux serverda LibreOffice topilmadi. Iltimos server (yoki HF) da libreoffice paketini o'rnating.")
            
    if not os.path.exists(pdf_path):
        raise Exception("Noma'lum xato. Fayl yaratilmadi.")
        
    return pdf_path

async def run_conversion(fn, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn, *args)
