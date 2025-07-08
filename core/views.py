# --- Imports from Django ---
from datetime import datetime
import decimal
from django.db import transaction
from django.utils import timezone
from django.views.generic import TemplateView


# --- Imports from Django REST Framework ---
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

# --- Imports from your app ---
from .models import (
    User, 
    Currency, 
    ChartOfAccount, 
    JournalEntry, 
    JournalEntryLine, 
    TradingAccount, 
    Asset, 
    ClosedTradesLog
)
from .serializers import *
from .services import generate_income_statement, make_deposit, make_withdrawal, deposit_spot_asset, withdraw_spot_asset, execute_spot_buy, execute_spot_sell, record_closed_trade
from .permissions import IsAdminUser, IsAccountantUser, IsTraderUser

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

class CurrencyViewSet(viewsets.ModelViewSet):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    permission_classes = [IsAuthenticated]

class ChartOfAccountViewSet(viewsets.ModelViewSet):
    queryset = ChartOfAccount.objects.all()
    serializer_class = ChartOfAccountSerializer
    permission_classes = [IsAuthenticated, IsAccountantUser | IsAdminUser]

class JournalEntryViewSet(viewsets.ModelViewSet):
    queryset = JournalEntry.objects.all()
    serializer_class = JournalEntrySerializer
    permission_classes = [IsAuthenticated, IsAccountantUser | IsAdminUser]

class JournalEntryLineViewSet(viewsets.ModelViewSet):
    queryset = JournalEntryLine.objects.all()
    serializer_class = JournalEntryLineSerializer
    permission_classes = [IsAuthenticated, IsAccountantUser | IsAdminUser]

