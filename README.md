# QQ Bot with Home Assistant Integration

这是一个集成了 Home Assistant 的 QQ 机器人应用。

## 功能特性
- ✅ 群消息白名单
- ✅ 集成 Home Assistant 对话 API


## 安装依赖

```bash
pip install -r requirements.txt
```

## 启动程序

```bash
python main.py
```


## 配置文件

首次运行时,程序会自动从 `config.example.yaml` 复制配置文件到 `config.yaml`。


### 支持的命令

- `/ha <消息>` - 与 Home Assistant 对话
- `/screen` - 发送特定图片

## 注意事项
配置好MQTT后，运行则自动添加实体到Homeassistant，鉴于Homeassistant限制，多次发送相同消息可能会丢失群号或者群消息
