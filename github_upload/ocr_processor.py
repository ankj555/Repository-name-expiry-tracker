import os
import re
import datetime
from kivy.utils import platform
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.uix.image import Image

# 根据平台导入不同的库
if platform == 'android':
    from jnius import autoclass
    from android.permissions import request_permissions, Permission
    # Android相关类
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    CameraManager = autoclass('android.hardware.camera2.CameraManager')
    CameraDevice = autoclass('android.hardware.camera2.CameraDevice')
    CameraCharacteristics = autoclass('android.hardware.camera2.CameraCharacteristics')
    ImageReader = autoclass('android.media.ImageReader')
    SurfaceTexture = autoclass('android.graphics.SurfaceTexture')
    Surface = autoclass('android.view.Surface')
    # Tesseract OCR
    TessBaseAPI = autoclass('com.googlecode.tesseract.android.TessBaseAPI')
else:
    # 桌面平台使用OpenCV和Tesseract
    import cv2
    import pytesseract

class OCRProcessor:
    """OCR处理类，负责识别生产日期"""
    
    def __init__(self):
        """初始化OCR处理器"""
        self.camera = None
        self.callback = None
        self.is_scanning = False
        self.image_widget = None
        self.clock_event = None
        
        # 初始化OCR引擎
        if platform == 'android':
            # 在Android上请求相机权限
            request_permissions([Permission.CAMERA])
            
            # 初始化Tesseract
            self.tess = TessBaseAPI()
            activity = PythonActivity.mActivity
            app_dir = activity.getExternalFilesDir(None).getAbsolutePath()
            tessdata_path = os.path.join(app_dir, 'tessdata')
            
            # 确保tessdata目录存在
            if not os.path.exists(tessdata_path):
                os.makedirs(tessdata_path)
            
            # 初始化Tesseract引擎
            self.tess.init(app_dir, "chi_sim+eng")
        else:
            # 桌面平台使用pytesseract
            pass
    
    def start_camera(self, callback):
        """启动相机进行OCR识别
        
        Args:
            callback: OCR识别回调函数，接收识别到的文本作为参数
        """
        self.callback = callback
        self.is_scanning = True
        
        if platform == 'android':
            self._start_camera_android()
        else:
            self._start_camera_desktop()
    
    def _start_camera_android(self):
        """在Android平台上启动相机"""
        # 获取当前活动
        activity = PythonActivity.mActivity
        context = activity.getApplicationContext()
        
        # 获取相机管理器
        camera_manager = context.getSystemService(context.CAMERA_SERVICE)
        
        # 获取后置相机ID
        camera_id = None
        for camera_id_candidate in camera_manager.getCameraIdList():
            characteristics = camera_manager.getCameraCharacteristics(camera_id_candidate)
            facing = characteristics.get(CameraCharacteristics.LENS_FACING)
            if facing == CameraCharacteristics.LENS_FACING_BACK:
                camera_id = camera_id_candidate
                break
        
        if not camera_id:
            camera_id = camera_manager.getCameraIdList()[0]  # 使用第一个可用相机
        
        # 创建图像读取器
        self.image_reader = ImageReader.newInstance(
            1280, 720, ImageReader.ImageFormat.YUV_420_888, 2)
        
        # 创建相机预览
        self.surface_texture = SurfaceTexture(0)
        self.surface_texture.setDefaultBufferSize(1280, 720)
        self.surface = Surface(self.surface_texture)
        
        # 打开相机
        camera_manager.openCamera(camera_id, self.camera_state_callback, None)
        
        # 创建图像显示组件
        self.image_widget = Image()
        
        # 添加到UI
        from kivy.app import App
        app = App.get_running_app()
        camera_preview = app.root.get_screen('scan').ids.camera_preview
        camera_preview.clear_widgets()
        camera_preview.add_widget(self.image_widget)
        
        # 设置定时器进行OCR识别
        self.clock_event = Clock.schedule_interval(self._process_frame_android, 2.0)  # 每2秒处理一次
    
    def camera_state_callback(self, camera, state):
        """相机状态回调函数"""
        if state == CameraDevice.STATE_OPENED:
            self.camera = camera
            # 创建会话
            self.capture_session = camera.createCaptureSession([self.image_reader.getSurface(), self.surface])
            # 设置预览请求
            self.capture_request_builder = camera.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW)
            self.capture_request_builder.addTarget(self.surface)
            self.capture_request_builder.addTarget(self.image_reader.getSurface())
            self.capture_request = self.capture_request_builder.build()
            self.capture_session.setRepeatingRequest(self.capture_request, None, None)
    
    def _process_frame_android(self, dt):
        """处理Android相机帧并进行OCR识别"""
        if not self.is_scanning or not self.image_reader:
            return
        
        # 获取最新的图像
        image = self.image_reader.acquireLatestImage()
        if not image:
            return
        
        # 处理图像并进行OCR识别
        try:
            # 获取YUV数据
            y_plane = image.getPlanes()[0]
            y_buffer = y_plane.getBuffer()
            y_data = bytearray(y_buffer.remaining())
            y_buffer.get(y_data)
            
            # 设置Tesseract图像
            self.tess.setImage(y_data, image.getWidth(), image.getHeight(), 1, image.getWidth())
            
            # 执行OCR识别
            text = self.tess.getUTF8Text()
            
            # 查找日期格式
            date_text = self._extract_date(text)
            
            if date_text:
                # 停止扫描并回调
                self.is_scanning = False
                Clock.unschedule(self.clock_event)
                self.callback(date_text)
        finally:
            # 释放图像
            image.close()
    
    def _start_camera_desktop(self):
        """在桌面平台上启动相机"""
        # 打开默认相机
        self.camera = cv2.VideoCapture(0)
        
        if not self.camera.isOpened():
            print("无法打开相机")
            return
        
        # 创建图像显示组件
        self.image_widget = Image()
        
        # 添加到UI
        from kivy.app import App
        app = App.get_running_app()
        camera_preview = app.root.get_screen('scan').ids.camera_preview
        camera_preview.clear_widgets()
        camera_preview.add_widget(self.image_widget)
        
        # 设置定时器进行OCR识别
        self.clock_event = Clock.schedule_interval(self._process_frame_desktop, 2.0)  # 每2秒处理一次
    
    def _process_frame_desktop(self, dt):
        """处理桌面相机帧并进行OCR识别"""
        if not self.is_scanning or not self.camera:
            return
        
        # 读取一帧
        ret, frame = self.camera.read()
        if not ret:
            return
        
        # 显示图像
        # 将OpenCV的BGR格式转换为RGB
        buf = cv2.flip(frame, 0).tostring()
        texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
        texture.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
        self.image_widget.texture = texture
        
        # 预处理图像以提高OCR准确性
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        
        # 执行OCR识别
        text = pytesseract.image_to_string(gray, lang='chi_sim+eng')
        
        # 查找日期格式
        date_text = self._extract_date(text)
        
        if date_text:
            # 停止扫描并回调
            self.is_scanning = False
            Clock.unschedule(self.clock_event)
            self.callback(date_text)
    
    def _extract_date(self, text):
        """从文本中提取日期
        
        Args:
            text: OCR识别的文本
        
        Returns:
            str: 提取的日期文本，如果没有找到则返回None
        """
        # 常见的日期格式模式
        patterns = [
            # YYYY-MM-DD 或 YYYY/MM/DD
            r'\b(20\d{2})[\-/\.年](0?[1-9]|1[0-2])[\-/\.月](0?[1-9]|[12]\d|3[01])日?\b',
            # DD-MM-YYYY 或 DD/MM/YYYY
            r'\b(0?[1-9]|[12]\d|3[01])[\-/\.](0?[1-9]|1[0-2])[\-/\.](20\d{2})\b',
            # MM-DD-YYYY 或 MM/DD/YYYY
            r'\b(0?[1-9]|1[0-2])[\-/\.](0?[1-9]|[12]\d|3[01])[\-/\.](20\d{2})\b',
            # 生产日期: YYYY-MM-DD
            r'生产日期[：:](20\d{2})[\-/\.年](0?[1-9]|1[0-2])[\-/\.月](0?[1-9]|[12]\d|3[01])日?',
            # 生产日期: DD-MM-YYYY
            r'生产日期[：:](0?[1-9]|[12]\d|3[01])[\-/\.](0?[1-9]|1[0-2])[\-/\.](20\d{2})',
            # 生产日期: MM-DD-YYYY
            r'生产日期[：:](0?[1-9]|1[0-2])[\-/\.](0?[1-9]|[12]\d|3[01])[\-/\.](20\d{2})',
            # 简单年月日格式
            r'(20\d{2})年(0?[1-9]|1[0-2])月(0?[1-9]|[12]\d|3[01])日',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                # 根据匹配的格式返回日期文本
                if isinstance(matches[0], tuple):
                    if len(matches[0]) == 3:
                        # 根据模式确定日期格式
                        if pattern.startswith(r'\b(20\d{2})'):
                            # YYYY-MM-DD
                            return f"{matches[0][0]}-{matches[0][1]}-{matches[0][2]}"
                        elif pattern.startswith(r'\b(0?[1-9]|[12]\d|3[01])'):
                            # DD-MM-YYYY
                            return f"{matches[0][2]}-{matches[0][1]}-{matches[0][0]}"
                        elif pattern.startswith(r'\b(0?[1-9]|1[0-2])'):
                            # MM-DD-YYYY
                            return f"{matches[0][2]}-{matches[0][0]}-{matches[0][1]}"
                        elif pattern.startswith(r'生产日期[：:](20\d{2})'):
                            # 生产日期: YYYY-MM-DD
                            return f"{matches[0][0]}-{matches[0][1]}-{matches[0][2]}"
                        elif pattern.startswith(r'生产日期[：:](0?[1-9]|[12]\d|3[01])'):
                            # 生产日期: DD-MM-YYYY
                            return f"{matches[0][2]}-{matches[0][1]}-{matches[0][0]}"
                        elif pattern.startswith(r'生产日期[：:](0?[1-9]|1[0-2])'):
                            # 生产日期: MM-DD-YYYY
                            return f"{matches[0][2]}-{matches[0][0]}-{matches[0][1]}"
                        elif pattern.startswith(r'(20\d{2})年'):
                            # 简单年月日格式
                            return f"{matches[0][0]}-{matches[0][1]}-{matches[0][2]}"
                else:
                    # 直接返回匹配的文本
                    return matches[0]
        
        return None
    
    def parse_date(self, date_text):
        """解析日期文本为日期对象
        
        Args:
            date_text: 日期文本
        
        Returns:
            datetime.date: 解析后的日期对象
        
        Raises:
            ValueError: 如果日期格式无效
        """
        # 尝试不同的日期格式
        formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%Y.%m.%d',
            '%Y年%m月%d日',
            '%d-%m-%Y',
            '%d/%m/%Y',
            '%d.%m.%Y',
            '%m-%d-%Y',
            '%m/%d/%Y',
            '%m.%d.%Y'
        ]
        
        for fmt in formats:
            try:
                date_obj = datetime.datetime.strptime(date_text, fmt).date()
                return date_obj
            except ValueError:
                continue
        
        # 如果所有格式都失败，尝试提取数字并组合
        numbers = re.findall(r'\d+', date_text)
        if len(numbers) >= 3:
            year = int(numbers[0]) if len(numbers[0]) == 4 else int(numbers[2])
            month = int(numbers[1])
            day = int(numbers[2]) if len(numbers[0]) == 4 else int(numbers[0])
            
            try:
                return datetime.date(year, month, day)
            except ValueError:
                pass
        
        raise ValueError(f"无法解析日期: {date_text}")
    
    def stop_camera(self):
        """停止相机"""
        self.is_scanning = False
        
        if self.clock_event:
            Clock.unschedule(self.clock_event)
        
        if platform == 'android':
            if self.camera:
                self.camera.close()
                self.camera = None
            
            if self.image_reader:
                self.image_reader.close()
                self.image_reader = None
        else:
            if self.camera:
                self.camera.release()
                self.camera = None
        
        # 清除图像显示
        if self.image_widget and self.image_widget.parent:
            self.image_widget.parent.remove_widget(self.image_widget)
            self.image_widget = None