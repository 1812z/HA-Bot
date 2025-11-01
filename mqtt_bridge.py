import json
import time
import paho.mqtt.client as mqtt
from typing import Optional, Callable


class MQTTBridge:
    """MQTT桥接类 - 与Home Assistant集成"""

    def __init__(self, config_manager):
        self.config = config_manager
        self.client: Optional[mqtt.Client] = None

        # MQTT配置
        self.enabled = self.config.get('mqtt', 'enabled', default=False)
        if not self.enabled:
            print("⚠️ MQTT功能未启用")
            return

        self.broker = self.config.get('mqtt', 'broker')
        self.port = self.config.get('mqtt', 'port', default=1883)
        self.username = self.config.get('mqtt', 'username')
        self.password = self.config.get('mqtt', 'password')
        self.client_id = self.config.get('mqtt', 'client_id', default='qq_bot_ha')

        # MQTT主题
        self.topic_receive = self.config.get('mqtt', 'topics', 'receive', default='qqbot/messages/received')
        self.topic_send = self.config.get('mqtt', 'topics', 'send', default='qqbot/messages/send')
        self.topic_status = self.config.get('mqtt', 'topics', 'status', default='qqbot/status')
        self.discovery_prefix = self.config.get('mqtt', 'topics', 'discovery_prefix', default='homeassistant')

        # Home Assistant设备信息
        self.device_name = self.config.get('homeassistant', 'device_name', default='QQ Bot')
        self.device_id = self.config.get('homeassistant', 'device_id', default='qq_bot_001')

        self.is_connected = False
        self.temp_message = ""
        self.temp_group_id = self.config.get('default', 'target_group')

        # 消息发送回调
        self.on_send_message: Optional[Callable] = None

    def setup(self):
        """设置MQTT客户端"""
        if not self.enabled:
            return

        self.client = mqtt.Client(client_id=self.client_id)

        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        self.client.will_set(
            self.topic_status,
            payload=json.dumps({"status": "offline"}),
            qos=1,
            retain=True
        )

    def _on_connect(self, client, userdata, flags, rc):
        """MQTT连接回调"""
        if rc == 0:
            print("✅ MQTT连接成功!")
            self.is_connected = True

            # 订阅主题
            client.subscribe(f"{self.topic_send}_text")
            client.subscribe(f"{self.topic_send}_group")
            client.subscribe(f"{self.topic_send}_button")

            # 发布在线状态
            self._publish_status("online")

            # 发布HA发现配置
            self._publish_ha_discovery()
        else:
            print(f"❌ MQTT连接失败，错误码: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """断开连接回调"""
        print(f"⚠️ MQTT断开连接")
        self.is_connected = False

    def _on_message(self, client, userdata, msg):
        """消息接收回调"""
        try:
            # 处理文本输入
            if msg.topic == f"{self.topic_send}_text":
                self.temp_message = msg.payload.decode()
                print(f"💬 收到消息输入: {self.temp_message}")

            # 处理群号输入
            elif msg.topic == f"{self.topic_send}_group":
                try:
                    self.temp_group_id = int(msg.payload.decode())
                    print(f"👥 收到群号输入: {self.temp_group_id}")
                except ValueError:
                    print("⚠️ 无效的群号")

            # 处理发送按钮
            elif msg.topic == f"{self.topic_send}_button":
                if msg.payload.decode() == "SEND":
                    if self.temp_group_id and self.temp_message:
                        print(f"📤 准备发送消息到群 {self.temp_group_id}: {self.temp_message}")
                        if self.on_send_message:
                            self.on_send_message(self.temp_group_id, self.temp_message)
                        self.temp_message = ""
                    else:
                        print("⚠️ 群号或消息为空")

        except Exception as e:
            print(f"❌ 处理MQTT消息错误: {e}")

    def _publish_status(self, status: str):
        """发布状态"""
        if self.client and self.is_connected:
            payload = {"status": status, "timestamp": time.time()}
            self.client.publish(self.topic_status, json.dumps(payload), qos=1, retain=True)

    def _publish_ha_discovery(self):
        """发布Home Assistant自动发现配置"""
        device_info = {
            "identifiers": [self.device_id],
            "name": self.device_name,
            "manufacturer": self.config.get('homeassistant', 'manufacturer', default='1812z'),
            "model": self.config.get('homeassistant', 'model', default='QQ Bot v1.0')
        }

        # 1. 最后消息传感器
        text_sensor = {
            "name": f"{self.device_name} Last Message",
            "unique_id": f"{self.device_id}_last_message",
            "state_topic": self.topic_receive,
            "value_template": "{{ value_json.message }}",
            "icon": "mdi:message-text",
            "device": device_info
        }
        self.client.publish(
            f"{self.discovery_prefix}/sensor/{self.device_id}_message/config",
            json.dumps(text_sensor), qos=1, retain=True
        )

        # 2. 最后群号传感器
        group_sensor = {
            "name": f"{self.device_name} Last Group ID",
            "unique_id": f"{self.device_id}_last_group",
            "state_topic": self.topic_receive,
            "value_template": "{{ value_json.group_id }}",
            "icon": "mdi:account-group",
            "device": device_info
        }
        self.client.publish(
            f"{self.discovery_prefix}/sensor/{self.device_id}_group/config",
            json.dumps(group_sensor), qos=1, retain=True
        )

        # 3. 消息文本输入框
        text_input = {
            "name": f"{self.device_name} Send Message",
            "unique_id": f"{self.device_id}_send_message",
            "command_topic": f"{self.topic_send}_text",
            "icon": "mdi:message-draw",
            "device": device_info,
            "mode": "text"
        }
        self.client.publish(
            f"{self.discovery_prefix}/text/{self.device_id}_send_message/config",
            json.dumps(text_input), qos=1, retain=True
        )

        # 4. 群号输入框
        group_input = {
            "name": f"{self.device_name} Target Group ID",
            "unique_id": f"{self.device_id}_target_group",
            "command_topic": f"{self.topic_send}_group",
            "icon": "mdi:numeric",
            "device": device_info,
            "mode": "text"
        }
        self.client.publish(
            f"{self.discovery_prefix}/text/{self.device_id}_target_group/config",
            json.dumps(group_input), qos=1, retain=True
        )

        # 5. 发送按钮
        button = {
            "name": f"{self.device_name} Send Button",
            "unique_id": f"{self.device_id}_send_button",
            "command_topic": f"{self.topic_send}_button",
            "payload_press": "SEND",
            "icon": "mdi:send",
            "device": device_info
        }
        self.client.publish(
            f"{self.discovery_prefix}/button/{self.device_id}_send_button/config",
            json.dumps(button), qos=1, retain=True
        )

        print("📢 已发布所有Home Assistant发现配置")

    def publish_received_message(self, group_id: int, message: str, user_id: int = None):
        """发布接收到的消息到Home Assistant"""
        if not self.enabled or not self.client or not self.is_connected:
            return

        payload = {
            "group_id": group_id,
            "message": message,
            "timestamp": time.time()
        }
        if user_id:
            payload["user_id"] = user_id

        self.client.publish(self.topic_receive, json.dumps(payload), qos=1)
        print(f"📢 已推送到HA: 群{group_id} - {message}")

    def connect(self):
        """连接MQTT"""
        if not self.enabled:
            return False

        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            print(f"🔌 MQTT已启动: {self.broker}:{self.port}")
            return True
        except Exception as e:
            print(f"❌ MQTT连接失败: {e}")
            return False

    def disconnect(self):
        """断开MQTT"""
        if self.enabled and self.client:
            self._publish_status("offline")
            self.client.loop_stop()
            self.client.disconnect()