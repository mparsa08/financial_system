# --- Imports from Django ---
from django.shortcuts import get_object_or_404, redirect
from datetime import datetime
import decimal
from django.db import transaction
from django.utils import timezone
from django.views.generic import TemplateView
import re


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
    Trade
)
from .serializers import *
from .services import Decimal, close_trade, generate_income_statement, make_deposit, make_withdrawal, deposit_spot_asset, open_trade, withdraw_spot_asset, execute_spot_buy, execute_spot_sell
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


class TradeViewSet(viewsets.ModelViewSet):
    """
    این ViewSet تمام عملیات مربوط به معاملات (باز کردن، بستن، مشاهده) را مدیریت می‌کند.
    """
    queryset = Trade.objects.all().order_by('-entry_date')
    serializer_class = TradeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        فقط معاملاتی را نشان می‌دهد که به کاربر لاگین کرده تعلق دارند.
        ادمین همه معاملات را می‌بیند.
        """
        if self.request.user.role == 'Admin':
            return Trade.objects.all().order_by('-entry_date')
        return Trade.objects.filter(trading_account__user=self.request.user).order_by('-entry_date')

    def perform_create(self, serializer):
        """
        این متد بازنویسی شده تا به جای ذخیره مستقیم، تابع سرویس 'open_trade' را فراخوانی کند.
        این متد مسئول باز کردن یک معامله جدید است.
        """
        data = serializer.validated_data
        open_trade(
            trading_account=data['trading_account'],
            asset=data['asset'],
            side=data['position_side'],
            quantity=data['quantity'],
            entry_price=data['entry_price']
        )

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """
        یک اکشن سفارشی برای بستن یک معامله باز.
        URL: POST /api/v1/trades/{id}/close/
        """
        # معامله‌ای که قرار است بسته شود را پیدا می‌کنیم
        trade_to_close = self.get_object()
        
        # داده‌های لازم برای بستن معامله را از بدنه درخواست می‌خوانیم
        exit_price = request.data.get('exit_price')
        broker_commission = request.data.get('broker_commission')
        trader_commission = request.data.get('trader_commission')
        commission_recipient_id = request.data.get('commission_recipient')

        # اعتبارسنجی ورودی‌ها
        if not all([exit_price, broker_commission, trader_commission, commission_recipient_id]):
            return Response(
                {"error": "exit_price, broker_commission, trader_commission, and commission_recipient are required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            recipient = User.objects.get(id=commission_recipient_id)
            # فراخوانی سرویس بستن معامله
            closed_trade = close_trade(
                trade_to_close=trade_to_close,
                exit_price=Decimal(exit_price),
                broker_commission=Decimal(broker_commission),
                trader_commission=Decimal(trader_commission),
                commission_recipient=recipient
            )
            # نمایش معامله به‌روز شده به کاربر
            serializer = self.get_serializer(closed_trade)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": "Commission recipient user not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
class DashboardView(TemplateView):
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['trading_accounts'] = TradingAccount.objects.filter(user=self.request.user)
        return context

import re
from django.db import transaction

from decimal import Decimal

from django.contrib import messages
from decimal import Decimal, InvalidOperation

def journal_entry_delete(request, pk):
    journal_entry = get_object_or_404(JournalEntry, pk=pk)
    if request.method == 'POST':
        with transaction.atomic():
            # Check for Futures Trade by description
            trade_id_match = re.search(r'Trade #(\d+)', journal_entry.description)
            
            # Check for Spot Asset purchase by looking at the accounts involved
            is_spot_buy = journal_entry.journalentryline_set.filter(account__account_number='1020', debit_amount__gt=0).exists()

            if trade_id_match:
                # --- Handle Futures Trade Deletion ---
                trade_id = int(trade_id_match.group(1))
                try:
                    trade_to_delete = Trade.objects.get(id=trade_id)
                    related_journal_entries = JournalEntry.objects.filter(description__contains=f'Trade #{trade_id}')
                    related_journal_entries.delete()
                    trade_to_delete.delete()
                    messages.success(request, f"Successfully deleted trade #{trade_id} and its associated journal entries.")
                except Trade.DoesNotExist:
                    journal_entry.delete() # Orphaned entry, just delete it

            elif is_spot_buy:
                # --- Handle Spot Asset Purchase Deletion (New, Safer Logic) ---
                spot_buy_match = re.search(r'Spot Buy: ([\d.]+) (\w+)', journal_entry.description)
                lot_deleted = False
                if spot_buy_match:
                    try:
                        quantity = Decimal(spot_buy_match.group(1))
                        asset_symbol = spot_buy_match.group(2)
                        
                        asset_holding_line = journal_entry.journalentryline_set.filter(account__account_number='1020').first()

                        if asset_holding_line and quantity > 0:
                            trade_cost = asset_holding_line.debit_amount
                            trading_account = asset_holding_line.account.trading_account
                            purchase_price = trade_cost / quantity

                            # Build a highly precise filter
                            matching_lots = AssetLot.objects.filter(
                                trading_account=trading_account,
                                asset__symbol=asset_symbol,
                                quantity=quantity,
                                purchase_price_usd=purchase_price,
                                purchase_date__date=journal_entry.entry_date
                            )

                            # --- SAFETY CHECK --- #
                            if matching_lots.count() == 1:
                                matching_lots.first().delete()
                                lot_deleted = True
                            else:
                                # If we find 0 or more than 1, we have an ambiguity.
                                messages.warning(request, f"Could not uniquely identify the asset lot for journal entry #{journal_entry.id}. The journal entry was deleted, but the asset lot requires manual review.")

                    except (InvalidOperation, IndexError):
                        messages.error(request, f"Could not parse details from journal entry #{journal_entry.id} description.")
                
                journal_entry.delete()
                if lot_deleted:
                    messages.success(request, f"Journal entry #{journal_entry.id} and its associated asset lot were successfully deleted.")
                else:
                    messages.info(request, f"Journal entry #{journal_entry.id} was deleted.")

            else:
                # --- Handle all other Journal Entries ---
                journal_entry.delete()
                messages.success(request, f"Journal entry #{journal_entry.id} has been deleted.")
                
        return redirect('transaction_history')
    return redirect('transaction_history')

def trade_delete(request, pk):
    trade = get_object_or_404(Trade, pk=pk)
    if request.method == 'POST':
        with transaction.atomic():
            # Find journal entries related to this trade by looking for a unique identifier in the description
            journal_entries = JournalEntry.objects.filter(description__contains=f'Trade #{trade.id}')
            # Delete all related journal entries
            journal_entries.delete()
            # Delete the trade itself
            trade.delete()
        return redirect('transaction_history')
    return redirect('transaction_history')