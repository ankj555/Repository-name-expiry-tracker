class ProductManager:
    """产品管理类，负责处理产品信息的管理"""
    
    def __init__(self, db_manager):
        """初始化产品管理器
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db_manager = db_manager
    
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
        return self.db_manager.add_product(barcode, name, shelf_life, return_days)
    
    def get_product_info(self, barcode):
        """获取产品信息
        
        Args:
            barcode: 产品条码
        
        Returns:
            dict: 产品信息，如果不存在则返回None
        """
        return self.db_manager.get_product(barcode)
    
    def update_product(self, barcode, name=None, shelf_life=None, return_days=None):
        """更新产品信息
        
        Args:
            barcode: 产品条码
            name: 产品名称（可选）
            shelf_life: 保质期（天数，可选）
            return_days: 退货期限（天数，可选）
        
        Returns:
            bool: 是否更新成功
        """
        # 获取当前产品信息
        product = self.db_manager.get_product(barcode)
        if not product:
            return False
        
        # 更新字段
        updated_name = name if name is not None else product['name']
        updated_shelf_life = shelf_life if shelf_life is not None else product['shelf_life']
        updated_return_days = return_days if return_days is not None else product['return_days']
        
        # 保存更新
        return self.db_manager.add_product(
            barcode, updated_name, updated_shelf_life, updated_return_days)
    
    def get_products_by_expiry(self, days_threshold=7):
        """获取即将过期的产品
        
        Args:
            days_threshold: 天数阈值，获取剩余天数小于等于此值的产品
        
        Returns:
            list: 产品记录列表
        """
        all_products = self.db_manager.get_all_products(sort_by='days_remaining')
        return [p for p in all_products if p['days_remaining'] <= days_threshold]
    
    def get_products_by_return_days(self):
        """获取在退货期限内的产品
        
        Returns:
            list: 产品记录列表
        """
        all_products = self.db_manager.get_all_products()
        result = []
        
        for product in all_products:
            # 获取产品的退货期限
            product_info = self.db_manager.get_product(product['barcode'])
            if not product_info:
                continue
            
            return_days = product_info['return_days']
            
            # 检查是否在退货期限内
            if product['days_remaining'] <= return_days:
                result.append(product)
        
        return result