import os
import sqlite3
import datetime
import requests
import threading
import json
import csv
import pandas as pd
from tkinter import filedialog
import tkinter as tk
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.properties import StringProperty, NumericProperty, ListProperty, ObjectProperty
from kivy.utils import platform
from kivy.resources import resource_add_path
from kivy.core.text import LabelBase

# 注册中文字体
try:
    LabelBase.register(name='Chinese', fn_regular='C:/Windows/Fonts/msyh.ttc')
except:
    try:
        LabelBase.register(name='Chinese', fn_regular='C:/Windows/Fonts/simsun.ttc')
    except:
        pass  # 如果字体不可用，使用默认字体

# 导入自定义模块
from database import DatabaseManager
from barcode_scanner import BarcodeScanner
from date_recognizer import DateRecognizer
from product_manager import ProductManager

# OCRProcessor别名，使用DateRecognizer
OCRProcessor = DateRecognizer

# 设置窗口大小（仅在桌面平台上有效）
if platform != 'android':
    Window.size = (400, 700)

# 加载KV设计文件
Builder.load_file('design.kv')

class HomeScreen(Screen):
    """主屏幕，显示应用程序的主要功能按钮"""
    def __init__(self, **kwargs):
        super(HomeScreen, self).__init__(**kwargs)

class ScanScreen(Screen):
    """条码扫描屏幕"""
    def __init__(self, **kwargs):
        super(ScanScreen, self).__init__(**kwargs)
        self.barcode_scanner = BarcodeScanner()
        self.ocr_processor = OCRProcessor()
    
    def on_enter(self):
        """进入屏幕时启动相机"""
        if platform == 'android':
            self.start_camera()
    
    def start_camera(self):
        """启动相机进行条码扫描"""
        self.barcode_scanner.start_camera(callback=self.on_barcode_detected)
    
    def on_barcode_detected(self, barcode):
        """条码检测回调函数"""
        # 获取产品信息
        product_info = App.get_running_app().product_manager.get_product_info(barcode)
        if product_info:
            self.ids.product_name.text = product_info['name']
            self.ids.product_code.text = barcode
            # 切换到日期识别模式
            self.barcode_scanner.stop_camera()
            self.start_date_recognition()
        else:
            # 产品不存在，提示添加新产品
            self.manager.current = 'add_product'
            self.manager.get_screen('add_product').set_barcode(barcode)
    
    def start_date_recognition(self):
        """启动日期识别"""
        self.ocr_processor.start_camera(callback=self.on_date_recognized)
    
    def on_date_recognized(self, date_text):
        """日期识别回调函数"""
        try:
            # 解析日期文本
            production_date = self.ocr_processor.parse_date(date_text)
            # 获取产品保质期
            product_info = App.get_running_app().product_manager.get_product_info(self.ids.product_code.text)
            shelf_life = product_info['shelf_life']
            
            # 计算过期日期
            expiry_date = production_date + datetime.timedelta(days=shelf_life)
            days_remaining = (expiry_date - datetime.datetime.now().date()).days
            
            # 更新UI
            self.ids.production_date.text = production_date.strftime('%Y-%m-%d')
            self.ids.expiry_date.text = expiry_date.strftime('%Y-%m-%d')
            self.ids.days_remaining.text = str(days_remaining)
            
            # 保存记录
            App.get_running_app().db_manager.add_product_record(
                barcode=self.ids.product_code.text,
                name=self.ids.product_name.text,
                production_date=production_date,
                expiry_date=expiry_date,
                days_remaining=days_remaining
            )
            
        except Exception as e:
            # 日期识别失败，提示手动输入
            self.ids.error_label.text = f"日期识别失败: {str(e)}\n请手动输入生产日期"
            self.ids.manual_date_input.opacity = 1

