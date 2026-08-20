# راهنمای جامع پروژه TERMUX-ART

این ابزار برای تفکیک لایه‌های رنگی تصویر، ادغام و خروجی گرفتن جهت کارهای چاپ و گرافیک در ترموکس استفاده می‌شود.

---

پیش‌نیازها و ساخت دایرکتوری در حافظه داخلی:

برای ساخت دایرکتوری کاری در حافظه گوشی و نصب ابزارهای مورد نیاز، دستورات زیر را اجرا کنید:

mkdir -p /sdcard/termux-art/layers
cd /sdcard/termux-art
pkg update && pkg install -y python git termux-api
pip install pillow numpy

---

دریافت و دانلود مستقیم اسکریپت:

لینک مستقیم دانلود فایل اسکریپت:
https://raw.githubusercontent.com/abrasion110/-/main/termux-art/dto-interactive.py

دستور دریافت مستقیم فایل:
curl -O https://raw.githubusercontent.com/abrasion110/-/main/termux-art/dto-interactive.py

---

نحوه اجرا:

۱. تصویر مورد نظر خود را با نام image.png در مسیر /sdcard/termux-art/image.png قرار دهید.
۲. اسکریپت را اجرا کنید:

python termux-art/dto-interactive.py
