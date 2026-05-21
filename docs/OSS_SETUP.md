# 接入阿里云 OSS 持久化（数据永不丢）

## 为什么需要？

念念目前把所有用户/人物/对话/资料/上传的文件都存成 JSON+二进制文件到本地 `data/` 目录。

- 本地跑：不丢
- Render Free 计划：每次 push、每次部署后**数据全没**（容器文件系统是临时的）
- Render Starter $7：必须额外**手动挂一块 Persistent Disk**，否则也会丢
- 即使挂了 Disk，多实例扩容时数据会分裂

**接 OSS 后**：本地继续读写（速度快），每次写完异步推到 OSS，启动时从 OSS 拉回。Render 容器随便重启都不丢。免费额度足够个人使用。

---

## 一、开通阿里云 OSS（10 分钟）

### 1) 注册 / 登录阿里云

- 国际站：https://www.alibabacloud.com/（推荐，OSS 香港节点 Render 访问快）
- 中国站：https://www.aliyun.com/

### 2) 开通 OSS 服务

控制台搜「**对象存储 OSS**」→ 立即开通（按量付费，不存就不收钱，新用户有免费额度）。

### 3) 创建 Bucket（存储桶）

- 控制台 → OSS → Bucket 列表 → **创建 Bucket**
- 名称：`niannian-data`（全局唯一，可加后缀如 `niannian-data-yourname`）
- 区域：**香港**（如果用户主要在大陆/亚太/Render 香港节点）或**美国西部**（Render 默认 Oregon）
- 存储类型：**标准存储**
- 读写权限：**私有**（重要！数据安全）
- 其余默认，创建

记下两个信息：
- **Bucket 名称**：`niannian-data-xxx`
- **Endpoint**：例如 `oss-cn-hongkong.aliyuncs.com` 或 `oss-us-west-1.aliyuncs.com`（在 Bucket 概览页可看）

### 4) 创建 AccessKey

- 控制台右上角头像 → **AccessKey 管理**
- 推荐：**创建 RAM 子账号**而不是用主账号 AK（更安全）
  - 控制台搜 RAM → 用户 → 创建用户 `niannian-app`
  - 勾选「**OpenAPI 调用访问**」→ 创建
  - **复制并保存** `AccessKey ID` 和 `AccessKey Secret`（Secret 只显示一次！）
  - 给该用户授权：勾选 `AliyunOSSFullAccess`（或更精细的只对你那个 Bucket 的权限）

至此你拿到 4 个值：
```
OSS_ACCESS_KEY_ID       = LTAI5tXXXXXXXXXX
OSS_ACCESS_KEY_SECRET   = XXXXXXXXXXXXXXXXXXXXXXXX
OSS_BUCKET              = niannian-data-xxx
OSS_ENDPOINT            = oss-cn-hongkong.aliyuncs.com
```

---

## 二、配置念念（本地）

在项目根 `.env` 文件加（如果没有就新建）：

```ini
# 启用 OSS 持久化
OSS_ENABLE=1
OSS_ACCESS_KEY_ID=LTAI5tXXXXXXXXXX
OSS_ACCESS_KEY_SECRET=XXXXXXXXXXXXXXXXXXXXXXXX
OSS_BUCKET=niannian-data-xxx
OSS_ENDPOINT=oss-cn-hongkong.aliyuncs.com
OSS_PREFIX=nian/

# 安全：JWT 和访问码
JWT_SECRET=换成你自己的随机字符串
OWNER_ACCESS_CODE=666666
```

安装依赖：
```powershell
pip install oss2
```

启动后端：
```powershell
cd backend
uvicorn main:app --reload
```

启动日志会显示：
```
[oss] enabled, bootstrap pulling from OSS...
[oss] bootstrap pull done, synced N files from nian/
```

测试：登录 → 创建一个人物 → 填资料 → 重启服务 → 资料还在 → 去 OSS 控制台看 Bucket，应该有 `nian/users/owner/memorials/m_xxx/meta.json` 等文件。

---

## 三、配置念念（Render 部署）

在 Render Dashboard → 你的服务 → **Environment** 加 5 个环境变量：

| Key | Value | 说明 |
|---|---|---|
| `OSS_ENABLE` | `1` | 启用 |
| `OSS_ACCESS_KEY_ID` | `LTAI5tXXX...` | RAM 子账号 AK |
| `OSS_ACCESS_KEY_SECRET` | `XXX...` | RAM 子账号 Secret（设为 secret） |
| `OSS_BUCKET` | `niannian-data-xxx` | 你的桶 |
| `OSS_ENDPOINT` | `oss-cn-hongkong.aliyuncs.com` | 你的 endpoint |

保存 → Render 自动重新部署。看 Logs 应该输出 `[oss] enabled, bootstrap pulling...`。

**之后即使去掉 Persistent Disk，数据也不会丢**（OSS 是 single source of truth）。

---

## 四、一次性把已有本地数据推到 OSS

如果你本地已经有人物数据，第一次启用 OSS 后想把它们全推上去：

```python
# 启动 Python，在 backend/ 目录下：
from core import storage, oss_sync
oss_sync.push_all()
# 输出 [oss] push_all done, uploaded N files
```

或者写个一行脚本：
```powershell
cd backend
python -c "from core import storage, oss_sync; oss_sync.push_all()"
```

---

## 五、费用估算

OSS 香港节点价格（截至 2026）：
- 存储：约 ¥0.12 / GB / 月
- 上行流量（写）：免费
- 下行流量（读）：约 ¥0.5 / GB（公网下载，内网免费）
- 请求次数：每万次 ¥0.01

念念一个用户的数据量大约：
- 文字（人物档案、对话）：< 1MB
- 上传的图片：每张 1~5 MB
- 上传的音频：每个 5~20 MB

**100 个用户、每人 100MB → 10GB → 月费约 ¥1.2**。新用户 6 个月内还有 5GB 免费包。基本可以忽略。

---

## 六、回退

任何时候只要把 Render 的 `OSS_ENABLE` 设成 `0` 或删掉环境变量，就回到本地文件模式（依赖 Persistent Disk）。OSS 上的数据不会自动删除。

---

## 七、安全建议

1. **RAM 子账号** + **最小权限**（只授权指定 Bucket 的 OSS 操作）
2. AccessKey 只放在环境变量，**不要写进代码**
3. Bucket 权限保持 **私有读写**（公网无法直接拉数据）
4. JWT_SECRET 在 Render 用 `generateValue` 自动生成（render.yaml 已配置）
5. 定期在阿里云控制台开启 **Bucket 版本控制**，防止误删