class ProductListScreen(Screen):
    """产品列表屏幕，显示所有扫描过的产品"""
    def __init__(self, **kwargs):
        super(ProductListScreen, self).__init__(**kwargs)
    
    def on_enter(self):
        """进入屏幕时刷新产品列表"""
        self.refresh_product_list()
    
    def refresh_product_list(self, sort_by='days_remaining'):
        """刷新产品列表
        
        Args:
            sort_by: 排序方式，可选值：'days_remaining', 'name', 'expiry_date'
        """
        products = App.get_running_app().db_manager.get_all_products(sort_by=sort_by)
        
        # 清空当前列表
        product_list = self.ids.product_list
        product_list.clear_widgets()
        
        # 添加产品到列表
        for product in products:
            item = ProductListItem(
                product_name=product['name'],
                barcode=product['barcode'],
                expiry_date=product['expiry_date'],
                days_remaining=product['days_remaining']
            )
            product_list.add_widget(item)
    
    def export_to_excel(self):
        """导出产品列表到Excel文件"""
        try:
            # 获取所有产品数据
            products = App.get_running_app().db_manager.get_all_products()
            
            if not products:
                self.show_message("没有产品数据可导出")
                return
            
            # 创建隐藏的tkinter窗口用于文件对话框
            root = tk.Tk()
            root.withdraw()
            
            # 选择保存文件路径
            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel文件", "*.xlsx"), ("CSV文件", "*.csv"), ("所有文件", "*.*")],
                title="导出产品列表"
            )
            
            root.destroy()
            
            if not file_path:
                return
            
            # 准备数据
            data = []
            for product in products:
                data.append({
                    '产品名称': product['name'],
                    '条码': product['barcode'],
                    '生产日期': product.get('production_date', ''),
                    '过期日期': product['expiry_date'],
                    '剩余天数': product['days_remaining'],
                    '保质期(天)': product.get('shelf_life', ''),
                    '退货期限(天)': product.get('return_days', '')
                })
            
            # 创建DataFrame并导出
            df = pd.DataFrame(data)
            
            if file_path.endswith('.csv'):
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
            else:
                df.to_excel(file_path, index=False, engine='openpyxl')
            
            self.show_message(f"导出成功！\n文件保存至: {file_path}")
            
        except Exception as e:
            self.show_message(f"导出失败: {str(e)}")
    
    def import_from_excel(self):
        """从Excel文件导入产品数据"""
        try:
            # 创建隐藏的tkinter窗口用于文件对话框
            root = tk.Tk()
            root.withdraw()
            
            # 选择导入文件
            file_path = filedialog.askopenfilename(
                filetypes=[("Excel文件", "*.xlsx"), ("CSV文件", "*.csv"), ("所有文件", "*.*")],
                title="选择要导入的文件"
            )
            
            root.destroy()
            
            if not file_path:
                return
            
            # 读取文件
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path, encoding='utf-8-sig')
            else:
                df = pd.read_excel(file_path, engine='openpyxl')
            
            # 验证必需的列
            required_columns = ['产品名称', '条码', '过期日期']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                self.show_message(f"文件格式错误，缺少必需的列: {', '.join(missing_columns)}")
                return
            
            # 导入数据
            imported_count = 0
            error_count = 0
            
            for index, row in df.iterrows():
                try:
                    # 准备产品数据
                    product_data = {
                        'name': str(row['产品名称']).strip(),
                        'barcode': str(row['条码']).strip(),
                        'expiry_date': str(row['过期日期']).strip(),
                        'production_date': str(row.get('生产日期', '')).strip(),
                        'shelf_life': int(row.get('保质期(天)', 0)) if pd.notna(row.get('保质期(天)')) else None,
                        'return_days': int(row.get('退货期限(天)', 0)) if pd.notna(row.get('退货期限(天)')) else None
                    }
                    
                    # 验证数据
                    if not product_data['name'] or not product_data['barcode'] or not product_data['expiry_date']:
                        error_count += 1
                        continue
                    
                    # 添加到数据库
                    App.get_running_app().db_manager.add_product_record(
                        barcode=product_data['barcode'],
                        name=product_data['name'],
                        expiry_date=product_data['expiry_date'],
                        production_date=product_data['production_date'],
                        shelf_life=product_data['shelf_life'],
                        return_days=product_data['return_days']
                    )
                    
                    imported_count += 1
                    
                except Exception as e:
                    error_count += 1
                    continue
            
            # 刷新列表
            self.refresh_product_list()
            
            # 显示结果
            message = f"导入完成！\n成功导入: {imported_count} 条\n失败: {error_count} 条"
            self.show_message(message)
            
        except Exception as e:
            self.show_message(f"导入失败: {str(e)}")
    
    def show_message(self, message):
        """显示消息弹窗"""
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text=message, text_size=(300, None), halign='center'))
        
        popup = Popup(
            title='提示',
            content=content,
            size_hint=(0.8, 0.4),
            auto_dismiss=True
        )
        
        close_btn = Button(text='确定', size_hint_y=None, height='40dp')
        close_btn.bind(on_press=popup.dismiss)
        content.add_widget(close_btn)
        
        popup.open()

