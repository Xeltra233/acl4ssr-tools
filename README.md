# ACL4SSR 本地转换工具

把 Clash/Mihomo 的裸节点片段转换成可导入的 Mihomo YAML，并套用远程原版 ACL4SSR 全分组模板。

远程模板：

```text
https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/config/ACL4SSR_Online_Full.ini
```

## 用法

### 双击自动转换

把节点 `.txt` 文件放到这个目录：

```text
C:\project\acl4ssr-tools
```

然后双击：

```text
C:\project\acl4ssr-tools\run_convert_acl4ssr_full.bat
```

脚本会自动扫描同目录下所有 `.txt` 文件，并为每个文件生成：

```text
原文件名.acl4ssr-full.yaml
```

例如：

```text
nodes.txt -> nodes.acl4ssr-full.yaml
```

`convert.log` 会记录每次双击运行的结果。不要优先双击 `.py` 文件，Windows 可能会用没装依赖的 Python 或直接用编辑器打开它。

### 命令行转换

把节点片段保存成 UTF-8 文件，例如 `nodes.txt`。可以是这种开头：

```yaml
- { name: ' 香港 01', type: anytls, server: example.com, port: 35101, password: redacted, client-fingerprint: chrome, udp: true, alpn: [h2, http/1.1], sni: fs1.example.com }
- { name: ' 新加坡 01', type: anytls, server: example.com, port: 35121, password: redacted, client-fingerprint: chrome, udp: true, alpn: [h2, http/1.1], sni: dl.example.com }
```

生成 ACL4SSR 全分组 YAML：

```powershell
python C:\project\acl4ssr-tools\fragment_to_mihomo_yaml.py C:\path\to\nodes.txt `
  --acl4ssr-template https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/config/ACL4SSR_Online_Full.ini `
  -o C:\path\to\acl4ssr-full.yaml
```

## 说明

- 输入没有 `proxies:` 顶层字段时，脚本会自动补上。
- 输入里已有 `proxy-groups` 时，使用 `--acl4ssr-template` 会替换成远程 ACL4SSR 模板分组。
- 香港、台湾、澳门、新加坡、日本、美国会按节点名自动归到对应分组；其他地区会进入 `🎏 其他`。
- `anytls` 需要使用支持该协议的 Mihomo 内核，旧版 Clash 可能无法加载。
- 重名的节点会自动改名为 `原名 (2)`、`原名 (3)`，避免 Mihomo 因 `duplicate name` 拒绝加载；改名保留原名前缀，地区分组不受影响。
- 生成前会做一次结构校验（重名、悬空分组引用、规则指向缺失的分组或 rule-provider 等），校验不通过会报错并不写文件。
