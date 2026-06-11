"""
Analytics functions for invoice data analysis
"""

# --- at top of analytics.py ---
import re
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime, timedelta

_EMPTY_NUMS = {"", ".", "-", "-."}

def _to_float(x):
    if x is None:
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        s = x.strip().replace(",", "")
        s = re.sub(r"[^0-9.\-]", "", s)
        if not s or s in _EMPTY_NUMS:
            return 0.0
        try:
            return float(s)
        except ValueError:
            return 0.0
    try:
        return float(x)
    except Exception:
        return 0.0

def _coerce_amount_series(df, col="total_amount"):
    # Make sure groupbys/sums work even if OCR produced strings or None
    if col not in df.columns:
        df[col] = 0.0
        return df
    df[col] = pd.to_numeric(
        df[col].astype(str).str.replace(",", "", regex=False)
                        .str.replace(r"[^0-9.\-]", "", regex=True),
        errors="coerce"
    ).fillna(0.0)
    return df

def calculate_total_spending(invoices: List[Dict]) -> float:
    # Safe against None, strings, currency symbols
    return round(sum(_to_float((inv or {}).get("total_amount")) for inv in (invoices or [])), 2)



def get_spending_by_vendor(invoices: List[Dict]) -> pd.DataFrame:
    df = pd.DataFrame(invoices)
    if df.empty:
        return pd.DataFrame(columns=['vendor_name', 'total_spending'])
    df = _coerce_amount_series(df, "total_amount")
    vendor_totals = df.groupby('vendor_name', dropna=False)['total_amount'].sum().reset_index()
    vendor_totals.columns = ['vendor_name', 'total_spending']
    return vendor_totals.sort_values('total_spending', ascending=False)


def get_spending_over_time(invoices: List[Dict], period: str = 'daily') -> pd.DataFrame:
    df = pd.DataFrame(invoices)
    if df.empty:
        return pd.DataFrame(columns=['date', 'total_amount'])

    df = _coerce_amount_series(df, "total_amount")
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])

    if period == 'daily':
        df_grouped = df.groupby(df['date'].dt.date)['total_amount'].sum().reset_index()
    elif period == 'weekly':
        df['week'] = df['date'].dt.to_period('W')
        df_grouped = df.groupby('week')['total_amount'].sum().reset_index()
        df_grouped['date'] = df_grouped['week'].dt.start_time
    elif period == 'monthly':
        df['month'] = df['date'].dt.to_period('M')
        df_grouped = df.groupby('month')['total_amount'].sum().reset_index()
        df_grouped['date'] = df_grouped['month'].dt.start_time
    else:
        df_grouped = df.groupby(df['date'].dt.date)['total_amount'].sum().reset_index()

    return df_grouped[['date', 'total_amount']]


def get_top_vendors(invoices: List[Dict], top_n: int = 5) -> List[Dict]:
    """Get top N vendors by spending"""
    df = get_spending_by_vendor(invoices)
    top_vendors = df.head(top_n).to_dict('records')
    return top_vendors

def calculate_average_invoice_amount(invoices: List[Dict]) -> float:
    if not invoices:
        return 0.0
    amounts = [_to_float((inv or {}).get("total_amount")) for inv in invoices]
    # if you prefer average over valid invoices only:
    valid = [a for a in amounts if a is not None]
    return round((sum(valid) / (len(valid) if valid else 1)), 2)


def get_fraud_statistics(invoices: List[Dict]) -> Dict[str, Any]:
    """Calculate fraud detection statistics"""
    total_invoices = len(invoices)
    flagged_invoices = [inv for inv in invoices if inv.get('fraud_flags')]
    
    fraud_counts = {}
    for inv in flagged_invoices:
        for flag in inv.get('fraud_flags', []):
            fraud_counts[flag] = fraud_counts.get(flag, 0) + 1
    
    return {
        'total_invoices': total_invoices,
        'flagged_invoices': len(flagged_invoices),
        'fraud_rate': len(flagged_invoices) / total_invoices if total_invoices > 0 else 0,
        'fraud_types': fraud_counts
    }

def get_spending_by_category(invoices: List[Dict]) -> pd.DataFrame:
    df = pd.DataFrame(invoices)
    if df.empty:
        return pd.DataFrame(columns=['category', 'total_amount'])
    df = _coerce_amount_series(df, "total_amount")
    # ... keep your existing categorize_invoice logic, then:
    category_totals = df.groupby('category', dropna=False)['total_amount'].sum().reset_index()
    return category_totals.sort_values('total_amount', ascending=False)

    
    df = pd.DataFrame(invoices)
    if df.empty:
        return pd.DataFrame(columns=['category', 'total_amount'])
    
    df['category'] = df.apply(
        lambda row: categorize_invoice(row.get('vendor_name', ''), row.get('items', [])),
        axis=1
    )
    
    category_totals = df.groupby('category')['total_amount'].sum().reset_index()
    return category_totals.sort_values('total_amount', ascending=False)

def get_date_range_invoices(invoices: List[Dict], start_date: str = None, end_date: str = None) -> List[Dict]:
    """Filter invoices by date range"""
    filtered = []
    
    for inv in invoices:
        if not inv.get('date'):
            continue
        
        try:
            inv_date = datetime.strptime(inv['date'], '%Y-%m-%d')
            
            if start_date:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                if inv_date < start:
                    continue
            
            if end_date:
                end = datetime.strptime(end_date, '%Y-%m-%d')
                if inv_date > end:
                    continue
            
            filtered.append(inv)
        except:
            continue
    
    return filtered

def get_monthly_comparison(invoices: List[Dict]) -> pd.DataFrame:
    """Compare spending month-over-month"""
    df = pd.DataFrame(invoices)
    if df.empty:
        return pd.DataFrame()
    
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    df['month'] = df['date'].dt.to_period('M')
    
    monthly = df.groupby('month')['total_amount'].agg(['sum', 'count', 'mean']).reset_index()
    monthly.columns = ['month', 'total', 'invoice_count', 'average']
    monthly['month_str'] = monthly['month'].dt.strftime('%Y-%m')
    
    # Calculate month-over-month change
    monthly['previous_month_total'] = monthly['total'].shift(1)
    monthly['change_pct'] = ((monthly['total'] - monthly['previous_month_total']) / monthly['previous_month_total'] * 100).round(2)
    
    return monthly[['month_str', 'total', 'invoice_count', 'average', 'change_pct']]
