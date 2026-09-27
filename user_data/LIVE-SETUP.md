# 独立实盘配置

此配置沿用现有 Binance USDT 逐仓合约和 BaterHiro 策略（当前策略返回 1 倍杠杆），不是现货配置。尚未启动，也未验证真实账户连接。

- 模拟盘继续使用原 config.json、数据库、端口和 Telegram。
- 实盘使用 config.live.json + config.live.private.json、trades-live.sqlite、freqtrade-live.log 和本机 8082 端口。
- 初始状态 stopped，不会自动按策略开仓；手动强制开仓已禁用。实盘进程仍会连接交易所，启动不是离线检查。
- 暂定每笔 20 USDT、最多 1 笔，需在启用前确认预算及各交易对最低下单量。最低交易额调整可能使实际投入高于设定值。
- 开启交易所止损（市价止损）；需验证当前安装版本与币安 API 的兼容性。止损不保证成交价格。
- Telegram 已关闭；如需开启，必须使用另一个机器人。
- 网页 API 独立随机密码保存在私密配置中，用户名 freqtrader-live。

## 启动前

1. 确认是支持当前配置的币安账户和合约产品；地区版本或现货账户不能直接沿用。
2. 准备专用 API key，开启读取和合约交易权限、绑定运行机器公网出口 IP，关闭提现权限。
3. 在本机编辑 config.live.private.json，填入 exchange.key 和 exchange.secret。不要发送密钥或提交 Git。
4. 核对合约钱包资金、单向持仓、单资产模式，以及该账户现有仓位和其他机器人的使用情况。优先使用独立账户/子账户，避免混用仓位。
5. 确认策略、预算和选币列表（当前沿用动态成交量前 50 及过滤器），检查币安最小交易额、软件/API兼容性。当前准备工作没有评估策略收益。

## 新克隆仓库的凭据初始化

现有机器已经有私密配置，不要覆盖。新克隆仓库在项目根目录运行以下命令，以空白模板创建私密配置并生成独立网页密码：

```bash
python3 - <<'PYSETUP'
import json, os, secrets
from pathlib import Path
p = Path("user_data/config.live.private.json")
c = json.loads(Path("user_data/config.live.private.example.json").read_text())
for field in ("password", "jwt_secret_key", "ws_token"):
    c["api_server"][field] = secrets.token_urlsafe(32)
fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as f:
    json.dump(c, f, indent=4)
    f.write("\n")
PYSETUP
```

随后在本机私密配置中填写币安凭据。依赖和 `.venv` 按仓库安装说明准备。

## 本机启动

在项目根目录执行：

```bash
./user_data/start-live.sh
```

脚本要求使用项目 .venv，且拒绝 FREQTRADE__ 环境覆盖，防止串用模拟盘设置。缺少密钥时直接退出。
打开 http://127.0.0.1:8082 ，使用私密配置中的 API 用户名和密码登录。
启动后保持 stopped；账户及额度检查完成后，在实盘界面明确执行 Start 才开启策略交易。

停止策略不等于平仓；有真实持仓时，不要直接关进程或删除数据库。重启要保留同一实盘数据库以便接管持仓。

当前启动入口用于本机，不使用原 docker-compose.yml（原文件硬编码了模拟盘数据库和示例策略）。没有新增开机自启或 Docker 服务。
策略文件与模拟盘共用；修改策略前需要同时考虑两个实例。实盘配置、策略、启动脚本和空白凭据模板纳入 Git；真实私密配置、模拟盘配置、数据库和日志继续忽略。
