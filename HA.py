import requests

def call_conversation_api(text,url,language='zh-cn', access_token="", agent_id=''):
    url = url+ '/api/services/conversation/process?return_response'
    # 设置请求头，包含访问令牌
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }

    # 请求体，包含文本和语言
    data = {
        'text': text,
        'agent_id': agent_id
    }

    # 发送 POST 请求
    try:
        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=10
        )

        # 检查响应状态
        if response.status_code == 200:
            print("✅ Response received:", response.json())
            try:
                speech = response.json()['service_response']['response']['speech']['plain']['speech']
                return speech
            except (KeyError, TypeError) as e:
                print(f"⚠️ 解析响应失败: {e}")
                return "消息格式错误"
        else:
            error_msg = f"API请求失败: {response.status_code}"
            print(f"❌ {error_msg}")
            return error_msg

    except requests.exceptions.SSLError as e:
        error_msg = f"SSL证书错误: {str(e)[:100]}"
        print(f"❌ {error_msg}")
        return "Home Assistant SSL连接失败"

    except requests.exceptions.Timeout:
        error_msg = "请求超时"
        print(f"❌ {error_msg}")
        return "Home Assistant 响应超时"

    except requests.exceptions.ConnectionError as e:
        error_msg = f"连接错误: {str(e)[:100]}"
        print(f"❌ {error_msg}")
        return "无法连接到 Home Assistant"

    except Exception as e:
        error_msg = f"未知错误: {str(e)[:100]}"
        print(f"❌ {error_msg}")
        return "调用 Home Assistant 失败"
