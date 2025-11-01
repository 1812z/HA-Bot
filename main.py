import requests
import json
import time
import uvicorn
import yaml
import shutil
from pathlib import Path
from fastapi import FastAPI, Request
import HA
from mqtt_bridge import MQTTBridge


class IntegratedConfigManager:
    """统一配置管理类"""

    def __init__(self, config_path="config.yaml", example_path="config.example.yaml"):
        self.config_path = Path(config_path)
        self.example_path = Path(example_path)
        self.config = self._load_config()

    def _load_config(self):
        """加载配置文件"""
        if not self.config_path.exists():
            if self.example_path.exists():
                print(f"配置文件 {self.config_path} 不存在，从 {self.example_path} 复制...")
                shutil.copy(self.example_path, self.config_path)
                print(f"配置文件已创建: {self.config_path}")
            else:
                raise FileNotFoundError(f"示例配置文件 {self.example_path} 不存在！")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def get(self, *keys, default=None):
        """获取配置值"""
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value


class RequestHelper:
    """HTTP请求辅助类"""

    def __init__(self, max_retries=3, delay=1):
        self.max_retries = max_retries
        self.delay = delay

    def send_with_retry(self, url, payload, headers):
        """带重试的POST请求"""
        for attempt in range(self.max_retries):
            try:
                response = requests.post(url, data=payload, headers=headers)
                print(f"✅ 请求成功: {response.text}")
                return response.text
            except requests.exceptions.ConnectionError:
                print(f"⚠️ 尝试 {attempt + 1}/{self.max_retries} 失败")
                if attempt < self.max_retries - 1:
                    time.sleep(self.delay)
                else:
                    raise
            except Exception as e:
                print(f"❌ 请求错误: {e}")
                break
        return None


class MessageHandler:
    """消息处理类"""

    def __init__(self, config_manager: IntegratedConfigManager, mqtt_bridge: MQTTBridge):
        self.config = config_manager
        self.mqtt = mqtt_bridge
        self.request_helper = RequestHelper()

        # 配置参数
        self.host = self.config.get('qq_bot', 'host')
        self.port = self.config.get('qq_bot', 'port')
        self.ha_url = self.config.get('home_assistant', 'url')
        self.secret = self.config.get('home_assistant', 'secret')
        self.agent_id = self.config.get('home_assistant', 'agent_id')
        self.group_list = self.config.get('group_whitelist', default=[])
        self.screenshot_url = self.config.get('screenshot', 'url')

        # 设置MQTT发送消息回调
        if self.mqtt:
            self.mqtt.on_send_message = self.send_group_message

    def parse_data(self, data):
        """解析消息数据"""
        group_id = data.get('group_id', None)
        user_id = data.get('user_id', None)
        message_text = data.get('message', [{}])[0].get('data', {}).get('text', None)

        print(f'群聊:{group_id} 用户:{user_id} 消息:{message_text}')
        return group_id, user_id, message_text

    def execute(self, data):
        """执行消息处理"""
        group_id, user_id, message_text = self.parse_data(data)

        # 推送到Home Assistant
        if message_text:
            self.mqtt.publish_received_message(group_id, message_text, user_id)

        if group_id not in self.group_list:
            return

        if not message_text:
            return

        # 处理/ha命令
        if message_text.startswith('/ha'):
            print("🏠 调用Home Assistant")
            response_data = HA.call_conversation_api(
                message_text.removeprefix('/ha'),
                self.ha_url,
                access_token=self.secret,
                agent_id=self.agent_id
            )
            self.send_group_message(group_id, response_data)

        # 处理/screen命令
        elif '/screen' in message_text:
            self.send_group_message(group_id, message_type='screen')

    def send_group_message(self, group_id, message='', message_type="text"):
        """发送群消息"""
        if message_type == 'text':
            payload = {
                "group_id": group_id,
                "message": [{"type": "text", "data": {"text": message}}]
            }
        elif message_type == 'screen':
            payload = {
                "group_id": group_id,
                "message": [{"type": "image", "data": {"file": self.screenshot_url}}]
            }

        print(f"📤 发送到群 {group_id}: {message}")

        url = f"http://{self.host}:{self.port}/send_group_msg"
        headers = {'Content-Type': 'application/json'}

        try:
            self.request_helper.send_with_retry(url, json.dumps(payload), headers)
        except Exception as e:
            print(f"❌ 发送失败: {e}")


class IntegratedQQBotApp:
    """集成QQ机器人应用 - 包含MQTT Home Assistant支持"""

    def __init__(self, config_path="config.yaml"):
        self.config_manager = IntegratedConfigManager(config_path)
        self.mqtt_bridge = MQTTBridge(self.config_manager)
        self.mqtt_bridge.setup()
        self.message_handler = MessageHandler(self.config_manager, self.mqtt_bridge)
        self.app = FastAPI()
        self._setup_routes()

    def _setup_routes(self):
        """设置路由"""

        @self.app.post("/")
        async def root(request: Request):
            data = await request.json()
            self.message_handler.execute(data)
            return {}

    def run(self):
        """启动应用"""
        # 启动MQTT
        self.mqtt_bridge.connect()

        # 启动FastAPI
        host = self.config_manager.get('server', 'host', default='0.0.0.0')
        port = self.config_manager.get('server', 'port', default=8080)

        print("\n" + "=" * 60)
        print("🤖 QQ Bot 集成服务启动")
        print("=" * 60)
        print(f"🌐 FastAPI服务: {host}:{port}")
        print(f"🏠 Home Assistant MQTT: {'已启用' if self.mqtt_bridge.enabled else '未启用'}")
        print(f"📋 群白名单: {self.message_handler.group_list}")
        print("=" * 60 + "\n")

        try:
            uvicorn.run(self.app, host=host, port=port)
        except KeyboardInterrupt:
            print("\n⚠️ 正在关闭...")
        finally:
            self.mqtt_bridge.disconnect()


if __name__ == "__main__":
    bot = IntegratedQQBotApp()
    bot.run()