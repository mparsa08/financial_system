# Generated by Django 5.2.4 on 2025-07-09 16:39

import django.contrib.auth.models
import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Asset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('symbol', models.CharField(max_length=50)),
                ('name', models.CharField(max_length=255)),
                ('asset_type', models.CharField(choices=[('SPOT', 'Spot'), ('DERIVATIVE', 'Derivative')], max_length=50)),
            ],
        ),
        migrations.CreateModel(
            name='Currency',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=10)),
                ('name', models.CharField(max_length=50)),
            ],
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(error_messages={'unique': 'A user with that username already exists.'}, help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.', max_length=150, unique=True, validators=[django.contrib.auth.validators.UnicodeUsernameValidator()], verbose_name='username')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='email address')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('role', models.CharField(choices=[('Admin', 'Admin'), ('Accountant', 'Accountant'), ('Trader', 'Trader')], default='Trader', max_length=50)),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
                'abstract': False,
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='ChartOfAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_number', models.CharField(max_length=50)),
                ('account_name', models.CharField(max_length=255)),
                ('account_type', models.CharField(choices=[('Asset', 'Asset'), ('Liability', 'Liability'), ('Equity', 'Equity'), ('Revenue', 'Revenue'), ('Expense', 'Expense')], max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('counterparty_user', models.ForeignKey(blank=True, help_text='Connects this account to a specific user as a counterparty', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gl_accounts', to=settings.AUTH_USER_MODEL)),
                ('parent_account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.chartofaccount')),
            ],
        ),
        migrations.CreateModel(
            name='JournalEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entry_date', models.DateField()),
                ('description', models.TextField()),
                ('posted_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='JournalEntryLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('debit_amount', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('credit_amount', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.chartofaccount')),
                ('journal_entry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.journalentry')),
            ],
        ),
        migrations.CreateModel(
            name='TradingAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_type', models.CharField(choices=[('Crypto', 'Crypto'), ('Forex', 'Forex')], max_length=50)),
                ('name', models.CharField(max_length=100)),
                ('account_purpose', models.CharField(choices=[('SPOT', 'Spot Trading'), ('FUTURES', 'Futures Trading')], help_text='مشخص می\u200cکند که این حساب برای چه نوع معاملاتی استفاده می\u200cشود.', max_length=50)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Trade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('OPEN', 'Open'), ('CLOSED', 'Closed')], default='OPEN', max_length=10)),
                ('position_side', models.CharField(choices=[('LONG', 'Long'), ('SHORT', 'Short')], max_length=10)),
                ('entry_price', models.DecimalField(decimal_places=8, max_digits=20)),
                ('quantity', models.DecimalField(decimal_places=8, max_digits=20)),
                ('entry_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('exit_price', models.DecimalField(blank=True, decimal_places=8, max_digits=20, null=True)),
                ('exit_date', models.DateTimeField(blank=True, null=True)),
                ('gross_profit_or_loss', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('broker_commission', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('trader_commission', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('asset', models.ForeignKey(limit_choices_to={'asset_type': 'DERIVATIVE'}, on_delete=django.db.models.deletion.PROTECT, to='core.asset')),
                ('commission_recipient', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='commissioned_trades', to=settings.AUTH_USER_MODEL)),
                ('trading_account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='trades', to='core.tradingaccount')),
            ],
        ),
        migrations.AddField(
            model_name='chartofaccount',
            name='trading_account',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='chart_of_accounts', to='core.tradingaccount'),
        ),
        migrations.CreateModel(
            name='AssetLot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=8, help_text='مقدار اولیه خریداری شده در این دسته', max_digits=20)),
                ('purchase_price_usd', models.DecimalField(decimal_places=8, help_text='قیمت هر واحد به دلار در لحظه خرید', max_digits=20)),
                ('purchase_date', models.DateTimeField(auto_now_add=True)),
                ('remaining_quantity', models.DecimalField(decimal_places=8, help_text='مقدار باقی\u200cمانده از این دسته که هنوز فروخته نشده', max_digits=20)),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lots', to='core.asset')),
                ('trading_account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lots', to='core.tradingaccount')),
            ],
            options={
                'ordering': ['purchase_date'],
            },
        ),
    ]
