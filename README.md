# ACL4SSR 本地转换工具

把 Clash/Mihomo 的节点片段或完整配置转换成可导入的 Mihomo YAML，并套用远程原版 ACL4SSR 全分组模板。

远程模板：

```text
https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/config/ACL4SSR_Online_Full.ini
```

## 用法

### 双击自动转换

把输入文件放到这个目录：

```text
C:\project\acl4ssr-tools
```

支持的输入：

- 裸节点片段 `.txt`：`- { name: ..., type: ... }` 列表，或带 `proxies:` 顶层字段的片段
- 完整配置 `.yaml` / `.yml`：自带 `proxies`，以及 `dns`、`port`、`tun` 等运行时段

然后双击：

```text
C:\project\acl4ssr-tools\run_convert_acl4ssr_full.bat
```

脚本会扫描同目录下所有输入文件，为每个文件生成：

```text
原文件名.acl4ssr-full.yaml
```

例如：

```text
nodes.txt   -> nodes.acl4ssr-full.yaml
profile.yaml -> profile.acl4ssr-full.yaml
```

已经是 `.acl4ssr-full.yaml` 的输出文件会被跳过，不会重复转换。已经套用过 ACL4SSR 规则的 YAML（`rule-providers` 指向 ACL4SSR，或分组里带“漏网之鱼”）也会被识别并跳过，转换时打印 `SKIP: xxx.yaml 已套用 ACL4SSR 规则，跳过不重新生成`，原文件不改动。多个输入映射到同一输出名时脚本直接报错退出，不会覆盖。

`convert.log` 会记录每次双击运行的结果。不要优先双击 `.py` 文件，Windows 可能会用没装依赖的 Python 或直接用编辑器打开它。

### 命令行转换

裸节点片段：

```powershell
python C:\project\acl4ssr-tools\fragment_to_mihomo_yaml.py C:\path\to\nodes.txt `
  --acl4ssr-template https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/config/ACL4SSR_Online_Full.ini `
  -o C:\path\to\acl4ssr-full.yaml
```

完整配置（保留其 DNS）：

```powershell
python C:\project\acl4ssr-tools\fragment_to_mihomo_yaml.py C:\path\to\profile.yaml `
  --acl4ssr-template https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/config/ACL4SSR_Online_Full.ini `
  -o C:\path\to\acl4ssr-full.yaml
```

## 保留源配置的 DNS

输入是完整 YAML 时，只有 `proxy-groups`、`rule-providers`、`rules` 会被 ACL4SSR 模板替换，其余顶层配置原样保留：

- `dns` 整段逐字段保留，包括 `enhanced-mode`、`fake-ip-filter`、`nameserver-policy`、`proxy-server-nameserver`、`respect-rules`
- `port`、`socks-port`、`mixed-port`、`allow-lan`、`mode`、`log-level`、`external-controller`、`unified-delay`、`ipv6`、`tun` 等运行时段保留
- 输出里 `dns` 固定排在 `proxies` 之前

`dns` 里引用的 `rule-set:` 会跟着一起处理，因为模板替换了整块 `rule-providers`：

- 源配置自己定义的 provider（例如 Mesl 给 `nameserver-policy` 用的 `cn-domain`）会被复制进新的 `rule-providers`，DNS 分流语义保持不变，转换时打印 `info: kept dns rule-set provider: cn-domain`
- 源配置没有定义、模板也不提供的引用会被裁剪，并打印 `warning: dropped dangling rule-set:... reference from dns`

不做这步处理时，Mihomo 会直接拒绝加载并报 `not found rule-set: cn-domain`。

## 说明

- 输入没有 `proxies:` 顶层字段时，脚本会自动补上。
- 香港、台湾、澳门、新加坡、日本、美国会按节点名自动归到对应分组；其他地区会进入 `🎏 其他`。
- `anytls` 需要使用支持该协议的 Mihomo 内核，旧版 Clash 可能无法加载。
- 重名的节点会自动改名为 `原名 (2)`、`原名 (3)`，避免 Mihomo 因 `duplicate name` 拒绝加载；改名保留原名前缀，地区分组不受影响。
- 生成前会做一次结构校验（重名、悬空分组引用、规则指向缺失的分组或 rule-provider 等），校验不通过会报错并不写文件。
- ACL4SSR 模板自带的 `URL-REGEX` 规则是 Mihomo 不支持的类型，启动时会产生若干 `unsupported rule type: URL-REGEX` 警告，不影响加载与代理。
