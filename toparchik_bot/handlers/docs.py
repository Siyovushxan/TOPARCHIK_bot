import os
import logging
from aiogram import Router, types, F
from aiogram.types import FSInputFile

from toparchik_bot import config
from toparchik_bot.services.docs import convert_pdf_to_docx, convert_docx_to_pdf, run_conversion

logger = logging.getLogger(__name__)
router = Router()

PROMO_TEXT = "\n\n🔥 <i>Eng sara musiqalar va aqlli AI xizmatlari: @toparchik_bot</i>"
MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


@router.message(F.text == "📄 Word<->Pdf")
async def docs_menu(message: types.Message):
    await message.answer(
        "<b>📄 Hujjatlarni konvertatsiya qilish:</b>\n\n"
        "Bot yordamida fayllarni tezkor aylantiring:\n"
        "✅ <b>PDF to Word:</b> PDF faylni botga yuboring.\n"
        "✅ <b>Word to PDF:</b> .docx faylni botga yuboring.\n\n"
        f"⚠️ <i>Eslatma: Fayllar hajmi {MAX_FILE_SIZE_MB} MB dan oshmasligi tavsiya etiladi.</i>" + PROMO_TEXT,
        parse_mode="HTML"
    )


@router.message(F.document)
async def handle_document(message: types.Message):
    doc = message.document
    file_name = (doc.file_name or "document").lower()

    # Fayl hajmini tekshirish
    if doc.file_size and doc.file_size > MAX_FILE_SIZE_BYTES:
        size_mb = doc.file_size / (1024 * 1024)
        await message.answer(
            f"❌ Fayl hajmi juda katta: <b>{size_mb:.1f} MB</b>.\n"
            f"Maksimal ruxsat etilgan hajm: <b>{MAX_FILE_SIZE_MB} MB</b>.",
            parse_mode="HTML"
        )
        return

    if file_name.endswith('.pdf'):
        wait_msg = await message.answer("⏳ PDF Word'ga aylantirilmoqda...")
        file = await message.bot.get_file(doc.file_id)
        input_path = os.path.join(config.DOWNLOAD_DIR, doc.file_name or "input.pdf")
        await message.bot.download_file(file.file_path, input_path)

        output_path = None
        try:
            output_path = await run_conversion(convert_pdf_to_docx, input_path)
            doc_file = FSInputFile(output_path)
            await message.answer_document(
                doc_file,
                caption=f"✅ Word fayl tayyor! {PROMO_TEXT}",
                parse_mode="HTML"
            )
        except Exception as exc:
            logger.error(f"PDF->DOCX xato: {exc}")
            await message.answer(f"❌ Konvertatsiyada xatolik: {exc}")
        finally:
            if os.path.exists(input_path):
                os.remove(input_path)
            if output_path and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass
            await wait_msg.delete()

    elif file_name.endswith('.docx'):
        wait_msg = await message.answer("⏳ Word PDF'ga aylantirilmoqda...")
        file = await message.bot.get_file(doc.file_id)
        input_path = os.path.join(config.DOWNLOAD_DIR, doc.file_name or "input.docx")
        await message.bot.download_file(file.file_path, input_path)

        output_path = None
        try:
            output_path = await run_conversion(convert_docx_to_pdf, input_path)
            pdf_file = FSInputFile(output_path)
            await message.answer_document(
                pdf_file,
                caption=f"✅ PDF fayl tayyor! {PROMO_TEXT}",
                parse_mode="HTML"
            )
        except Exception as exc:
            logger.error(f"DOCX->PDF xato: {exc}")
            await message.answer(f"❌ Konvertatsiyada xatolik: {exc}")
        finally:
            if os.path.exists(input_path):
                os.remove(input_path)
            if output_path and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass
            await wait_msg.delete()

    elif file_name.endswith('.doc'):
        # Eski .doc format python-docx bilan ishlamaydi
        await message.answer(
            "⚠️ <b>Eski Word formati (.doc) qo'llab-quvvatlanmaydi.</b>\n\n"
            "Iltimos, faylingizni <b>.docx</b> formatiga aylantirib qayta yuboring.\n"
            "<i>Bu amalni Microsoft Word yoki LibreOffice orqali amalga oshirishingiz mumkin.</i>" + PROMO_TEXT,
            parse_mode="HTML"
        )

    else:
        await message.answer(
            "🛑 Faqat <b>PDF</b> yoki <b>Word (.docx)</b> fayllarni yuboring." + PROMO_TEXT,
            parse_mode="HTML"
        )
