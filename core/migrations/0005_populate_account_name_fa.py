from django.db import migrations


def populate_farsi_names(apps, schema_editor):
    ChartOfAccount = apps.get_model('core', 'ChartOfAccount')
    mapping = {
        'Assets': 'دارایی‌ها',
        'Cash': 'نقد',
        'Spot Assets Holdings': 'دارایی‌های اسپات',
        'Derivative Contracts': 'قراردادهای مشتقه',
        'Initial Margin': 'مارجین اولیه',
        'Maintenance Margin': 'مارجین نگهداری',
        'Unrealized PnL - Derivatives': 'سود/زیان تحقق‌نیافته - مشتقات',
        'Liabilities': 'بدهی‌ها',
        'Equity': 'حقوق صاحبان سهام',
        'User Capital': 'سرمایه کاربر',
        'Revenues': 'درآمدها',
        'Realized PnL - Derivatives': 'سود/زیان تحقق‌یافته - مشتقات',
        'Commissions & Fees': 'کارمزدها و هزینه‌ها',
        'Funding Receipts': 'دریافت‌های فاندینگ',
        'Lending Income': 'درآمد وام‌دهی',
        'Staking Rewards': 'جوایز استیکینگ',
        'Expenses': 'هزینه‌ها',
        'Trading Fees': 'کارمزد معاملات',
        'Interest Expense': 'هزینه بهره',
        'Funding Payments': 'پرداخت‌های فاندینگ',
        'Withdrawal Fees': 'کارمزد برداشت',
        'Platform Fees': 'هزینه‌های پلتفرم',
    }
    for account in ChartOfAccount.objects.all():
        for eng, fa in mapping.items():
            if account.account_name.startswith(eng):
                suffix = account.account_name[len(eng):]
                account.account_name_fa = f"{fa}{suffix}"
                account.save(update_fields=["account_name_fa"])
                break
        else:
            account.account_name_fa = account.account_name
            account.save(update_fields=["account_name_fa"])


def reverse_func(apps, schema_editor):
    # No reverse; leave existing values
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_chartofaccount_account_name_fa"),
    ]

    operations = [
        migrations.RunPython(populate_farsi_names, reverse_func),
    ]
