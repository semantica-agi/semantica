# LDAP 登录(COWIN Explorer)

Explorer 后端默认使用共享 `X-API-Key`(或显式的匿名模式)保护所有
API 路由。本模块在此基础上增加**面向人的 LDAP 登录**:用户在登录页
输入域账号,后端对 LDAP/Active Directory 做 bind 验证,签发一个
HMAC-SHA256 签名的短期 token;此后所有请求以
`Authorization: Bearer <token>` 携带身份,WebSocket 以 `?token=` 携带。

共享 API Key 依然可用(用于脚本与服务间调用);两种凭证走同一条
`require_auth` 认证链,互不影响。

## 启用

```bash
pip install 'semantica[auth-ldap]'   # 提供 ldap3

export SEMANTICA_LDAP_URL="ldaps://dc01.example.com:636"
export SEMANTICA_AUTH_SECRET="至少 32 字节的随机串"   # openssl rand -hex 32

# 方式一:直接绑定(DN 模板)
export SEMANTICA_LDAP_USER_DN_TEMPLATE="uid={username},ou=people,dc=example,dc=com"

# 方式二:先检索后绑定(AD 常用)
# export SEMANTICA_LDAP_BIND_DN="cn=svc-semantica,ou=service,dc=example,dc=com"
# export SEMANTICA_LDAP_BIND_PASSWORD="***"
# export SEMANTICA_LDAP_SEARCH_BASE="dc=example,dc=com"
# export SEMANTICA_LDAP_USER_FILTER="(sAMAccountName={username})"

semantica-explorer --graph my_graph.json
```

只要 `SEMANTICA_LDAP_URL` 与 `SEMANTICA_AUTH_SECRET` 同时存在,登录即
启用;前端 `/api/auth/status` 检测到后自动展示登录页。未启用时行为
与之前完全一致(匿名 / API Key / 503 fail-closed)。

## Docker Compose 部署

`docker-compose.yml` 已内置全部 LDAP 参数(经 `${VAR:-默认值}` 插值透传,
默认为空 = 不启用)。最省事的方式是在 compose 文件旁放一个 `.env`:

```bash
# .env(与 docker-compose.yml 同目录)
SEMANTICA_LDAP_URL=ldaps://dc01.example.com:636
SEMANTICA_AUTH_SECRET=<openssl rand -hex 32>
SEMANTICA_LDAP_BIND_DN=cn=svc-semantica,ou=service,dc=example,dc=com
SEMANTICA_LDAP_BIND_PASSWORD=***
SEMANTICA_LDAP_SEARCH_BASE=dc=example,dc=com

docker compose up -d
```

要点:

- 镜像的锁定依赖已包含 ldap3(`explorer-extra-*.txt` 以
  `--extra explorer --extra auth-ldap` 生成),开箱即用;
- 容器内访问宿主机上的目录服务器用 `host.docker.internal`;
- 服务账号密码等敏感值建议走密钥管理(或至少保证 `.env` 权限为 600),
  不要写进 compose 文件本身;
- 开发用的 `docker-compose.dev.yml` 默认匿名,文件内附了切换到 LDAP
  登录的注释示例。

## 环境变量

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `SEMANTICA_AUTH_SECRET` | token 签名密钥(HMAC-SHA256)。必配 | 无 |
| `SEMANTICA_AUTH_TOKEN_TTL` | token 有效期(秒) | `28800`(8 小时) |
| `SEMANTICA_LDAP_URL` | 目录地址 `ldap://host:389` 或 `ldaps://host:636`。必配 | 无 |
| `SEMANTICA_LDAP_STARTTLS` | `true` 时对 ldap:// 连接升级 StartTLS | `false` |
| `SEMANTICA_LDAP_VERIFY_CERTS_OFF` | 任意真值跳过服务器证书校验(仅限内网测试) | 校验 |
| `SEMANTICA_LDAP_TIMEOUT` | 连接/检索超时(秒) | `10` |
| `SEMANTICA_LDAP_USER_DN_TEMPLATE` | 直接绑定 DN 模板,含 `{username}` | 无 |
| `SEMANTICA_LDAP_BIND_DN` | 服务账号 DN(检索-绑定模式) | 无 |
| `SEMANTICA_LDAP_BIND_PASSWORD` | 服务账号密码 | 无 |
| `SEMANTICA_LDAP_SEARCH_BASE` | 检索基础 DN | 无 |
| `SEMANTICA_LDAP_USER_FILTER` | 检索过滤模板,含 `{username}` | `(sAMAccountName={username})` |

两种绑定模式二选一;同时配置会被拒绝启动登录。

## token 内容

登录成功后 token 携带目录中的属性(取 `mail`、`displayName`、
`memberOf`、`cn`),映射为 claims:`sub`(账号)、`name`、`email`、
`groups`、`dn`、`iat`、`exp`。前端用 `/api/auth/me` 恢复会话。
密码不会写入 token,也不会出现在任何日志里。

## API

- `GET /api/auth/status` — 公开。`{"anonymous":false,"ldap":true,"api_key":false}`
- `POST /api/auth/login` — 公开。请求 `{"username","password"}`;
  `200` 返回 `{token, expires_at, user}`;`401` 凭证错误;
  `503` 未配置或目录不可达。
- `GET /api/auth/me` — 需要已认证。返回当前身份;Bearer token 返回
  用户信息,API Key / 匿名返回 `user: null`。

## 行为细节

- **fail-closed 不变**:既没有 API Key 也没有启用 LDAP 登录时,
  受保护路由返回 `503`;显式匿名仍需 `SEMANTICA_ALLOW_ANONYMOUS=true`。
- **Bearer 优先且不回退**:请求带了 `Authorization: Bearer` 但 token
  无效/过期时,直接 `401`(即使 API Key 正确),避免过期会话被静默放过。
- **不泄露账号是否存在**:未知用户与错误密码同样返回 `401`。
- **用户名转义**:进入检索过滤器前经 `escape_filter_chars`,直接绑定
  模式下对 DN 中的 `,`/`\\` 做转义,防注入。
- **WebSocket**:浏览器无法自定义握手头,token 以 `?token=` 传递;
  原有 `?api_key=` 继续可用。

## 与溯源(Provenance)的衔接点

`semantica/provenance/manager.py` 已有 PROV-O `wasAttributedTo` 归因
能力。token claims(`sub`/`dn`)是后续把图变更、决策记录归因到具体
登录用户的天然入口;当前版本未自动写入,留作后续增量。

## 测试

```bash
python -m pytest tests/explorer/test_explorer_ldap_auth.py -q
```

测试不访问网络:ldap3.Connection 以桩替换,覆盖直接绑定、检索-绑定、
凭证错误、目录不可达等分支;token 部分覆盖签发/校验/过期/篡改/换钥。