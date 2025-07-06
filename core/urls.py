from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, CurrencyViewSet, ChartOfAccountViewSet, JournalEntryViewSet, JournalEntryLineViewSet, TradingAccountViewSet, AssetViewSet, AssetLotViewSet, ClosedTradesLogViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'currencies', CurrencyViewSet)
router.register(r'chart-of-accounts', ChartOfAccountViewSet)
router.register(r'journal-entries', JournalEntryViewSet)
router.register(r'journal-entry-lines', JournalEntryLineViewSet)
router.register(r'trading-accounts', TradingAccountViewSet)
router.register(r'assets', AssetViewSet)
router.register(r'asset-wallets', AssetLotViewSet)
router.register(r'closed-trades-logs', ClosedTradesLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
]