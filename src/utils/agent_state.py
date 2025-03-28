import asyncio
import logging
import threading
import time
import uuid

from browser_use.agent.message_manager.views import MessageManagerState
from browser_use.agent.views import ActionResult, AgentHistoryList

logger = logging.getLogger(__name__)

class AgentState:
    _instance = None

    def __init__(self):
        if not hasattr(self, '_stop_requested'):
            self._stop_requested = asyncio.Event()
            self.last_valid_state = None  # store the last valid browser state
            self.agent_id = str(uuid.uuid4())  # 生成唯一的agent_id
            self.stopped = False  # 标记agent是否已停止
            self.next_suggested_action = None  # 下一个建议的操作
            self.message_manager_state = MessageManagerState()  # 添加message_manager_state属性
            self.history = AgentHistoryList(history=[])  # 添加history属性
            self.n_steps = 0  # 添加n_steps属性，用于跟踪执行步骤数
            self.consecutive_failures = 0  # 添加consecutive_failures属性，用于跟踪连续失败次数
            self.paused = False  # 添加paused属性，用于标记agent是否暂停
            self.last_action = None  # 添加last_action属性，用于记录上一个执行的操作
            self.extracted_content = None  # 添加extracted_content属性，用于存储提取的内容
            self.last_result = []  # 添加last_result属性，用于记录上一个操作的结果
            self.user_control_active = False  # 添加user_control_active属性，用于标记是否处于用户接管状态
            self.last_takeover_time = 0  # 添加时间戳字段，记录最后一次请求接管的时间
            self._polling_thread = None  # 用于存储轮询线程
            self._stop_polling = False  # 用于停止轮询线程

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentState, cls).__new__(cls)
        return cls._instance

    def request_stop(self):
        self._stop_requested.set()
        self.stopped = True

    def clear_stop(self):
        self._stop_requested.clear()
        self.last_valid_state = None
        self.stopped = False
        self.next_suggested_action = None  # 重置建议操作
        self.user_control_active = False  # 重置用户接管状态

    def is_stop_requested(self):
        return self._stop_requested.is_set()

    def set_last_valid_state(self, state):
        self.last_valid_state = state

    def get_last_valid_state(self):
        return self.last_valid_state

    def suggest_next_action(self, action_name):
        """设置下一个建议操作"""
        self.next_suggested_action = action_name
        
    def get_next_suggested_action(self):
        """获取并清除下一个建议操作"""
        action = self.next_suggested_action
        self.next_suggested_action = None
        return action

    def set_user_control_active(self, active: bool):
        """设置用户接管状态"""
        self.user_control_active = active
        if active:
            # 如果是激活用户接管，记录时间戳
            self.last_takeover_time = time.time()

    def is_user_control_active(self) -> bool:
        """检查是否处于用户接管状态"""
        return self.user_control_active

    def get_last_takeover_time(self) -> float:
        """获取最后一次请求接管的时间戳"""
        return self.last_takeover_time
        
    def start_status_polling(self):
        """启动状态轮询，周期性触发状态更新，确保前端能检测到变化"""
        if self._polling_thread is not None and self._polling_thread.is_alive():
            logger.info("状态轮询线程已在运行")
            return
            
        self._stop_polling = False
        
        def _polling_func():
            logger.info("启动状态轮询线程")
            count = 0
            while not self._stop_polling:
                # 每隔3秒微调时间戳，确保前端能检测到变化
                if count % 3 == 0 and self.user_control_active:
                    old_time = self.last_takeover_time
                    self.last_takeover_time = time.time()
                    logger.info(f"状态轮询: 更新接管时间戳 {old_time} -> {self.last_takeover_time}")
                
                time.sleep(1)
                count += 1
                
        self._polling_thread = threading.Thread(target=_polling_func, daemon=True)
        self._polling_thread.start()
        
    def stop_status_polling(self):
        """停止状态轮询线程"""
        if self._polling_thread is not None and self._polling_thread.is_alive():
            logger.info("停止状态轮询线程")
            self._stop_polling = True
            self._polling_thread.join(timeout=2.0)
            self._polling_thread = None