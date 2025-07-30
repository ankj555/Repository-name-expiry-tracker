#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电脑端数据接收服务器
用于接收手机端同步的产品数据，并提供Web界面查看
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string, send_file
from werkzeug.serving import run_simple
import threading
import webbrowser
from io import BytesIO
import csv

app = Flask(__name__)

class DesktopDataManager:
    """电脑端数据管理器"""
    
    def __init__(self, db_path="desktop_products.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建产品记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT NOT NULL,
                name TEXT NOT NULL,
                production_date DATE NOT NULL,
                expiry_date DATE NOT NULL,
                days_remaining INTEGER NOT NULL,
                scan_date TIMESTAMP NOT NULL,
                sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                device_id TEXT DEFAULT 'mobile'
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_records(self, records):
        """批量添加记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            for record in records:
                # 计算当前剩余天数
                expiry_date = datetime.strptime(record['expiry_date'], '%Y-%m-%d')
                days_remaining = (expiry_date - datetime.now()).days
                
                cursor.execute('''
                    INSERT OR REPLACE INTO product_records 
                    (barcode, name, production_date, expiry_date, days_remaining, scan_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    record['barcode'],
                    record['name'],
                    record['production_date'],
                    record['expiry_date'],
                    days_remaining,
                    record['scan_date']
                ))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"添加记录失败: {e}")
            return False
        finally:
            conn.close()
    
    def get_all_records(self, sort_by='days_remaining', search_text='', status_filter='全部'):
        """获取所有记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 更新剩余天数
        cursor.execute('''
            UPDATE product_records 
            SET days_remaining = CAST(
                (julianday(expiry_date) - julianday('now')) AS INTEGER
            )
        ''')
        
        # 构建查询条件
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
        
        # 排序映射
        sort_map = {
            '剩余天数': 'days_remaining ASC',
            '产品名称': 'name ASC',
            '过期日期': 'expiry_date ASC',
            '添加时间': 'scan_date DESC'
        }
        
        order_clause = sort_map.get(sort_by, 'days_remaining ASC')
        
        cursor.execute(f'''
            SELECT * FROM product_records 
            WHERE {where_clause}
            ORDER BY {order_clause}
        ''', params)
        
        results = cursor.fetchall()
        conn.close()
        
        records = []
        for row in results:
            records.append({
                'id': row[0],
                'barcode': row[1],
                'name': row[2],
                'production_date': row[3],
                'expiry_date': row[4],
                'days_remaining': row[5],
                'scan_date': row[6],
                'sync_time': row[7],
                'device_id': row[8]
            })
        
        return records
    
    def get_statistics(self):
        """获取统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 更新剩余天数
        cursor.execute('''
            UPDATE product_records 
            SET days_remaining = CAST(
                (julianday(expiry_date) - julianday('now')) AS INTEGER
            )
        ''')
        
        # 总产品数
        cursor.execute('SELECT COUNT(*) FROM product_records')
        total = cursor.fetchone()[0]
        
        # 即将过期（7天内）
        cursor.execute('SELECT COUNT(*) FROM product_records WHERE days_remaining <= 7 AND days_remaining > 0')
        expiring_soon = cursor.fetchone()[0]
        
        # 已过期
        cursor.execute('SELECT COUNT(*) FROM product_records WHERE days_remaining <= 0')
        expired = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total': total,
            'expiring_soon': expiring_soon,
            'expired': expired
        }
    
    def delete_record(self, record_id):
        """删除记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM product_records WHERE id = ?', (record_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"删除记录失败: {e}")
            return False
        finally:
            conn.close()
    
    def export_to_csv(self):
        """导出为CSV文件"""
        records = self.get_all_records()
        
        output = BytesIO()
        output.write('\ufeff'.encode('utf-8'))  # BOM for Excel
        
        fieldnames = ['产品名称', '条码', '生产日期', '过期日期', '剩余天数', '扫描日期', '同步时间']
        
        csv_content = []
        csv_content.append(','.join(fieldnames))
        
        for record in records:
            row = [
                record['name'],
                record['barcode'],
                record['production_date'],
                record['expiry_date'],
                str(record['days_remaining']),
                record['scan_date'],
                record['sync_time']
            ]
            csv_content.append(','.join([f'"{field}"' for field in row]))
        
        output.write('\n'.join(csv_content).encode('utf-8'))
        output.seek(0)
        
        return output

# 全局数据管理器实例
data_manager = DesktopDataManager()

# Web界面HTML模板
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>产品数据管理中心</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .stats {
            display: flex;
            justify-content: space-around;
            margin-top: 20px;
        }
        
        .stat-item {
            text-align: center;
            padding: 15px;
            background: rgba(255,255,255,0.2);
            border-radius: 10px;
            min-width: 120px;
        }
        
        .stat-number {
            font-size: 2em;
            font-weight: bold;
            display: block;
        }
        
        .controls {
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
        }
        
        .control-row {
            display: flex;
            gap: 20px;
            align-items: center;
            flex-wrap: wrap;
        }
        
        .control-group {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        input, select, button {
            padding: 10px 15px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
        }
        
        input:focus, select:focus {
            outline: none;
            border-color: #4facfe;
        }
        
        button {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            border: none;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        button:hover {
            transform: translateY(-2px);
        }
        
        .export-btn {
            background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
        }
        
        .table-container {
            padding: 30px;
            overflow-x: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        
        th, td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        
        th {
            background: #f8f9fa;
            font-weight: bold;
            color: #495057;
        }
        
        tr:hover {
            background: #f8f9fa;
        }
        
        .status-normal {
            color: #28a745;
            font-weight: bold;
        }
        
        .status-warning {
            color: #ffc107;
            font-weight: bold;
        }
        
        .status-danger {
            color: #dc3545;
            font-weight: bold;
        }
        
        .delete-btn {
            background: #dc3545;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 12px;
        }
        
        .delete-btn:hover {
            background: #c82333;
        }
        
        .no-data {
            text-align: center;
            padding: 50px;
            color: #6c757d;
            font-size: 1.2em;
        }
        
        @media (max-width: 768px) {
            .control-row {
                flex-direction: column;
                align-items: stretch;
            }
            
            .stats {
                flex-direction: column;
                gap: 10px;
            }
            
            .header h1 {
                font-size: 1.8em;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 产品数据管理中心</h1>
            <p>实时监控产品保质期状态</p>
            <div class="stats">
                <div class="stat-item">
                    <span class="stat-number" id="total-count">{{ statistics.total }}</span>
                    <span>总产品</span>
                </div>
                <div class="stat-item">
                    <span class="stat-number" id="expiring-count">{{ statistics.expiring_soon }}</span>
                    <span>即将过期</span>
                </div>
                <div class="stat-item">
                    <span class="stat-number" id="expired-count">{{ statistics.expired }}</span>
                    <span>已过期</span>
                </div>
            </div>
        </div>
        
        <div class="controls">
            <div class="control-row">
                <div class="control-group">
                    <label>搜索:</label>
                    <input type="text" id="search-input" placeholder="产品名称或条码..." onkeyup="filterData()">
                </div>
                
                <div class="control-group">
                    <label>状态:</label>
                    <select id="status-filter" onchange="filterData()">
                        <option value="全部">全部</option>
                        <option value="正常">正常</option>
                        <option value="即将过期">即将过期</option>
                        <option value="已过期">已过期</option>
                    </select>
                </div>
                
                <div class="control-group">
                    <label>排序:</label>
                    <select id="sort-select" onchange="filterData()">
                        <option value="剩余天数">剩余天数</option>
                        <option value="产品名称">产品名称</option>
                        <option value="过期日期">过期日期</option>
                        <option value="添加时间">添加时间</option>
                    </select>
                </div>
                
                <button onclick="refreshData()">🔄 刷新</button>
                <button class="export-btn" onclick="exportData()">📊 导出CSV</button>
            </div>
        </div>
        
        <div class="table-container">
            <div id="loading" style="text-align: center; padding: 50px; display: none;">
                <p>加载中...</p>
            </div>
            
            <table id="data-table">
                <thead>
                    <tr>
                        <th>产品名称</th>
                        <th>条码</th>
                        <th>生产日期</th>
                        <th>过期日期</th>
                        <th>剩余天数</th>
                        <th>扫描日期</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody id="table-body">
                    {% for record in records %}
                    <tr>
                        <td><strong>{{ record.name }}</strong></td>
                        <td>{{ record.barcode }}</td>
                        <td>{{ record.production_date }}</td>
                        <td>{{ record.expiry_date }}</td>
                        <td>
                            <span class="{% if record.days_remaining > 7 %}status-normal{% elif record.days_remaining > 0 %}status-warning{% else %}status-danger{% endif %}">
                                {{ record.days_remaining }}天
                            </span>
                        </td>
                        <td>{{ record.scan_date }}</td>
                        <td>
                            <button class="delete-btn" onclick="deleteRecord({{ record.id }})">删除</button>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            
            {% if not records %}
            <div class="no-data">
                <p>📱 暂无数据</p>
                <p>请使用手机端扫描产品并同步数据</p>
            </div>
            {% endif %}
        </div>
    </div>
    
    <script>
        function filterData() {
            const search = document.getElementById('search-input').value;
            const status = document.getElementById('status-filter').value;
            const sort = document.getElementById('sort-select').value;
            
            const params = new URLSearchParams({
                search: search,
                status: status,
                sort: sort
            });
            
            window.location.href = '/?' + params.toString();
        }
        
        function refreshData() {
            window.location.reload();
        }
        
        function exportData() {
            window.open('/export', '_blank');
        }
        
        function deleteRecord(id) {
            if (confirm('确定要删除这条记录吗？')) {
                fetch('/delete/' + id, {
                    method: 'DELETE'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        window.location.reload();
                    } else {
                        alert('删除失败: ' + data.message);
                    }
                })
                .catch(error => {
                    alert('删除失败: ' + error);
                });
            }
        }
        
        // 自动刷新（每30秒）
        setInterval(function() {
            // 只有在没有用户交互时才自动刷新
            if (document.hidden === false) {
                const stats = document.querySelectorAll('.stat-number');
                fetch('/api/statistics')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('total-count').textContent = data.total;
                    document.getElementById('expiring-count').textContent = data.expiring_soon;
                    document.getElementById('expired-count').textContent = data.expired;
                })
                .catch(error => console.log('统计更新失败:', error));
            }
        }, 30000);
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """主页面"""
    search_text = request.args.get('search', '')
    status_filter = request.args.get('status', '全部')
    sort_by = request.args.get('sort', '剩余天数')
    
    records = data_manager.get_all_records(sort_by, search_text, status_filter)
    statistics = data_manager.get_statistics()
    
    return render_template_string(HTML_TEMPLATE, records=records, statistics=statistics)

@app.route('/api/sync', methods=['POST'])
def sync_data():
    """接收手机端同步的数据"""
    try:
        data = request.get_json()
        records = data.get('records', [])
        
        if data_manager.add_records(records):
            return jsonify({
                'success': True,
                'message': f'成功同步 {len(records)} 条记录'
            })
        else:
            return jsonify({
                'success': False,
                'message': '数据同步失败'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'同步失败: {str(e)}'
        }), 500

@app.route('/api/statistics')
def get_statistics():
    """获取统计信息API"""
    return jsonify(data_manager.get_statistics())

@app.route('/delete/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    """删除记录"""
    if data_manager.delete_record(record_id):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': '删除失败'}), 500

@app.route('/export')
def export_data():
    """导出数据为CSV"""
    csv_data = data_manager.export_to_csv()
    
    return send_file(
        csv_data,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'产品数据_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

def open_browser():
    """延迟打开浏览器"""
    import time
    time.sleep(1.5)
    webbrowser.open('http://localhost:8000')

if __name__ == '__main__':
    print("🚀 启动产品数据管理服务器...")
    print("📱 手机端请将服务器地址设置为: http://你的电脑IP:8000")
    print("🌐 电脑端访问地址: http://localhost:8000")
    print("⚠️  请确保手机和电脑在同一局域网内")
    print("\n" + "="*50)
    
    # 在新线程中打开浏览器
    threading.Thread(target=open_browser, daemon=True).start()
    
    # 启动服务器
    try:
        run_simple('0.0.0.0', 8000, app, use_reloader=False, use_debugger=False)
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")