class ProductListItem(BoxLayout):
    """产品列表项组件"""
    product_name = StringProperty('')
    barcode = StringProperty('')
    expiry_date = StringProperty('')
    days_remaining = NumericProperty(0)
    
    def __init__(self, **kwargs):
        super(ProductListItem, self).__init__(**kwargs)

class AddProductScreen(Screen):
    """添加新产品屏幕"""
    def __init__(self, **kwargs):
        super(AddProductScreen, self).__init__(**kwargs)
    
    def set_barcode(self, barcode):
        """设置条码"""
        self.ids.barcode_input.text = barcode
    
    def add_product(self):
        """添加新产品"""
        barcode = self.ids.barcode_input.text
        name = self.ids.name_input.text
        shelf_life = int(self.ids.shelf_life_input.text)
        return_days = int(self.ids.return_days_input.text)
        
        if not all([barcode, name, shelf_life > 0]):
            self.ids.error_label.text = "请填写所有必填字段"
            return
        
        # 添加产品到数据库
        App.get_running_app().product_manager.add_product(
            barcode=barcode,
            name=name,
            shelf_life=shelf_life,
            return_days=return_days
        )
        
        # 返回扫描页面
        self.manager.current = 'scan'

class SettingsScreen(Screen):
    """设置屏幕"""
    
    def __init__(self, **kwargs):
        super(SettingsScreen, self).__init__(**kwargs)
        Clock.schedule_once(self.load_settings, 0.1)
    
    def load_settings(self, dt):
        """加载设置"""
        app = App.get_running_app()
        
        # 加载服务器地址
        server_url = app.db_manager.get_setting('server_url', 'http://192.168.1.100:8000')
        if hasattr(self.ids, 'server_input'):
            self.ids.server_input.text = server_url
    
    def save_settings(self):
        """保存设置"""
        app = App.get_running_app()
        
        # 保存服务器地址
        if hasattr(self.ids, 'server_input'):
            server_url = self.ids.server_input.text.strip()
            if server_url:
                app.network_manager.update_server_url(server_url)
                self.ids.status_label.text = "设置已保存"
            else:
                self.ids.status_label.text = "请输入有效的服务器地址"
    
    def sync_data(self):
        """同步数据到服务器"""
        app = App.get_running_app()
        
        # 显示同步中状态
        self.ids.status_label.text = "正在同步数据..."
        
        def sync_callback(success, message):
            """同步回调函数"""
            if success:
                self.ids.status_label.text = f"✅ {message}"
            else:
                self.ids.status_label.text = f"❌ {message}"
        
        # 开始同步
        app.network_manager.sync_to_server(sync_callback)
    
    def test_connection(self):
        """测试服务器连接"""
        app = App.get_running_app()
        
        def test_thread():
            try:
                server_url = self.ids.server_input.text.strip() if hasattr(self.ids, 'server_input') else app.network_manager.server_url
                response = requests.get(f"{server_url}/api/statistics", timeout=5)
                
                if response.status_code == 200:
                    Clock.schedule_once(lambda dt: setattr(self.ids.status_label, 'text', '✅ 服务器连接正常'))
                else:
                    Clock.schedule_once(lambda dt: setattr(self.ids.status_label, 'text', f'❌ 服务器响应错误: {response.status_code}'))
            except requests.exceptions.RequestException as e:
                Clock.schedule_once(lambda dt: setattr(self.ids.status_label, 'text', f'❌ 连接失败: {str(e)}'))
            except Exception as e:
                Clock.schedule_once(lambda dt: setattr(self.ids.status_label, 'text', f'❌ 测试失败: {str(e)}'))
        
        self.ids.status_label.text = "正在测试连接..."
        threading.Thread(target=test_thread, daemon=True).start()
    
    def clear_data(self):
        """清空本地数据"""
        def confirm_clear(instance):
            if instance.text == '确认':
                app = App.get_running_app()
                try:
                    success = app.db_manager.clear_all_data()
                    if success:
                        self.ids.status_label.text = "✅ 本地数据已清空"
                        # 刷新其他屏幕的数据
                        if hasattr(app.root, 'get_screen'):
                            try:
                                home_screen = app.root.get_screen('home')
                                if hasattr(home_screen, 'refresh_data'):
                                    home_screen.refresh_data()
                            except:
                                pass
                    else:
                        self.ids.status_label.text = "❌ 清空失败"
                except Exception as e:
                    self.ids.status_label.text = f"❌ 清空失败: {str(e)}"
            popup.dismiss()
        
        # 创建确认对话框
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        content.add_widget(Label(text='确定要清空所有本地数据吗？\n此操作不可恢复！', text_size=(280, None)))
        
        buttons = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=50)
        confirm_btn = Button(text='确认', size_hint_x=0.5)
        cancel_btn = Button(text='取消', size_hint_x=0.5)
        
        confirm_btn.bind(on_press=confirm_clear)
        cancel_btn.bind(on_press=lambda x: popup.dismiss())
        
        buttons.add_widget(confirm_btn)
        buttons.add_widget(cancel_btn)
        content.add_widget(buttons)
        
        popup = Popup(title='确认清空数据', content=content, size_hint=(0.8, 0.4))
        popup.open()

