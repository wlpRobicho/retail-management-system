from datetime import datetime, timedelta
from collections import defaultdict
from decimal import Decimal
from django.utils.timezone import now
from sales.models import SalesTransaction
from django.db.models import Sum
import calendar


def get_start_end_of_week(date):
    start = date - timedelta(days=date.weekday())
    end = start + timedelta(days=6)
    return start, end


def get_week_ranges_in_month(year, month):
    _, last_day = calendar.monthrange(year, month)
    start_date = datetime(year, month, 1).date()
    end_date = datetime(year, month, last_day).date()

    weeks = []
    current = start_date
    while current <= end_date:
        week_start, week_end = get_start_end_of_week(current)
        week_end = min(week_end, end_date)
        label = f"Week {len(weeks)+1} ({week_start.strftime('%d %b')} - {week_end.strftime('%d %b')})"
        weeks.append((label, week_start, week_end))
        current = week_end + timedelta(days=1)
    return weeks


def get_sales_summary(start_date, end_date):
    transactions = SalesTransaction.objects.filter(timestamp__date__range=(start_date, end_date))

    total = transactions.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    profit = transactions.aggregate(profit=Sum('total_profit'))['profit'] or Decimal('0.00')
    refunds = transactions.filter(total_amount__lt=0).aggregate(refunds=Sum('total_amount'))['refunds'] or Decimal('0.00')

    return {
        "total": round(total, 2),
        "profit": round(profit, 2),
        "refunds": round(refunds, 2),
    }


def get_daily_breakdown(start_date):
    breakdown = []
    for i in range(7):
        day = start_date + timedelta(days=i)
        data = get_sales_summary(day, day)
        breakdown.append({
            "label": day.strftime('%A'),
            "date": str(day),
            "total": data["total"],
            "profit": data["profit"],
            "refunds": data["refunds"],
        })
    return breakdown


def get_analytics():
    today = now().date()
    start_of_week, end_of_week = get_start_end_of_week(today)
    year, month = today.year, today.month
    weeks = get_week_ranges_in_month(year, month)

    daily_data = get_sales_summary(today, today)
    weekly_data = get_sales_summary(start_of_week, end_of_week)
    monthly_data = get_sales_summary(datetime(year, month, 1).date(), datetime(year, month, calendar.monthrange(year, month)[1]).date())

    # Week-by-week breakdown for monthly
    monthly_breakdown = []
    for label, start, end in weeks:
        summary = get_sales_summary(start, end)
        monthly_breakdown.append({
            "label": label,
            "total": summary["total"],
            "profit": summary["profit"],
            "refunds": summary["refunds"],
        })

    # Day-by-day breakdown for current week
    weekly_breakdown = get_daily_breakdown(start_of_week)

    # Payment breakdown
    payments = SalesTransaction.objects.filter(timestamp__month=month).values('payment_method').annotate(total=Sum('total_amount'))
    payment_summary = {
        "cash": Decimal('0.00'),
        "card": Decimal('0.00'),
        "refunds": Decimal('0.00'),
    }
    for entry in payments:
        method = entry['payment_method']
        total = entry['total'] or Decimal('0.00')
        if method == 'cash':
            payment_summary["cash"] += total
        elif method == 'card':
            payment_summary["card"] += total
        elif total < 0:
            payment_summary["refunds"] += abs(total)

    # Top products
    top_products = (
        SalesTransaction.objects
        .filter(timestamp__month=month)
        .values('items__product__name')
        .annotate(quantity_sold=Sum('items__quantity'))
        .order_by('-quantity_sold')[:5]
    )

    return {
        "daily": {
            "label": today.strftime('%d %b %Y'),
            "total_sales": daily_data["total"],
            "total_profit": daily_data["profit"],
            "total_refunds": daily_data["refunds"],
        },
        "weekly": {
            "label": f"{start_of_week.strftime('%d %b')} - {end_of_week.strftime('%d %b')}",
            "total_sales": weekly_data["total"],
            "total_profit": weekly_data["profit"],
            "total_refunds": weekly_data["refunds"],
            "breakdown": weekly_breakdown,
        },
        "monthly": {
            "label": f"{calendar.month_name[month]} {year}",
            "total_sales": monthly_data["total"],
            "total_profit": monthly_data["profit"],
            "total_refunds": monthly_data["refunds"],
            "breakdown": monthly_breakdown,
        },
        "payments": {
            "cash": round(payment_summary["cash"], 2),
            "card": round(payment_summary["card"], 2),
            "refunds": round(payment_summary["refunds"], 2),
        },
        "top_products": list(top_products),
    }
