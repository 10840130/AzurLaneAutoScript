"""
API 客户端模块
负责与 API 服务器进行所有HTTP交互
包括Bug日志上报、CL1数据提交和公告获取
支持主域名(nanoda.work)和备用域名(xf-sama.xyz)的自动故障转移
"""
import threading
from typing import Any, Dict, List, Tuple

import requests

from module.base.device_id import get_device_id
from module.logger import logger


class ApiClient:
    """统一的API客户端，支持双域名故障转移"""
    
    # 主域名和备用域名列表
    PRIMARY_DOMAIN = 'https://alas-apiv2.nanoda.work'
    FALLBACK_DOMAIN = 'https://alas-apiv2.xf-sama.xyz'
    
    # API端点路径
    BUG_LOG_PATH = '/api/post/bug'
    CL1_DATA_PATH = '/api/telemetry'
    ANNOUNCEMENT_PATH = '/api/get/announcement'
    
    @classmethod
    def _get_endpoints(cls, path: str) -> List[str]:
        """
        获取指定路径的所有端点URL（主域名+备用域名）
        
        Args:
            path: API路径
            
        Returns:
            端点URL列表
        """
        return [
            f'{cls.PRIMARY_DOMAIN}{path}',
            f'{cls.FALLBACK_DOMAIN}{path}'
        ]
    
    @classmethod
    def _post_with_fallback(cls, path: str, json_data: Dict[str, Any], timeout: int = 5) -> Tuple[bool, int, str]:
        """
        使用故障转移机制发送POST请求
        
        Args:
            path: API路径
            json_data: 要发送的JSON数据
            timeout: 超时时间（秒）
            
        Returns:
            (是否成功, HTTP状态码, 响应文本)
        """
        endpoints = cls._get_endpoints(path)
        last_error = None
        
        for i, endpoint in enumerate(endpoints):
            try:
                domain_type = "主域名" if i == 0 else "备用域名"
                logger.debug(f'尝试使用{domain_type}: {endpoint}')
                
                response = requests.post(
                    endpoint,
                    json=json_data,
                    timeout=timeout,
                    headers={'Content-Type': 'application/json'}
                )
                
                if response.status_code == 200:
                    if i > 0:
                        logger.info(f'✓ 使用{domain_type}请求成功')
                    return True, response.status_code, response.text
                else:
                    logger.warning(f'{domain_type}返回错误状态: {response.status_code}')
                    last_error = f'HTTP {response.status_code}'
                    
            except requests.exceptions.Timeout:
                logger.warning(f'{domain_type if i > 0 else "主域名"}请求超时')
                last_error = 'Timeout'
            except requests.exceptions.RequestException as e:
                logger.warning(f'{domain_type if i > 0 else "主域名"}请求失败: {e}')
                last_error = str(e)
            except Exception as e:
                logger.warning(f'{domain_type if i > 0 else "主域名"}发生异常: {e}')
                last_error = str(e)
        
        return False, 0, last_error or 'Unknown error'
    
    @classmethod
    def _get_with_fallback(cls, path: str, params: Dict[str, Any] = None, timeout: int = 10) -> Tuple[bool, int, str]:
        """
        使用故障转移机制发送GET请求
        
        Args:
            path: API路径
            params: URL参数
            timeout: 超时时间（秒）
            
        Returns:
            (是否成功, HTTP状态码, 响应文本)
        """
        endpoints = cls._get_endpoints(path)
        last_error = None
        
        for i, endpoint in enumerate(endpoints):
            try:
                domain_type = "主域名" if i == 0 else "备用域名"
                logger.debug(f'尝试使用{domain_type}: {endpoint}')
                
                response = requests.get(
                    endpoint,
                    params=params,
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    if i > 0:
                        logger.info(f'✓ 使用{domain_type}请求成功')
                    return True, response.status_code, response.text
                else:
                    logger.warning(f'{domain_type}返回错误状态: {response.status_code}')
                    last_error = f'HTTP {response.status_code}'
                    
            except requests.exceptions.Timeout:
                logger.warning(f'{domain_type if i > 0 else "主域名"}请求超时')
                last_error = 'Timeout'
            except requests.exceptions.RequestException as e:
                logger.warning(f'{domain_type if i > 0 else "主域名"}请求失败: {e}')
                last_error = str(e)
            except Exception as e:
                logger.warning(f'{domain_type if i > 0 else "主域名"}发生异常: {e}')
                last_error = str(e)
        
        return False, 0, last_error or 'Unknown error'
    
    @staticmethod
    def _submit_bug_log(content: str, log_type: str):
        """
        内部方法：提交Bug日志
        
        Args:
            content: 日志内容
            log_type: 日志类型
        """
        try:
            device_id = get_device_id()
            data = {
                'device_id': device_id,
                'log_type': log_type,
                'log_content': content,
            }
            
            success, status_code, response_text = ApiClient._post_with_fallback(
                ApiClient.BUG_LOG_PATH,
                data,
                timeout=5
            )
            
            if success:
                logger.info(f'Bug log submitted: {content[:50]}...')
            else:
                logger.warning(f'Failed to submit bug log: {response_text}')
        except Exception as e:
            logger.warning(f'Failed to submit bug log: {e}')
    
    @classmethod
    def submit_bug_log(cls, content: str, log_type: str = 'warning', enabled: bool = True):
        """
        提交Bug日志（异步）
        
        Args:
            content: 日志内容
            log_type: 日志类型，默认为'warning'
            enabled: 是否启用上报，可传入 config.DropRecord_BugReport 配置值
        """
        if not enabled:
            return
        threading.Thread(
            target=cls._submit_bug_log,
            args=(content, log_type),
            daemon=True
        ).start()
    
    @staticmethod
    def _submit_cl1_data(data: Dict[str, Any], timeout: int):
        """
        内部方法：提交CL1数据
        
        Args:
            data: 数据字典
            timeout: 超时时间（秒）
        """
        try:
            # 如果没有任何战斗数据,不提交
            if data.get('battle_count', 0) == 0:
                logger.info('No CL1 battle data to submit')
                return
            
            logger.info(f'Submitting CL1 data for {data.get("month", "unknown")}...')
            logger.attr('battle_count', data.get('battle_count', 0))
            logger.attr('akashi_encounters', data.get('akashi_encounters', 0))
            logger.attr('akashi_probability', f"{data.get('akashi_probability', 0):.2%}")
            
            success, status_code, response_text = ApiClient._post_with_fallback(
                ApiClient.CL1_DATA_PATH,
                data,
                timeout=timeout
            )
            
            if success:
                logger.info('✓ CL1 data submitted successfully')
            else:
                logger.warning(f'✗ CL1 data submission failed: {response_text}')
        
        except Exception as e:
            logger.exception(f'Unexpected error during CL1 data submission: {e}')
    
    @classmethod
    def submit_cl1_data(cls, data: Dict[str, Any], timeout: int = 10):
        """
        提交CL1统计数据（异步）
        
        Args:
            data: 包含device_id和统计数据的字典
            timeout: 请求超时时间（秒），默认10秒
        """
        threading.Thread(
            target=cls._submit_cl1_data,
            args=(data, timeout),
            daemon=True
        ).start()
    
    @classmethod
    def get_announcement(cls, timeout: int = 10) -> Dict[str, Any]:
        """
        获取公告信息（同步）
        
        Args:
            timeout: 请求超时时间（秒），默认10秒
            
        Returns:
            公告数据字典，失败时返回空字典
        """
        import time
        try:
            # 添加时间戳参数以绕过缓存
            timestamp = int(time.time())
            params = {'t': timestamp}
            
            success, status_code, response_text = cls._get_with_fallback(
                cls.ANNOUNCEMENT_PATH,
                params=params,
                timeout=timeout
            )
            
            if success:
                import json
                data = json.loads(response_text)
                if data and data.get('announcementId') and data.get('title') and data.get('content'):
                    return data
                else:
                    logger.debug('Announcement data is incomplete')
                    return {}
            else:
                logger.debug(f'Failed to get announcement: {response_text}')
                return {}
                
        except Exception as e:
            logger.debug(f'Failed to get announcement: {e}')
            return {}


class AnnouncementSSEClient:
    """
    公告 SSE 客户端
    与云服务保持长连接，接收公告推送
    支持自动重连和降级到轮询模式
    """
    
    # SSE 端点路径
    SSE_PATH = '/api/sse/announcement'
    
    # 重连配置（指数退避）
    RECONNECT_MIN_DELAY = 5      # 最小重连延迟（秒）
    RECONNECT_MAX_DELAY = 300    # 最大重连延迟（秒）
    
    def __init__(self, on_announcement=None):
        """
        初始化 SSE 客户端
        
        Args:
            on_announcement: 收到公告时的回调函数，签名: callback(data: dict)
        """
        self._on_announcement = on_announcement
        self._running = False
        self._thread = None
        self._current_delay = self.RECONNECT_MIN_DELAY
        self._last_announcement_id = None
    
    def start(self):
        """启动 SSE 客户端（后台线程）"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info('Announcement SSE client started')
    
    def stop(self):
        """停止 SSE 客户端"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info('Announcement SSE client stopped')
    
    def _run_loop(self):
        """主循环：连接 SSE 并处理事件"""
        import time
        
        while self._running:
            try:
                self._connect_sse()
            except Exception as e:
                logger.debug(f'SSE connection error: {e}')
            
            if not self._running:
                break
            
            # 重连等待（指数退避）
            logger.info(f'SSE reconnecting in {self._current_delay}s...')
            time.sleep(self._current_delay)
            self._current_delay = min(self._current_delay * 2, self.RECONNECT_MAX_DELAY)
    
    def _connect_sse(self):
        """连接 SSE 端点并处理事件流"""
        import time
        
        endpoints = ApiClient._get_endpoints(self.SSE_PATH)
        
        for i, endpoint in enumerate(endpoints):
            if not self._running:
                return
            
            try:
                domain_type = "主域名" if i == 0 else "备用域名"
                logger.info(f'Connecting to SSE ({domain_type})...')
                
                response = requests.get(
                    endpoint,
                    headers={'Accept': 'text/event-stream', 'Cache-Control': 'no-cache'},
                    stream=True,
                    timeout=(10, None)  # 连接超时10秒，读取不超时
                )
                
                if response.status_code != 200:
                    logger.warning(f'SSE {domain_type} returned {response.status_code}')
                    continue
                
                # 连接成功，重置重连延迟
                self._current_delay = self.RECONNECT_MIN_DELAY
                logger.info(f'SSE connected ({domain_type})')
                
                # 处理事件流
                self._process_stream(response)
                return  # 连接断开后退出，主循环会重连
                
            except requests.exceptions.Timeout:
                logger.warning(f'SSE {domain_type} connection timeout')
            except requests.exceptions.RequestException as e:
                logger.warning(f'SSE {domain_type} connection failed: {e}')
            except Exception as e:
                logger.warning(f'SSE {domain_type} error: {e}')
        
        # 所有端点都失败，尝试降级轮询
        self._fallback_poll()
    
    def _process_stream(self, response):
        """处理 SSE 事件流"""
        event_type = None
        data_lines = []
        
        for line in response.iter_lines(decode_unicode=True):
            if not self._running:
                break
            
            if line is None:
                continue
            
            if line == '':
                # 空行表示事件结束
                if event_type and data_lines:
                    data = ''.join(data_lines)
                    self._handle_event(event_type, data)
                event_type = None
                data_lines = []
            elif line.startswith('event:'):
                event_type = line[6:].strip()
            elif line.startswith('data:'):
                data_lines.append(line[5:].strip())
    
    def _handle_event(self, event_type: str, data: str):
        """处理单个 SSE 事件"""
        import json
        
        try:
            parsed = json.loads(data) if data else {}
        except json.JSONDecodeError:
            parsed = {}
        
        if event_type == 'connected':
            logger.info('SSE connection confirmed')
        elif event_type == 'heartbeat':
            logger.debug('SSE heartbeat received')
        elif event_type == 'announcement':
            self._handle_announcement(parsed)
        elif event_type == 'error':
            logger.warning(f'SSE error: {parsed.get("message", "Unknown")}')
    
    def _handle_announcement(self, data: dict):
        """处理公告事件"""
        announcement_id = data.get('id')
        if not announcement_id:
            return
        
        # 去重
        if announcement_id == self._last_announcement_id:
            return
        self._last_announcement_id = announcement_id
        
        logger.info(f'New announcement received: {announcement_id}')
        
        if self._on_announcement:
            try:
                self._on_announcement(data)
            except Exception as e:
                logger.warning(f'Announcement callback error: {e}')
    
    def _fallback_poll(self):
        """降级到轮询模式获取公告"""
        try:
            data = ApiClient.get_announcement(timeout=10)
            if data:
                # 转换旧格式到新格式
                converted = {
                    'id': data.get('announcementId') or data.get('id'),
                    'url': data.get('url', ''),
                    'title': data.get('title', ''),
                }
                if converted['id'] and converted['url']:
                    self._handle_announcement(converted)
        except Exception as e:
            logger.debug(f'Fallback poll failed: {e}')


class AnnouncementManager:
    """
    全局公告管理器（单例）
    管理 SSE 连接并广播公告给所有 PyWebIO 客户端
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance
    
    def _init(self):
        self._callbacks = []
        self._callbacks_lock = threading.Lock()
        self._current_announcement = None
        self._sse_client = None
    
    def start(self):
        """启动公告管理器"""
        if self._sse_client:
            return
        self._sse_client = AnnouncementSSEClient(on_announcement=self._on_announcement)
        self._sse_client.start()
    
    def stop(self):
        """停止公告管理器"""
        if self._sse_client:
            self._sse_client.stop()
            self._sse_client = None
    
    def register_callback(self, callback):
        """注册公告回调（PyWebIO 客户端调用）"""
        with self._callbacks_lock:
            self._callbacks.append(callback)
        # 如果有当前公告，立即推送
        if self._current_announcement:
            try:
                callback(self._current_announcement)
            except Exception:
                pass
    
    def unregister_callback(self, callback):
        """取消注册回调"""
        with self._callbacks_lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
    
    def _on_announcement(self, data: dict):
        """收到公告时广播给所有客户端"""
        self._current_announcement = data
        
        with self._callbacks_lock:
            callbacks = list(self._callbacks)
        
        for callback in callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.debug(f'Announcement broadcast error: {e}')


# 全局公告管理器实例
announcement_manager = AnnouncementManager()
