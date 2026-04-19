import os
import sys
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime

# ---------------------------
# 1. دریافت اطلاعات حساب از متغیرهای محیطی (مورد نیاز گیت‌هاب اکشن)
# ---------------------------
EMAIL_USER = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASS = os.environ.get("EMAIL_PASSWORD")

if not EMAIL_USER or not EMAIL_PASS:
    print("❌ خطا: متغیرهای محیطی EMAIL_ADDRESS و EMAIL_PASSWORD تنظیم نشده‌اند.")
    print("لطفاً آن‌ها را در Secrets گیت‌هاب یا محیط اجرای خود تعریف کنید.")
    sys.exit(1)

# ---------------------------
# 2. تشخیص خودکار سرور IMAP بر اساس دامنه ایمیل
# ---------------------------
def get_imap_server(email_addr):
    email_addr = email_addr.lower()
    if "@gmail.com" in email_addr:
        return "imap.gmail.com"
    elif "@yahoo.com" in email_addr or "@ymail.com" in email_addr:
        return "imap.mail.yahoo.com"
    elif "@outlook.com" in email_addr or "@hotmail.com" in email_addr or "@live.com" in email_addr:
        return "outlook.office365.com"
    else:
        # اگر ارائه‌دهنده دیگری باشد، می‌توانید سرور را مستقیماً اینجا وارد کنید
        # یا از متغیر محیطی IMAP_SERVER استفاده کنید
        custom_server = os.environ.get("IMAP_SERVER")
        if custom_server:
            return custom_server
        else:
            print("❌ خطا: نمی‌توان سرور IMAP را تشخیص داد. لطفاً متغیر IMAP_SERVER را تنظیم کنید.")
            sys.exit(1)

IMAP_SERVER = get_imap_server(EMAIL_USER)
print(f"📡 در حال اتصال به سرور: {IMAP_SERVER}")

# ---------------------------
# 3. توابع کمکی برای پردازش ایمیل
# ---------------------------
def decode_subject(subject):
    """رمزگشایی موضوع ایمیل با پشتیبانی از UTF-8"""
    if subject is None:
        return "(بدون موضوع)"
    decoded_parts = []
    for part, encoding in decode_header(subject):
        if isinstance(part, bytes):
            try:
                decoded_part = part.decode(encoding if encoding else "utf-8", errors="ignore")
            except (UnicodeDecodeError, LookupError):
                decoded_part = part.decode("utf-8", errors="ignore")
            decoded_parts.append(decoded_part)
        else:
            decoded_parts.append(part)
    return "".join(decoded_parts)

def get_email_body(msg):
    """استخراج بدنه متنی ایمیل (ترجیحاً text/plain)"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            # از ضمیمه‌ها صرف‌نظر می‌کنیم
            if "attachment" not in content_disposition:
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        try:
                            body = payload.decode()
                            break  # اولویت با نسخه ساده متنی است
                        except:
                            continue
                elif content_type == "text/html" and not body:
                    # اگر متن ساده نبود، از HTML استفاده می‌کنیم (در حد امکان)
                    payload = part.get_payload(decode=True)
                    if payload:
                        try:
                            body = payload.decode()
                        except:
                            continue
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            try:
                body = payload.decode()
            except:
                body = str(payload)
    
    if not body:
        return "(محتوای متنی یافت نشد)"
    
    # کوتاه کردن متن برای نمایش خلاصه (200 کاراکتر)
    if len(body) > 200:
        return body[:200] + "..."
    return body

# ---------------------------
# 4. اتصال به سرور و دریافت ۱۰ ایمیل آخر
# ---------------------------
try:
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_USER, EMAIL_PASS)
    mail.select("inbox")

    # جستجوی همه ایمیل‌ها
    status, data = mail.search(None, "ALL")
    if status != "OK":
        print("❌ خطا در جستجوی ایمیل‌ها.")
        sys.exit(1)

    mail_ids = data[0].split()
    total_emails = len(mail_ids)
    print(f"📬 تعداد کل ایمیل‌ها: {total_emails}")

    if total_emails == 0:
        print("ℹ️ صندوق ورودی خالی است.")
    else:
        # انتخاب ۱۰ ایمیل آخر (یا کمتر)
        last_10_ids = mail_ids[-10:] if total_emails >= 10 else mail_ids
        print(f"🔍 در حال دریافت جزئیات {len(last_10_ids)} ایمیل آخر...\n")

        # ایمیل‌ها را از جدیدترین به قدیمی‌ترین مرور می‌کنیم
        for i, mail_id in enumerate(reversed(last_10_ids)):
            status, msg_data = mail.fetch(mail_id, "(RFC822)")
            if status != "OK":
                print(f"⚠️ خطا در دریافت ایمیل با شناسه {mail_id.decode()}")
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            # استخراج اطلاعات
            subject = decode_subject(msg["Subject"])
            from_ = msg["From"]
            date_str = msg["Date"]
            
            # فرمت‌دهی تاریخ
            try:
                date_obj = parsedate_to_datetime(date_str)
                date_clean = date_obj.strftime("%Y-%m-%d %H:%M")
            except:
                date_clean = date_str if date_str else "تاریخ نامشخص"

            # چاپ اطلاعات در کنسول (گیت‌هاب لاگ)
            print(f"📧 ایمیل #{i+1}")
            print(f"   از طرف: {from_}")
            print(f"   تاریخ:  {date_clean}")
            print(f"   موضوع:  {subject}")
            print(f"   متن:    {get_email_body(msg)}")
            print("-" * 50)

    mail.close()
    mail.logout()
    print("✅ اتصال با موفقیت بسته شد.")

except imaplib.IMAP4.error as e:
    print(f"❌ خطای احراز هویت یا IMAP: {e}")
    print("راهنمایی: مطمئن شوید که:")
    print("1. دسترسی IMAP در تنظیمات ایمیل فعال است.")
    print("2. از «رمز برنامه» (App Password) استفاده کرده‌اید.")
    sys.exit(1)
except Exception as e:
    print(f"❌ خطای غیرمنتظره: {e}")
    sys.exit(1)
