import http
import json
import time
import uvicorn
from fastapi import FastAPI, Request
import HA

app = FastAPI()
host = "192.168.43.203" # QQ机器人主机
port = 3000
#Homeassistant
ha_url = "https://example.com:8124"
secret = "S74"
group_list = [63616] #QQ群白名单

def send_request_with_retry(host, port, path, payload, headers, max_retries=3, delay=1):
    retries = 0
    while retries < max_retries:
        try:
            conn = http.client.HTTPConnection(host, port)
            conn.request("POST", path, payload, headers)
            response = conn.getresponse()
            data = response.read()
            print("Response received:", data.decode("utf-8"))
            conn.close()
            return data  # 请求成功，返回响应数据
        
        except http.client.RemoteDisconnected:
            print(f"Attempt {retries + 1} failed: Remote server disconnected without response.")
            retries += 1
            if retries < max_retries:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)  # 等待一段时间再重试
            else:
                print("Max retries reached, failing.")
                raise  # 超过最大重试次数，抛出异常
        
        except Exception as e:
            print(f"Error: {str(e)}")
            break  # 其他异常，直接退出
        
@app.post("/")
async def root(request: Request):
    data = await request.json()  # 获取事件数据
    # print(data)
    execute(data)
    return {}

def parse_data(data):
    group_id = data.get('group_id', None)
    message_text = data.get('message', [{}])[0].get('data', {}).get('text', None)
    
    print(f'群聊:{group_id}  消息:{message_text}')
    return group_id, message_text


def execute(data):
    group_id , message_text = parse_data(data)
    if(group_id in group_list):
        if message_text.startswith('/ha'):
            response_data = HA.call_conversation_api(message_text.removeprefix('/ha'),ha_url,access_token=secret) 
            send_group_message(group_id,response_data)
            
def send_group_message(group_id,message):
    payload ={
   "group_id": 123,
   "message": [
      {
         "type": "text",
         "data": {
            "text": "HelloKitty"
         }
      }
    ]
    }
    payload["group_id"] = group_id
    payload["message"][0]["data"]["text"] = message
    print(f"群聊:{group_id} 消息:{message}")
    headers = {
    'Content-Type': 'application/json'
    }

    payload_data = json.dumps(payload)
    try:
        response = send_request_with_retry(host, port, "/send_group_msg", payload_data, headers)
        print("Request successful:", response)
    except Exception as e:
        print(f"Request failed: {str(e)}")



if __name__ == "__main__":
    uvicorn.run(app, port=8080,host="0.0.0.0")