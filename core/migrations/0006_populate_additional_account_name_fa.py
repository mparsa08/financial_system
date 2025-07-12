from django.db import migrations


def populate_more_farsi_names(apps, schema_editor):
    ChartOfAccount = apps.get_model('core', 'ChartOfAccount')

    updates = {
        'Realized Gain on Spot Sale': 'سود حاصل از فروش اسپات',
        'Realized Loss on Spot Sale': 'ضرر حاصل از فروش اسپات',
    }
    for eng, fa in updates.items():
        ChartOfAccount.objects.filter(account_name=eng).update(account_name_fa=fa)

    prefix = 'Payable to:'
    for account in ChartOfAccount.objects.filter(account_name__startswith=prefix):
        suffix = account.account_name[len(prefix):].strip()
        account.account_name_fa = f'قابل پرداخت به {suffix}'
        account.save(update_fields=['account_name_fa'])


def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_populate_account_name_fa'),
    ]

    operations = [
        migrations.RunPython(populate_more_farsi_names, reverse_func),
    ]
