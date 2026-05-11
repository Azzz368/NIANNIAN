import os, requests, json, base64
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("AI302_API_KEY")
hdrs = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

# 真实 HTTPS 图片（公开可访问）
img_https = "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/Above_Gotham.jpg/320px-Above_Gotham.jpg"

tests = [
    # omni3 + HTTPS URL via images[]
    {"prompt": "camera pans slowly", "duration": 5, "aspect_ratio": "auto",
     "mode": "pro", "images": [img_https], "o1_type": "firstTail"},
    # omni3 + HTTPS via image field
    {"prompt": "camera pans slowly", "duration": 5, "aspect_ratio": "auto",
     "mode": "pro", "image": img_https, "o1_type": "firstTail"},
    # omni3 + HTTPS via image_url field
    {"prompt": "camera pans slowly", "duration": 5, "aspect_ratio": "auto",
     "mode": "pro", "image_url": img_https, "o1_type": "firstTail"},
    # omni3 + referImage type
    {"prompt": "camera pans slowly", "duration": 5, "aspect_ratio": "auto",
     "mode": "pro", "images": [img_https], "o1_type": "referImage"},
]

print("Testing omni3 with real HTTPS image URL...\n")
for i, b in enumerate(tests):
    try:
        r = requests.post("https://api.302.ai/klingai/m2v_omni_3_video",
                          headers=hdrs, json=b, timeout=30)
        d = r.json()
        tid = d.get("data", {}).get("task", {}).get("id", "")
        ti  = d.get("data", {}).get("task", {}).get("taskInfo", {})
        err = (d.get("error") or {}).get("message_cn", "")
        print(f"[{i}] HTTP {r.status_code}  task={tid or 'NONE'}")
        print(f"     taskInfo: {json.dumps(ti, ensure_ascii=False)}")
        if err:
            print(f"     err: {err[:60]}")
        # 关键检查：taskInfo 是否包含图片相关字段
        has_img = any(k in str(ti) for k in ["image", "img", "first", "refer"])
        print(f"     image in taskInfo: {has_img}")
        print()
    except Exception as e:
        print(f"[{i}] EXC: {e}\n")
