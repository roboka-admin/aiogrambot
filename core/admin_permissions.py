from models.admin import AdminPermission


# Single source of truth for capabilities exposed by the admin panel.
# Adding a new panel capability only requires adding one entry here; the
# database schema and admin-assignment mechanism do not need to change.
ADMIN_PERMISSION_REGISTRY: tuple[AdminPermission, ...] = (
    AdminPermission("users", "👤 کاربران", "مشاهده و مدیریت کاربران"),
    AdminPermission("support", "📩 پشتیبانی", "مشاهده و پاسخ به تیکت‌های پشتیبانی"),
    AdminPermission("force_subscription", "📢 عضویت اجباری", "مدیریت مقصدهای عضویت اجباری"),
    AdminPermission("stats", "📊 آمار", "مشاهده آمار ربات"),
    AdminPermission("broadcast", "📢 ارسال همگانی", "ارسال پیام همگانی"),
    AdminPermission("settings", "⚙️ تنظیمات ربات", "مدیریت تنظیمات ربات"),
)
