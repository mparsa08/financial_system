from django.urls import path
from .views import DashboardView, DepositView, WithdrawView, TradeView, TradeBuyView, TradeSellView, HistoryView, LoginView, logout_view, CreateTradingAccountView, ChartOfAccountsView, IncomeStatementView, AddClosedTradeView, DeleteTradingAccountView, CalculateUnrealizedPnLView, TransferFundsView

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('deposit/', DepositView.as_view(), name='deposit_funds'),
    path('withdraw/', WithdrawView.as_view(), name='withdraw_funds'),
    path('trade/', TradeView.as_view(), name='trade_assets'),
    path('trade/buy/', TradeBuyView.as_view(), name='trade_buy'),
    path('trade/sell/', TradeSellView.as_view(), name='trade_sell'),
    path('history/', HistoryView.as_view(), name='transaction_history'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
    path('create-trading-account/', CreateTradingAccountView.as_view(), name='create_trading_account'),
    path('chart-of-accounts/', ChartOfAccountsView.as_view(), name='chart_of_accounts'),
    path('income-statement/', IncomeStatementView.as_view(), name='income_statement'),
    path('add-closed-trade/', AddClosedTradeView.as_view(), name='add_closed_trade'),
    path('delete-trading-account/<int:pk>/', DeleteTradingAccountView.as_view(), name='delete_trading_account'),
    path('calculate-unrealized-pnl/', CalculateUnrealizedPnLView.as_view(), name='unrealized_pnl_view'),
    path('transfer-funds/', TransferFundsView.as_view(), name='transfer_funds'),
]
