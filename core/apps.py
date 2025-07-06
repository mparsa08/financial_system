from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # این خط سیگنال‌های ما را هنگام بالا آمدن سرور، به جنگو معرفی می‌کند.
        import core.signals
