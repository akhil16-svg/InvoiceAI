"""
User-specific database for storing invoices
Each user has their own separate invoice storage
"""

import json
import os
from typing import List, Dict, Optional, Any
from datetime import datetime
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor

class InvoiceDatabase:
    """
    Database for invoice storage with user separation
    Supports JSON (simple), SQLite, and PostgreSQL (scalable) backends
    """
    
    def __init__(self, user_email: str = None, db_type: str = 'json', db_path: str = None):
        """
        Initialize database for specific user
        
        Args:
            user_email: User's email (used for data separation)
            db_type: 'json', 'sqlite', or 'postgres'
            db_path: Custom path (optional, auto-generated if None)
        """
        self.user_email = user_email
        self.db_type = db_type
        
        # Generate user-specific path (for json and sqlite)
        if db_path:
            self.db_path = db_path
        elif user_email:
            # Each user gets their own folder
            safe_email = user_email.replace('@', '_at_').replace('.', '_')
            self.db_path = f'data/users/{safe_email}/invoices.{db_type}'
        else:
            # Fallback to shared database
            self.db_path = f'data/invoices.{db_type}'
            
        self.pg_url = os.environ.get("DATABASE_URL")
        
        # Initialize database
        if db_type == 'json':
            self._init_json()
        elif db_type == 'sqlite':
            self._init_sqlite()
        elif db_type == 'postgres':
            if not self.pg_url:
                raise ValueError("DATABASE_URL environment variable is missing for PostgreSQL.")
            self._init_postgres()
    
    def _init_json(self):
        """Initialize JSON file storage"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if not os.path.exists(self.db_path):
            with open(self.db_path, 'w') as f:
                json.dump([], f)
    
    def _init_sqlite(self):
        """Initialize SQLite database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE,
                vendor_name TEXT,
                date TEXT,
                total_amount REAL,
                currency TEXT,
                tax_amount REAL,
                subtotal REAL,
                payment_method TEXT,
                fraud_flags TEXT,
                raw_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_email TEXT
            )
        ''')
        
        # Create indexes for faster queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_vendor ON invoices(vendor_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON invoices(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user ON invoices(user_email)')
        
        conn.commit()
        conn.close()

    def _init_postgres(self):
        """Initialize Postgres database"""
        conn = psycopg2.connect(self.pg_url)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id SERIAL PRIMARY KEY,
                invoice_number TEXT UNIQUE,
                vendor_name TEXT,
                date TEXT,
                total_amount REAL,
                currency TEXT,
                tax_amount REAL,
                subtotal REAL,
                payment_method TEXT,
                fraud_flags TEXT,
                raw_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_email TEXT
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pg_vendor ON invoices(vendor_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pg_date ON invoices(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pg_user ON invoices(user_email)')
        
        conn.commit()
        cursor.close()
        conn.close()
    
    def save_invoice(self, invoice_data: Dict[str, Any]) -> bool:
        """
        Save invoice to database
        
        Args:
            invoice_data: Parsed invoice dictionary
            
        Returns:
            Success boolean
        """
        try:
            # Add user email to invoice data
            if self.user_email:
                invoice_data['user_email'] = self.user_email
            
            if self.db_type == 'json':
                return self._save_to_json(invoice_data)
            elif self.db_type == 'sqlite':
                return self._save_to_sqlite(invoice_data)
            elif self.db_type == 'postgres':
                return self._save_to_postgres(invoice_data)
        except Exception as e:
            print(f"Error saving invoice: {e}")
            return False
    
    def _save_to_json(self, invoice_data: Dict) -> bool:
        """Save to JSON file"""
        with open(self.db_path, 'r') as f:
            invoices = json.load(f)
        
        # Add timestamp
        invoice_data['saved_at'] = datetime.now().isoformat()
        
        # Check for duplicates by invoice number
        invoice_number = invoice_data.get('invoice_number')
        if invoice_number:
            # Remove existing invoice with same number
            invoices = [inv for inv in invoices 
                       if inv.get('invoice_number') != invoice_number]
        
        # Add new invoice
        invoices.append(invoice_data)
        
        with open(self.db_path, 'w') as f:
            json.dump(invoices, f, indent=2)
        
        return True
    
    def _save_to_sqlite(self, invoice_data: Dict) -> bool:
        """Save to SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO invoices 
                (invoice_number, vendor_name, date, total_amount, currency, 
                 tax_amount, subtotal, payment_method, fraud_flags, raw_data, user_email)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                invoice_data.get('invoice_number'),
                invoice_data.get('vendor_name'),
                invoice_data.get('date'),
                invoice_data.get('total_amount'),
                invoice_data.get('currency'),
                invoice_data.get('tax_amount'),
                invoice_data.get('subtotal'),
                invoice_data.get('payment_method'),
                json.dumps(invoice_data.get('fraud_flags', [])),
                json.dumps(invoice_data),
                self.user_email
            ))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"SQLite error: {e}")
            return False
        finally:
            conn.close()

    def _save_to_postgres(self, invoice_data: Dict) -> bool:
        """Save to Postgres database"""
        conn = psycopg2.connect(self.pg_url)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO invoices 
                (invoice_number, vendor_name, date, total_amount, currency, 
                 tax_amount, subtotal, payment_method, fraud_flags, raw_data, user_email)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (invoice_number) DO UPDATE SET
                    vendor_name = EXCLUDED.vendor_name,
                    date = EXCLUDED.date,
                    total_amount = EXCLUDED.total_amount,
                    currency = EXCLUDED.currency,
                    tax_amount = EXCLUDED.tax_amount,
                    subtotal = EXCLUDED.subtotal,
                    payment_method = EXCLUDED.payment_method,
                    fraud_flags = EXCLUDED.fraud_flags,
                    raw_data = EXCLUDED.raw_data,
                    user_email = EXCLUDED.user_email
            ''', (
                invoice_data.get('invoice_number'),
                invoice_data.get('vendor_name'),
                invoice_data.get('date'),
                invoice_data.get('total_amount'),
                invoice_data.get('currency'),
                invoice_data.get('tax_amount'),
                invoice_data.get('subtotal'),
                invoice_data.get('payment_method'),
                json.dumps(invoice_data.get('fraud_flags', [])),
                json.dumps(invoice_data),
                self.user_email
            ))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Postgres error: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    
    def get_all_invoices(self) -> List[Dict]:
        """Get all invoices for current user"""
        if self.db_type == 'json':
            return self._get_all_from_json()
        elif self.db_type == 'sqlite':
            return self._get_all_from_sqlite()
        elif self.db_type == 'postgres':
            return self._get_all_from_postgres()
        return []
    
    def _get_all_from_json(self) -> List[Dict]:
        """Get all from JSON file"""
        try:
            with open(self.db_path, 'r') as f:
                invoices = json.load(f)
            
            # Filter by user email if specified
            if self.user_email:
                invoices = [inv for inv in invoices 
                           if inv.get('user_email') == self.user_email]
            
            return invoices
        except:
            return []
    
    def _get_all_from_sqlite(self) -> List[Dict]:
        """Get all from SQLite"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if self.user_email:
            cursor.execute('SELECT raw_data FROM invoices WHERE user_email = ? ORDER BY created_at DESC', 
                          (self.user_email,))
        else:
            cursor.execute('SELECT raw_data FROM invoices ORDER BY created_at DESC')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [json.loads(row[0]) for row in rows]

    def _get_all_from_postgres(self) -> List[Dict]:
        """Get all from Postgres"""
        conn = psycopg2.connect(self.pg_url)
        cursor = conn.cursor()
        
        try:
            if self.user_email:
                cursor.execute('SELECT raw_data FROM invoices WHERE user_email = %s ORDER BY created_at DESC', 
                              (self.user_email,))
            else:
                cursor.execute('SELECT raw_data FROM invoices ORDER BY created_at DESC')
            
            rows = cursor.fetchall()
            return [json.loads(row[0]) for row in rows]
        except Exception as e:
            print(f"Postgres error getting invoices: {e}")
            return []
        finally:
            cursor.close()
            conn.close()
    
    def get_invoice_by_number(self, invoice_number: str) -> Optional[Dict]:
        """Get specific invoice by number"""
        invoices = self.get_all_invoices()
        for inv in invoices:
            if inv.get('invoice_number') == invoice_number:
                return inv
        return None
    
    def delete_invoice(self, invoice_number: str) -> bool:
        """Delete invoice by number"""
        if self.db_type == 'json':
            return self._delete_from_json(invoice_number)
        elif self.db_type == 'sqlite':
            return self._delete_from_sqlite(invoice_number)
        elif self.db_type == 'postgres':
            return self._delete_from_postgres(invoice_number)
        return False
    
    def _delete_from_json(self, invoice_number: str) -> bool:
        """Delete from JSON file"""
        with open(self.db_path, 'r') as f:
            invoices = json.load(f)
        
        original_count = len(invoices)
        
        # Filter out invoice and ensure user owns it
        invoices = [inv for inv in invoices 
                   if not (inv.get('invoice_number') == invoice_number and 
                          inv.get('user_email') == self.user_email)]
        
        with open(self.db_path, 'w') as f:
            json.dump(invoices, f, indent=2)
        
        return len(invoices) < original_count
    
    def _delete_from_sqlite(self, invoice_number: str) -> bool:
        """Delete from SQLite"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if self.user_email:
            cursor.execute('DELETE FROM invoices WHERE invoice_number = ? AND user_email = ?', 
                          (invoice_number, self.user_email))
        else:
            cursor.execute('DELETE FROM invoices WHERE invoice_number = ?', (invoice_number,))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted

    def _delete_from_postgres(self, invoice_number: str) -> bool:
        """Delete from Postgres"""
        conn = psycopg2.connect(self.pg_url)
        cursor = conn.cursor()
        try:
            if self.user_email:
                cursor.execute('DELETE FROM invoices WHERE invoice_number = %s AND user_email = %s', 
                              (invoice_number, self.user_email))
            else:
                cursor.execute('DELETE FROM invoices WHERE invoice_number = %s', (invoice_number,))
            
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted
        finally:
            cursor.close()
            conn.close()
    
    def get_invoice_count(self) -> int:
        """Get total number of invoices for user"""
        return len(self.get_all_invoices())
    
    def clear_all(self) -> bool:
        """Clear all invoices for current user"""
        if self.db_type == 'json':
            # Only clear current user's invoices
            with open(self.db_path, 'r') as f:
                invoices = json.load(f)
            
            if self.user_email:
                invoices = [inv for inv in invoices 
                           if inv.get('user_email') != self.user_email]
            else:
                invoices = []
            
            with open(self.db_path, 'w') as f:
                json.dump(invoices, f)
            return True
            
        elif self.db_type == 'sqlite':
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if self.user_email:
                cursor.execute('DELETE FROM invoices WHERE user_email = ?', (self.user_email,))
            else:
                cursor.execute('DELETE FROM invoices')
            
            conn.commit()
            conn.close()
            return True
            
        elif self.db_type == 'postgres':
            conn = psycopg2.connect(self.pg_url)
            cursor = conn.cursor()
            try:
                if self.user_email:
                    cursor.execute('DELETE FROM invoices WHERE user_email = %s', (self.user_email,))
                else:
                    cursor.execute('DELETE FROM invoices')
                
                conn.commit()
                return True
            finally:
                cursor.close()
                conn.close()
        
        return False
    
    def get_storage_info(self) -> Dict[str, Any]:
        """Get storage statistics"""
        invoices = self.get_all_invoices()
        
        total_amount = sum(inv.get('total_amount', 0) or 0 for inv in invoices)
        
        # Calculate storage size
        if self.db_type == 'json':
            try:
                size_bytes = os.path.getsize(self.db_path)
                size_mb = size_bytes / (1024 * 1024)
            except:
                size_mb = 0
        elif self.db_type == 'sqlite':
            try:
                size_bytes = os.path.getsize(self.db_path)
                size_mb = size_bytes / (1024 * 1024)
            except:
                size_mb = 0
        elif self.db_type == 'postgres':
            # We skip accurate size for Postgres to avoid unnecessary queries,
            # or we could query pg_database_size. We'll default to 0 for this demo.
            size_mb = 0
            
        return {
            'total_invoices': len(invoices),
            'total_amount': total_amount,
            'storage_mb': round(size_mb, 2),
            'storage_type': self.db_type,
            'user_email': self.user_email
        }