class NetworkManager:
    """网络同步管理器"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        self.server_url = self.db.get_setting('server_url', 'http://192.168.1.100:8000')
    
    def sync_to_server(self, callback=None):
        """同步数据到服务器"""
        def sync_thread():
            try:
                # 获取所有产品记录
                records = self.db.get_all_products()
                
                # 准备同步数据
                sync_data = {
                    'records': [],
                    'device_id': 'mobile_app',
                    'sync_time': datetime.datetime.now().isoformat()
                }
                
                for record in records:
                    sync_data['records'].append({
                        'barcode': record['barcode'],
                        'name': record['name'],
                        'production_date': record['production_date'],
                        'expiry_date': record['expiry_date'],
                        'days_remaining': record['days_remaining'],
                        'scan_date': record['scan_date']
                    })
                
                # 发送到服务器
                response = requests.post(
                    f"{self.server_url}/api/sync",
                    json=sync_data,
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        Clock.schedule_once(lambda dt: callback(True, result.get('message', '同步成功')) if callback else None)
                    else:
                        Clock.schedule_once(lambda dt: callback(False, result.get('message', '同步失败')) if callback else None)
                else:
                    Clock.schedule_once(lambda dt: callback(False, f'服务器错误: {response.status_code}') if callback else None)
                    
            except requests.exceptions.RequestException as e:
                Clock.schedule_once(lambda dt: callback(False, f'网络错误: {str(e)}') if callback else None)
            except Exception as e:
                Clock.schedule_once(lambda dt: callback(False, f'同步失败: {str(e)}') if callback else None)
        
        threading.Thread(target=sync_thread, daemon=True).start()
    
    def update_server_url(self, url):
        """更新服务器地址"""
        self.server_url = url
        self.db.save_setting('server_url', url)

class ExpiryTrackerApp(App):
    """主应用程序类"""
    def build(self):
        # 初始化数据库管理器
        self.db_manager = DatabaseManager()
        
        # 初始化产品管理器
        self.product_manager = ProductManager(self.db_manager)
        
        # 初始化网络管理器
        self.network_manager = NetworkManager(self.db_manager)
        
        # 创建屏幕管理器
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(ScanScreen(name='scan'))
        sm.add_widget(ProductListScreen(name='product_list'))
        sm.add_widget(AddProductScreen(name='add_product'))
        sm.add_widget(SettingsScreen(name='settings'))
        
        return sm

if __name__ == '__main__':
    ExpiryTrackerApp().run()