import requests
import json

def call_conversation_api(text,url,language='zh-cn', access_token=""):
    url = url+ '/api/conversation/process'
    # 设置请求头，包含访问令牌
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }

    # 请求体，包含文本和语言
    data = {
        'text': text,
        'language': language,
    }

    # 发送 POST 请求
    response = requests.post(url, headers=headers, json=data)

    # 如果请求成功，返回 API 响应的 JSON 数据
    if response.status_code == 200:
        try:
            speech = response.json()['response']['speech']['plain']['speech']
            return speech
        except:
            return "消息错误"
    else:
        return {"error": f"API连接失败: {response.status_code}, {response.text}"}


