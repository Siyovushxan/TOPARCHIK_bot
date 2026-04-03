
# Agar Railway yoki boshqa muhit root app.py ni ishga tushirsa,
# faqat toparchik_bot.app modulini chaqiramiz (asosiy logika faqat bitta joyda bo'ladi)
try:
    from toparchik_bot.app import main
except Exception as e:
    raise RuntimeError("toparchik_bot.app modulini yuklab bo‘lmadi: %s" % e)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
