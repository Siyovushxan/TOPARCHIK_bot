import asyncio

# Agar Railway yoki boshqa muhit root. app.py ni ishga tushirsa,
# bu yerdan real botni chaqiramiz.
# Har doim `toparchik_bot/app.py` dagi main() ishlaydi.
try:
    from toparchik_bot.app import main
except Exception as e:
    raise RuntimeError("toparchik_bot.app modulini yuklab bo‘lmadi: %s" % e)

if __name__ == "__main__":
    asyncio.run(main())
