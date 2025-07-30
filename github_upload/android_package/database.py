import os
import sqlite3
import json
import datetime
import requests
from kivy.utils import platform

class DatabaseManager:
    """数据库管理类，负责处理数据的存储、检索和同步"""
    
    def __init__(self):
        """初始化数据库连接"""
        # 根据平台确定数据库路径
        if platform == 'android':
            from android.storage import app_storage_path
            db_dir = app_storage_path()
        else:
            db_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.db_path = os.path.join(db_dir, 'expiry_tracker.db')
        
        # 创建数据库连接
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # 使查询结果可以通过列名访问
        
        # 初始化数据库表
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        cursor = self.conn.cursor()
        
        # 创建产品表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            barcode TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            shelf_life INTEGER NOT NULL,
            return_days INTEGER NOT NULL DEFAULT 7
        )
        ''')
        
        # 创建产品记录表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT NOT NULL,
            name TEXT NOT NULL,
            production_date TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            days_remaining INTEGER NOT NULL,
            scan_date TEXT NOT NULL,
            synced INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (barcode) REFERENCES products (barcode)
        )
        ''')
        
        # 创建设置表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        ''')
        
        # 初始化默认设置
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
                      ('default_return_days', '7'))
        
        self.conn.commit()
    
    def add_product(self, barcode, name, shelf_life, return_days):
        """添加新产品
        
        Args:
            barcode: 产品条码
            name: 产品名称
            shelf_life: 保质期（天数）
            return_days: 退货期限（天数）
        
        Returns:
            bool: 是否添加成功
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO products (barcode, name, shelf_life, return_days) VALUES (?, ?, ?, ?)",
                (barcode, name, shelf_life, return_days)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"添加产品失败: {str(e)}")
            return False
    
    def get_product(self, barcode):
        """获取产品信息
        
        Args:
            barcode: 产品条码
        
        Returns:
            dict: 产品信息，如果不存在则返回None
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM products WHERE barcode = ?", (barcode,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        return None
    
    def add_product_record(self, barcode, name, production_date=None, expiry_date=None, days_remaining=None, shelf_life=None, return_days=None):
        """添加产品记录
        
        Args:
            barcode: 产品条码
            name: 产品名称
            production_date: 生产日期（datetime.date对象或字符串）
            expiry_date: 过期日期（datetime.date对象或字符串）
            days_remaining: 剩余天数
            shelf_life: 保质期天数
            return_days: 退货期限天数
        
        Returns:
            bool: 是否添加成功
        """
        try:
            cursor = self.conn.cursor()
            scan_date = datetime.datetime.now().strftime('%Y-%m-%d')
            
            # 处理日期格式
            if isinstance(production_date, datetime.date):
                production_date = production_date.strftime('%Y-%m-%d')
            elif production_date and production_date.strip() == '':
                production_date = None
            
            if isinstance(expiry_date, datetime.date):
                expiry_date = expiry_date.strftime('%Y-%m-%d')
            elif expiry_date and expiry_date.strip() == '':
                expiry_date = None
            
            # 如果没有提供剩余天数，尝试计算
            if days_remaining is None and expiry_date:
                try:
                    if isinstance(expiry_date, str):
                        expiry_dt = datetime.datetime.strptime(expiry_date, '%Y-%m-%d').date()
                    else:
                        expiry_dt = expiry_date
                    
                    today = datetime.date.today()
                    days_remaining = (expiry_dt - today).days
                except:
                    days_remaining = 0
            
            # 检查产品是否已存在
            cursor.execute("SELECT id FROM product_records WHERE barcode = ? AND name = ?", (barcode, name))
            existing = cursor.fetchone()
            
            if existing:
                # 更新现有记录
                cursor.execute(
                    """UPDATE product_records 
                       SET production_date = ?, expiry_date = ?, days_remaining = ?, scan_date = ?, synced = 0
                       WHERE barcode = ? AND name = ?""",
                    (production_date, expiry_date, days_remaining, scan_date, barcode, name)
                )
            else:
                # 插入新记录
                cursor.execute(
                    """INSERT INTO product_records 
                       (barcode, name, production_date, expiry_date, days_remaining, scan_date, synced) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (barcode, name, production_date, expiry_date, days_remaining, scan_date, 0)
                )
            
            # 如果提供了产品信息，也更新products表
            if shelf_life is not None or return_days is not None:
                cursor.execute("SELECT id FROM products WHERE barcode = ?", (barcode,))
                product_exists = cursor.fetchone()
                
                if product_exists:
                    update_fields = []
                    update_values = []
                    
                    if shelf_life is not None:
                        update_fields.append("shelf_life = ?")
                        update_values.append(shelf_life)
                    
                    if return_days is not None:
                        update_fields.append("return_days = ?")
                        update_values.append(return_days)
                    
                    if update_fields:
                        update_values.append(barcode)
                        cursor.execute(
                            f"UPDATE products SET {', '.join(update_fields)} WHERE barcode = ?",
                            update_values
                        )
                else:
                    cursor.execute(
                        """INSERT INTO products (barcode, name, shelf_life, return_days) 
                           VALUES (?, ?, ?, ?)""",
                        (barcode, name, shelf_life or 0, return_days or 0)
                    )
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"添加产品记录失败: {str(e)}")
            return False
    
    def get_all_products(self, sort_by='days_remaining'):
        """获取所有产品记录
        
        Args:
            sort_by: 排序方式，可选值：'days_remaining', 'name', 'expiry_date', 'scan_date'
        
        Returns:
            list: 产品记录列表
        """
        cursor = self.conn.cursor()
        
        # 先更新所有记录的剩余天数
        self._update_days_remaining()
        
        # 构建排序SQL
        sort_sql = {
            'days_remaining': 'ORDER BY days_remaining ASC',
            'name': 'ORDER BY name ASC', 
            'expiry_date': 'ORDER BY expiry_date ASC',
            'scan_date': 'ORDER BY scan_date DESC'
        }.get(sort_by, 'ORDER BY days_remaining ASC')
        
        cursor.execute(f"SELECT * FROM product_records {sort_sql}")
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def _update_days_remaining(self):
        """更新所有记录的剩余天数"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE product_records 
            SET days_remaining = CAST(
                (julianday(expiry_date) - julianday('now')) AS INTEGER
            )
        """)
        self.conn.commit()
    
    def get_statistics(self):
        """获取统计信息
        
        Returns:
            dict: 包含总数、即将过期、已过期等统计信息
        """
        self._update_days_remaining()
        
        cursor = self.conn.cursor()
        
        # 总产品数
        cursor.execute("SELECT COUNT(*) FROM product_records")
        total = cursor.fetchone()[0]
        
        # 即将过期（7天内）
        cursor.execute("SELECT COUNT(*) FROM product_records WHERE days_remaining <= 7 AND days_remaining > 0")
        expiring_soon = cursor.fetchone()[0]
        
        # 已过期
        cursor.execute("SELECT COUNT(*) FROM product_records WHERE days_remaining <= 0")
        expired = cursor.fetchone()[0]
        
        return {
            'total': total,
            'expiring_soon': expiring_soon,
            'expired': expired
        }
    
    def filter_products(self, search_text='', status_filter='全部'):
        """筛选产品记录
        
        Args:
            search_text: 搜索文本（产品名称或条码）
            status_filter: 状态筛选（'全部', '正常', '即将过期', '已过期'）
        
        Returns:
            list: 筛选后的产品记录列表
        """
        self._update_days_remaining()
        
        cursor = self.conn.cursor()
        
        # 构建WHERE条件
        where_conditions = []
        params = []
        
        if search_text:
            where_conditions.append("(name LIKE ? OR barcode LIKE ?)")
            params.extend([f"%{search_text}%", f"%{search_text}%"])
        
        if status_filter == '正常':
            where_conditions.append("days_remaining > 7")
        elif status_filter == '即将过期':
            where_conditions.append("days_remaining <= 7 AND days_remaining > 0")
        elif status_filter == '已过期':
            where_conditions.append("days_remaining <= 0")
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        cursor.execute(f"""
            SELECT * FROM product_records 
            WHERE {where_clause}
            ORDER BY days_remaining ASC
        """, params)
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def delete_record(self, record_id):
        """删除产品记录
        
        Args:
            record_id: 记录ID
        
        Returns:
            bool: 是否删除成功
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM product_records WHERE id = ?", (record_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"删除记录失败: {str(e)}")
            return False
    
    def update_record(self, record_id, **kwargs):
        """更新产品记录
        
        Args:
            record_id: 记录ID
            **kwargs: 要更新的字段
        
        Returns:
            bool: 是否更新成功
        """
        try:
            cursor = self.conn.cursor()
            
            # 构建更新语句
            set_clauses = []
            values = []
            
            for key, value in kwargs.items():
                if key in ['name', 'production_date', 'expiry_date', 'days_remaining']:
                    set_clauses.append(f"{key} = ?")
                    values.append(value)
            
            if set_clauses:
                values.append(record_id)
                query = f"UPDATE product_records SET {', '.join(set_clauses)} WHERE id = ?"
                cursor.execute(query, values)
                self.conn.commit()
            
            return True
        except Exception as e:
            print(f"更新记录失败: {str(e)}")
            return False
    
    def export_to_json(self, file_path):
        """导出数据到JSON文件
        
        Args:
            file_path: 导出文件路径
        
        Returns:
            bool: 是否导出成功
        """
        try:
            records = self.get_all_products()
            statistics = self.get_statistics()
            
            export_data = {
                'export_time': datetime.datetime.now().isoformat(),
                'statistics': statistics,
                'records': records
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"导出失败: {str(e)}")
            return False
    
    def get_settings(self):
        """获取应用设置
        
        Returns:
            dict: 设置字典
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        
        settings = {}
        for row in rows:
            key = row['key']
            value = row['value']
            
            # 尝试转换数值类型
            try:
                if value.isdigit():
                    value = int(value)
            except (ValueError, AttributeError):
                pass
            
            settings[key] = value
        
        return settings
    
    def get_setting(self, key, default_value=None):
        """获取单个设置
        
        Args:
            key: 设置键
            default_value: 默认值
        
        Returns:
            设置值或默认值
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
            result = cursor.fetchone()
            if result:
                return result[0]
            return default_value
        except Exception as e:
            print(f"获取设置失败: {str(e)}")
            return default_value
    
    def save_setting(self, key, value):
        """保存单个设置"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
                (key, str(value))
            )
            self.conn.commit()
            Logger.info(f"设置 {key} 保存成功")
            return True
        except Exception as e:
            Logger.error(f"保存设置失败: {e}")
            return False
    
    def save_settings(self, settings):
        """保存应用设置
        
        Args:
            settings: 设置字典
        
        Returns:
            bool: 是否保存成功
        """
        try:
            cursor = self.conn.cursor()
            
            for key, value in settings.items():
                # 将所有值转换为字符串
                value_str = str(value)
                
                cursor.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (key, value_str)
                )
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"保存设置失败: {str(e)}")
            return False
    
    def sync_data(self, server_address):
        """同步数据到服务器
        
        Args:
            server_address: 服务器地址
        
        Returns:
            bool: 是否同步成功
        """
        try:
            # 获取未同步的记录
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM product_records WHERE synced = 0")
            rows = cursor.fetchall()
            
            if not rows:
                return True  # 没有需要同步的数据
            
            # 准备同步数据
            sync_data = [dict(row) for row in rows]
            
            # 发送数据到服务器
            response = requests.post(
                f"{server_address}/api/sync",
                json={
                    'records': sync_data
                },
                timeout=10  # 10秒超时
            )
            
            if response.status_code == 200:
                # 更新同步状态
                for row in rows:
                    cursor.execute(
                        "UPDATE product_records SET synced = 1 WHERE id = ?",
                        (row['id'],)
                    )
                
                self.conn.commit()
                return True
            else:
                print(f"同步失败，服务器返回: {response.status_code}")
                return False
        except Exception as e:
            print(f"同步数据失败: {str(e)}")
            return False
    
    def clear_all_data(self):
        """清空所有数据"""
        try:
            cursor = self.conn.cursor()
            
            # 清空所有表的数据
            cursor.execute('DELETE FROM product_records')
            cursor.execute('DELETE FROM products')
            # 保留设置表，只清空产品相关数据
            
            self.conn.commit()
            Logger.info("所有产品数据已清空")
            return True
            
        except Exception as e:
            Logger.error(f"清空数据失败: {e}")
            return False
    
    def get_database_stats(self):
        """获取数据库统计信息"""
        try:
            cursor = self.conn.cursor()
            
            # 获取产品数量
            cursor.execute('SELECT COUNT(*) FROM products')
            product_count = cursor.fetchone()[0]
            
            # 获取记录数量
            cursor.execute('SELECT COUNT(*) FROM product_records')
            record_count = cursor.fetchone()[0]
            
            # 获取数据库文件大小
            import os
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            
            return {
                'product_count': product_count,
                'record_count': record_count,
                'db_size_mb': round(db_size / (1024 * 1024), 2)
            }
            
        except Exception as e:
            Logger.error(f"获取数据库统计失败: {e}")
            return {'product_count': 0, 'record_count': 0, 'db_size_mb': 0}
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()