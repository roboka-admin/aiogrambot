from aiogram.filters.callback_data import CallbackData


class AdminUsersCallback(CallbackData, prefix="admin_users"):
    page: int


class AdminUserCallback(CallbackData, prefix="admin_user"):
    telegram_id: int
    source: str = "users"
    page: int = 0


class AdminUserActionCallback(CallbackData, prefix="admin_user_action"):
    action: str
    telegram_id: int
    source: str = "users"
    page: int = 0


class AdminUserAmountCallback(CallbackData, prefix="admin_user_amount"):
    action: str
    telegram_id: int


class AdminBroadcastStartCallback(CallbackData, prefix="admin_broadcast_start"):
    pass


class AdminBroadcastConfirmCallback(CallbackData, prefix="admin_broadcast_confirm"):
    pass


class AdminBroadcastEditCallback(CallbackData, prefix="admin_broadcast_edit"):
    pass


class AdminBroadcastCancelCallback(CallbackData, prefix="admin_broadcast_cancel"):
    pass


class AdminBlockedUsersCallback(CallbackData, prefix="admin_blocked_users"):
    page: int


class AdminStatsCallback(CallbackData, prefix="admin_stats"):
    section: str


class AdminStatsRefreshCallback(CallbackData, prefix="admin_stats_refresh"):
    section: str


class AdminForceSubscriptionStatsTargetCallback(
    CallbackData, prefix="admin_force_subscription_stats_target"
):
    chat_id: int


class AdminForceSubscriptionStatsTargetRefreshCallback(
    CallbackData, prefix="admin_force_subscription_stats_target_refresh"
):
    chat_id: int


class AdminManagementCallback(CallbackData, prefix="admin_management"):
    action: str
    telegram_id: int = 0


class AdminPermissionCallback(CallbackData, prefix="admin_permission"):
    telegram_id: int
    permission_key: str


class AdminCreatePermissionCallback(CallbackData, prefix="admin_create_permission"):
    permission_key: str


class AdminCreateConfirmCallback(CallbackData, prefix="admin_create_confirm"):
    pass


class AdminCreateCancelCallback(CallbackData, prefix="admin_create_cancel"):
    pass
