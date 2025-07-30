#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日期识别模块
使用OCR技术识别图片中的日期信息
"""

import re
import cv2
import numpy as np
from datetime import datetime, timedelta
from kivy.logger import Logger

try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False
    Logger.warning("EasyOCR not available, using basic text recognition")

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False
    Logger.warning("Pytesseract not available")

class DateRecognizer:
    """日期识别器"""
    
    def __init__(self):
        self.reader = None
        if HAS_EASYOCR:
            try:
                self.reader = easyocr.Reader(['ch_sim', 'en'])
                Logger.info("EasyOCR initialized successfully")
            except Exception as e:
                Logger.error(f"Failed to initialize EasyOCR: {e}")
                self.reader = None
    
    def preprocess_image(self, image):
        """预处理图像以提高OCR识别率"""
        try:
            # 转换为灰度图
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # 应用高斯模糊去噪
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # 自适应阈值处理
            thresh = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            # 形态学操作去除噪点
            kernel = np.ones((2, 2), np.uint8)
            cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            
            return cleaned
            
        except Exception as e:
            Logger.error(f"Image preprocessing failed: {e}")
            return image
    
    def extract_text_easyocr(self, image):
        """使用EasyOCR提取文本"""
        try:
            if self.reader is None:
                return []
            
            results = self.reader.readtext(image)
            texts = []
            
            for (bbox, text, confidence) in results:
                if confidence > 0.3:  # 置信度阈值
                    texts.append(text)
                    Logger.debug(f"EasyOCR detected: {text} (confidence: {confidence:.2f})")
            
            return texts
            
        except Exception as e:
            Logger.error(f"EasyOCR text extraction failed: {e}")
            return []
    
    def extract_text_tesseract(self, image):
        """使用Tesseract提取文本"""
        try:
            if not HAS_TESSERACT:
                return []
            
            # 配置Tesseract参数
            config = '--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789年月日./-'
            text = pytesseract.image_to_string(image, lang='chi_sim+eng', config=config)
            
            if text.strip():
                Logger.debug(f"Tesseract detected: {text.strip()}")
                return [text.strip()]
            
            return []
            
        except Exception as e:
            Logger.error(f"Tesseract text extraction failed: {e}")
            return []
    
    def parse_date_patterns(self, texts):
        """解析文本中的日期模式"""
        dates = []
        
        # 定义日期正则表达式模式
        patterns = [
            # 中文格式
            r'(\d{4})年(\d{1,2})月(\d{1,2})日',
            r'(\d{4})年(\d{1,2})月',
            # 数字格式
            r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})',
            r'(\d{4})[-./](\d{1,2})',
            # 生产日期标识
            r'生产日期[：:](\d{4})[-./年](\d{1,2})[-./月](\d{1,2})',
            r'生产[：:]*(\d{4})[-./年](\d{1,2})[-./月](\d{1,2})',
            r'制造日期[：:](\d{4})[-./年](\d{1,2})[-./月](\d{1,2})',
            # 保质期标识
            r'保质期[：:](\d{1,2})[个]*月',
            r'保质期至[：:]*(\d{4})[-./年](\d{1,2})[-./月](\d{1,2})',
        ]
        
        for text in texts:
            for pattern in patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    try:
                        if len(match) == 3:  # 年月日
                            year, month, day = map(int, match)
                            date_obj = datetime(year, month, day)
                            dates.append({
                                'date': date_obj,
                                'type': 'production_date',
                                'text': text,
                                'confidence': 0.8
                            })
                        elif len(match) == 2:  # 年月
                            year, month = map(int, match)
                            date_obj = datetime(year, month, 1)
                            dates.append({
                                'date': date_obj,
                                'type': 'production_date',
                                'text': text,
                                'confidence': 0.6
                            })
                        elif len(match) == 1:  # 保质期月数
                            shelf_life_months = int(match[0])
                            dates.append({
                                'shelf_life_months': shelf_life_months,
                                'type': 'shelf_life',
                                'text': text,
                                'confidence': 0.7
                            })
                    except ValueError as e:
                        Logger.debug(f"Date parsing error: {e}")
                        continue
        
        return dates
    
    def recognize_date(self, image_path_or_array):
        """识别图像中的日期信息"""
        try:
            # 加载图像
            if isinstance(image_path_or_array, str):
                image = cv2.imread(image_path_or_array)
            else:
                image = image_path_or_array
            
            if image is None:
                Logger.error("Failed to load image")
                return None
            
            # 预处理图像
            processed_image = self.preprocess_image(image)
            
            # 提取文本
            texts = []
            
            # 尝试使用EasyOCR
            if HAS_EASYOCR and self.reader:
                easyocr_texts = self.extract_text_easyocr(processed_image)
                texts.extend(easyocr_texts)
            
            # 尝试使用Tesseract
            if HAS_TESSERACT:
                tesseract_texts = self.extract_text_tesseract(processed_image)
                texts.extend(tesseract_texts)
            
            if not texts:
                Logger.warning("No text detected in image")
                return None
            
            # 解析日期
            dates = self.parse_date_patterns(texts)
            
            if not dates:
                Logger.warning("No dates found in extracted text")
                return None
            
            # 返回置信度最高的日期
            best_date = max(dates, key=lambda x: x.get('confidence', 0))
            
            Logger.info(f"Date recognition successful: {best_date}")
            return best_date
            
        except Exception as e:
            Logger.error(f"Date recognition failed: {e}")
            return None
    
    def calculate_expiry_date(self, production_date, shelf_life_months=None, shelf_life_days=None):
        """计算过期日期"""
        try:
            if shelf_life_months:
                # 按月计算
                expiry_date = production_date + timedelta(days=shelf_life_months * 30)
            elif shelf_life_days:
                # 按天计算
                expiry_date = production_date + timedelta(days=shelf_life_days)
            else:
                # 默认保质期6个月
                expiry_date = production_date + timedelta(days=180)
            
            return expiry_date
            
        except Exception as e:
            Logger.error(f"Expiry date calculation failed: {e}")
            return None
    
    def get_days_remaining(self, expiry_date):
        """计算剩余天数"""
        try:
            today = datetime.now().date()
            if isinstance(expiry_date, datetime):
                expiry_date = expiry_date.date()
            
            remaining = (expiry_date - today).days
            return remaining
            
        except Exception as e:
            Logger.error(f"Days remaining calculation failed: {e}")
            return 0

# 测试函数
if __name__ == "__main__":
    recognizer = DateRecognizer()
    
    # 测试文本解析
    test_texts = [
        "生产日期：2024年1月15日",
        "2024/01/15",
        "保质期：12个月",
        "制造日期2024.1.15"
    ]
    
    dates = recognizer.parse_date_patterns(test_texts)
    for date_info in dates:
        print(f"识别到日期: {date_info}")