class TradingAccountViewSet(viewsets.ModelViewSet):
    queryset = TradingAccount.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role == 'Admin':
            return TradingAccount.objects.all()
        return TradingAccount.objects.filter(user=self.request.user)

    @action(detail=True, methods=['get'])
    def income_statement(self, request, pk=None):
        """
        صورت سود و زیان را برای این حساب معاملاتی برمی‌گرداند.
        تاریخ شروع و پایان را از query params دریافت می‌کند.
        مثال: /api/trading-accounts/1/income-statement/?start_date=2025-01-01&end_date=2025-12-31
        """
        trading_account = self.get_object()
        
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if not start_date_str or not end_date_str:
            return Response(
                {'error': 'start_date and end_date query parameters are required in YYYY-MM-DD format.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Dates must be in YYYY-MM-DD format.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        report_data = generate_income_statement(trading_account, start_date, end_date)
        
        return Response(report_data, status=status.HTTP_200_OK)
    @action(detail=True, methods=['post'])
    def withdraw_asset(self, request, pk=None):
        """
        اکشن سفارشی برای برداشت یک دارایی اسپات (کریپتو).
        """
        # این کد تقریبا کپی کامل اکشن deposit_asset است و فقط سرویس دیگری را صدا می‌زند
        trading_account = self.get_object()
        asset_id = request.data.get('asset_id')
        quantity = request.data.get('quantity')
        price_usd = request.data.get('price_usd')
        description = request.data.get('description', 'Spot Asset Withdrawal')

        if not all([asset_id, quantity, price_usd]):
            return Response({'error': 'asset_id, quantity, and price_usd are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            asset = Asset.objects.get(pk=asset_id)
            withdraw_spot_asset(
                trading_account=trading_account,
                asset=asset,
                quantity=decimal.Decimal(quantity),
                price_usd=decimal.Decimal(price_usd),
                description=description,
                user=request.user
            )
            return Response({'status': 'Asset withdrawal executed successfully.'}, status=status.HTTP_200_OK)
        except Asset.DoesNotExist:
            return Response({'error': 'Asset not found.'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
    @action(detail=True, methods=['post'])
    def deposit_asset(self, request, pk=None):
        """
        اکشن سفارشی برای واریز یک دارایی اسپات (کریپتو).
        """
        trading_account = self.get_object()
        
        asset_id = request.data.get('asset_id')
        quantity = request.data.get('quantity')
        price_usd = request.data.get('price_usd')
        description = request.data.get('description', 'Spot Asset Deposit')

        if not all([asset_id, quantity, price_usd]):
            return Response({'error': 'asset_id, quantity, and price_usd are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            asset = Asset.objects.get(pk=asset_id)
            deposit_spot_asset(
                trading_account=trading_account,
                asset=asset,
                quantity=decimal.Decimal(quantity),
                price_usd=decimal.Decimal(price_usd),
                description=description,
                user=request.user
            )
            return Response({'status': 'Asset deposit executed successfully.'}, status=status.HTTP_200_OK)

        except Asset.DoesNotExist:
            return Response({'error': 'Asset not found.'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
    @action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        """
        اکشن سفارشی برای برداشت وجه از یک حساب معاملاتی.
        """
        trading_account = self.get_object()
        amount = request.data.get('amount')
        description = request.data.get('description', 'Withdrawal')

        try:
            # تبدیل به Decimal برای دقت
            amount_decimal = decimal.Decimal(amount) if amount is not None else 0
            
            # فراخوانی سرویس فانکشن مشترک
            make_withdrawal(
                trading_account=trading_account,
                amount=amount_decimal,
                description=description,
                user=request.user
            )
            return Response({'status': 'Withdrawal executed successfully.'}, status=status.HTTP_200_OK)

        except ValueError as e:
            # گرفتن خطاهایی که از سرویس فانکشن می‌آیند (مثل کمبود وجه)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def deposit(self, request, pk=None):
        trading_account = self.get_object()
        amount = request.data.get('amount')
        description = request.data.get('description', 'Capital Deposit via API')

        try:
            # فراخوانی سرویس فانکشن مشترک
            make_deposit(
                trading_account=trading_account,
                amount=amount,
                description=description,
                user=request.user
            )
            return Response({'status': 'deposit successful'}, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    def get_serializer_class(self):
        """
        بسته به اکشن، سریالایزر مناسب را برمی‌گرداند.
        """
        # اگر اکشن 'retrieve' (نمایش جزئیات یک آیتم) بود
        if self.action == 'retrieve':
            return TradingAccountDetailSerializer
        
        # در غیر این صورت (مثلا برای list, create, update)
        return TradingAccountSerializer
    

    @action(detail=True, methods=['post'])
    def execute_spot_buy(self, request, pk=None):
        """
        اکشن سفارشی برای اجرای یک معامله اسپات.
        """
        trading_account = self.get_object()
        
        # دریافت داده‌ها از بدنه درخواست
        asset_id = request.data.get('asset_id')
        quantity = request.data.get('quantity')
        trade_cost = request.data.get('trade_cost')
        description = request.data.get('description', 'Spot Trade')

        # اعتبارسنجی ورودی‌های اولیه
        if not all([asset_id, quantity, trade_cost]):
            return Response({'error': 'asset_id, quantity, and trade_cost are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            asset = Asset.objects.get(pk=asset_id)
            # فراخوانی سرویس فانکشن اصلی
            execute_spot_buy(
                trading_account=trading_account,
                asset=asset,
                quantity=decimal.Decimal(quantity),  # تبدیل به Decimal برای دقت
                trade_cost=decimal.Decimal(trade_cost),
                description=description,
                user=request.user
            )
            return Response({'status': 'Spot trade executed successfully.'}, status=status.HTTP_200_OK)

        except Asset.DoesNotExist:
            return Response({'error': 'Asset not found.'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            # گرفتن خطاهایی که از سرویس فانکشن می‌آیند (مثل کمبود وجه)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def execute_spot_sell(self, request, pk=None):
        """
        اکشن سفارشی برای اجرای فروش یک دارایی اسپات.
        """
        trading_account = self.get_object()
        
        asset_id = request.data.get('asset_id')
        quantity = request.data.get('quantity')
        trade_cost = request.data.get('trade_cost')
        description = request.data.get('description', 'Spot Sell')

        if not all([asset_id, quantity, trade_cost]):
            return Response({'error': 'asset_id, quantity, and trade_cost are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            asset = Asset.objects.get(pk=asset_id)
            execute_spot_sell(
                trading_account=trading_account,
                asset=asset,
                quantity=decimal.Decimal(quantity),
                trade_cost=decimal.Decimal(trade_cost),
                description=description,
                user=request.user
            )
            return Response({'status': 'Spot sell executed successfully.'}, status=status.HTTP_200_OK)

        except Asset.DoesNotExist:
            return Response({'error': 'Asset not found.'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer
    permission_classes = [IsAuthenticated]

class AssetLotViewSet(viewsets.ModelViewSet):
    queryset = AssetLot.objects.all()
    serializer_class = AssetLotSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role == 'Admin':
            return AssetLot.objects.all()
        return AssetLot.objects.filter(trading_account__user=self.request.user)

class ClosedTradesLogViewSet(viewsets.ModelViewSet):
    queryset = ClosedTradesLog.objects.all()
    serializer_class = ClosedTradesLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role == 'Admin':
            return ClosedTradesLog.objects.all()
        return ClosedTradesLog.objects.filter(trading_account__user=self.request.user)

    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Extract data for the service function
            trading_account_id = serializer.validated_data.get('trading_account').id
            asset_id = serializer.validated_data.get('asset').id
            trade_date = serializer.validated_data.get('trade_date')
            net_profit_or_loss = serializer.validated_data.get('net_profit_or_loss')
            broker_commission = serializer.validated_data.get('broker_commission')
            trader_commission = serializer.validated_data.get('trader_commission')
            commission_recipient_id = serializer.validated_data.get('commission_recipient').id if serializer.validated_data.get('commission_recipient') else None

            try:
                # Fetch related objects
                trading_account = TradingAccount.objects.get(id=trading_account_id)
                asset = Asset.objects.get(id=asset_id)
                commission_recipient = User.objects.get(id=commission_recipient_id) if commission_recipient_id else None

                # Call the service function
                record_closed_trade(
                    trading_account=trading_account,
                    asset=asset,
                    trade_date=trade_date,
                    net_profit_or_loss=net_profit_or_loss,
                    broker_commission=broker_commission,
                    trader_commission=trader_commission,
                    commission_recipient=commission_recipient
                )
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except TradingAccount.DoesNotExist:
                return Response({"error": "Trading account not found."}, status=status.HTTP_404_NOT_FOUND)
            except Asset.DoesNotExist:
                return Response({"error": "Asset not found."}, status=status.HTTP_404_NOT_FOUND)
            except User.DoesNotExist:
                return Response({"error": "Commission recipient user not found."}, status=status.HTTP_404_NOT_FOUND)
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({"error": f"An unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class DashboardView(TemplateView):
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['trading_accounts'] = TradingAccount.objects.filter(user=self.request.user)
        return context