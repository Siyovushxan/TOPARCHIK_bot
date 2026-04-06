import os
import logging
from aiogram import Router, types, F
from aiogram.types import FSInputFile

from toparchik_bot.services.docs import convert_pdf_to_docx, convert_docx_to_pdf, run_conversion

logger = logging.getLogger(__name__)
router = Router()

PROMO_TEXT = "\n\n🔥 <i>Eng sara musiqalar va aqlli AI xizmatlari: @toparchik_bot</i>"

@router.message(F.text == "📄 Word<->Pdf")
async def docs_menu(message: types.Message):
    await message.answer(
        "<b>📄 Hujjatlarni konvertatsiya qilish:</b>\n\n"
        "Bot yordamida fayllarni tezkor aylantiring:\n"
        "✅ <b>PDF to Word:</b> PDF faylni botga yuboring.\n"
        "✅ <b>Word to PDF:</b> .docx faylni botga yuboring.\n\n"
        "⚠️ <i>Eslatma: Fayllar hajmi 20 MB dan oshmasligi tavsiya etiladi.</i>" + PROMO_TEXT,
        parse_mode="HTML"
    )

@router.message(F.document)
async def handle_document(message: types.Message):
    file_name = message.document.file_name.lower() if message.document.file_name else "document"
    
    if file_name.endswith('.pdf'):
        wait_msg = await message.answer("⏳ PDF Word'ga aylantirilmoqda...")
        file_id = message.document.file_id
        file = await message.bot.get_file(file_id)
        input_path = f"downloads/{message.document.file_name}"
        await message.bot.download_file(file.file_path, input_path)
        
        try:
            output_path = await run_conversion(convert_pdf_to_docx, input_path)
            doc_file = FSInputFile(output_path)
            await message.answer_document(doc_file, caption=f"✅ Word fayl tayyor! {PROMO_TEXT}", parse_mode="HTML")
        except Exception as exc:
            await message.answer(f"❌ Xatolik yuz berdi: {exc}")
        finally:
            if os.path.exists(input_path): os.remove(input_path)
            if 'output_path' in locals() and os.path.exists(output_path): 
                try: os.remove(output_path) 
                except: pass
            await wait_msg.delete()
            
    elif file_name.endswith(('.docx', '.doc')):
        wait_msg = await message.answer("⏳ Word PDF'ga aylantirilmoqda...")
        file_id = message.document.file_id
        file = await message.bot.get_file(file_id)
        input_path = f"downloads/{message.document.file_name}"
        await message.bot.download_file(file.file_path, input_path)
        
        try:
            output_path = await run_conversion(convert_docx_to_pdf, input_path)
            pdf_file = FSInputFile(output_path)
            await message.answer_document(pdf_file, caption=f"✅ PDF fayl tayyor! {PROMO_TEXT}", parse_mode="HTML")
        except Exception as exc:
            await message.answer(f"❌ Xatolik yuz berdi: {exc}")
        finally:
            if os.path.exists(input_path): os.remove(input_path)
            if 'output_path' in locals() and os.path.exists(output_path): 
                try: os.remove(output_path) 
                except: pass
            await wait_msg.delete()
            
    else:
        await message.answer("🛑 Faqat PDF yoki Word (.doc, .docx) fayllarni yuboring." + PROMO_TEXT, parse_mode="HTML")
