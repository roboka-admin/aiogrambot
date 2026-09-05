from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AdminPermissionDefinition:
    key: str
    title: str
    description: str


# This is the single registry for capabilities exposed by the admin panel.
# Adding a new panel capability only requires registering it here; the
# database schema and admin-assignment mechanism do not need to change.
ADMIN_PERMISSION_REGISTRY: tuple[AdminPermissionDefinition, ...] = (
    AdminPermissionDefinition("users", "👤 کاربران", "مشاهده و مدیریت کاربران"),
    AdminPermissionDefinition("support", "📩 پشتیبانی", "مشاهده و پاسخ به تیکت‌های پشتیبانی"),
    AdminPermissionDefinition("force_subscription", "📢 عضویت اجباری", "مدیریت مقصدهای عضویت اجباری"),
    AdminPermissionDefinition("stats", "📊 آمار", "مشاهده آمار ربات"),
    AdminPermissionDefinition("broadcast", "📢 ارسال همگانی", "ارسال پیام همگانی"),
    AdminPermissionDefinition("settings", "⚙️ تنظیمات ربات", "مدیریت تنظیمات ربات"),
)
