import os
import time
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
    ZBarDetector = autoclass('net.sourceforge.zbar.ImageScanner')
    ZBarImage = autoclass('net.sourceforge.zbar.Image')
    ZBarSymbol = autoclass('net.sourceforge.zbar.Symbol')
else:
    # 桌面平台使用OpenCV和ZBar
    import cv2
    from pyzbar import pyzbar

class BarcodeScanner:
    """条码扫描类，负责处理条码识别功能"""
    
    def __init__(self):
        """初始化条码扫描器"""
        self.camera = None
        self.callback = None
        self.is_scanning = False
        self.image_widget = None
        self.clock_event = None
        
        # 在Android上请求相机权限
        if platform == 'android':
            request_permissions([Permission.CAMERA])
    
    def start_camera(self, callback):
        """启动相机进行条码扫描
        
        Args:
            callback: 条码检测回调函数，接收检测到的条码作为参数
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
            640, 480, ImageReader.ImageFormat.YUV_420_888, 2)
        
        # 创建相机预览
        self.surface_texture = SurfaceTexture(0)
        self.surface_texture.setDefaultBufferSize(640, 480)
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
        
        # 设置定时器进行条码检测
        self.clock_event = Clock.schedule_interval(self._process_frame_android, 0.5)
    
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
        """处理Android相机帧并检测条码"""
        if not self.is_scanning or not self.image_reader:
            return
        
        # 获取最新的图像
        image = self.image_reader.acquireLatestImage()
        if not image:
            return
        
        # 处理图像并检测条码
        try:
            # 获取YUV数据
            y_plane = image.getPlanes()[0]
            y_buffer = y_plane.getBuffer()
            y_data = bytearray(y_buffer.remaining())
            y_buffer.get(y_data)
            
            # 创建ZBar图像
            zbar_image = ZBarImage()
            zbar_image.setSize(image.getWidth(), image.getHeight())
            zbar_image.setData(y_data)
            
            # 创建ZBar扫描器
            scanner = ZBarDetector()
            scanner.setConfig(0, ZBarDetector.CFG_ENABLE, 1)
            
            # 扫描条码
            result_code = scanner.scanImage(zbar_image)
            
            if result_code > 0:
                # 获取扫描结果
                symbols = zbar_image.getSymbols()
                for symbol in symbols:
                    barcode = symbol.getData()
                    # 停止扫描并回调
                    self.is_scanning = False
                    Clock.unschedule(self.clock_event)
                    self.callback(barcode)
                    break
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
        
        # 设置定时器进行条码检测
        self.clock_event = Clock.schedule_interval(self._process_frame_desktop, 0.1)
    
    def _process_frame_desktop(self, dt):
        """处理桌面相机帧并检测条码"""
        if not self.is_scanning or not self.camera:
            return
        
        # 读取一帧
        ret, frame = self.camera.read()
        if not ret:
            return
        
        # 检测条码
        barcodes = pyzbar.decode(frame)
        
        for barcode in barcodes:
            # 获取条码数据
            barcode_data = barcode.data.decode('utf-8')
            
            # 停止扫描并回调
            self.is_scanning = False
            Clock.unschedule(self.clock_event)
            self.callback(barcode_data)
            break
        
        # 显示图像
        # 将OpenCV的BGR格式转换为RGB
        buf = cv2.flip(frame, 0).tostring()
        texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
        texture.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
        self.image_widget.texture = texture
    
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