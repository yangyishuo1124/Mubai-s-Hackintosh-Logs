# AirPort_RTW89 源码核查 / Source investigation

## 状态 / Status

这是待构建的**诊断源码补丁**，不是已验证的 GUI 修复。硬盘 EFI 和驱动二进制未修改。基准为上游 `76d23fe`，补丁已通过 `git apply --check`；未编译、未运行上游测试、未实机启动。Windows 主机没有所需的 macOS/Xcode 构建环境。

This is a **diagnostic source patch**, not a verified GUI repair. The active EFI and driver binaries are unchanged. It targets upstream `76d23fe` and passes `git apply --check`. Compilation, upstream tests and hardware boot remain unperformed; the Windows host lacks the required macOS/Xcode build environment.

## 具体疑点 / Concrete candidate

`nativeAssociate()` 在已连接或连接中的 SSID/BSSID 相同后直接返回成功，没有比较认证方式与密钥。如果后续请求携带更新凭据，可能被当成重复请求忽略。但现有日志没有显示该分支是否命中，更没有证明密钥发生更新，因此不能认定它就是本机原因。不能直接删除此分支，否则正常重复请求也可能反复重置正在进行的握手。

`nativeAssociate()` returns success for the same SSID/BSSID while connected or joining without comparing authentication mode or credentials. An updated-credential request could therefore be suppressed. Current logs establish neither execution of that shortcut nor changed credentials, so this is not a proven cause here. Simply deleting the shortcut could repeatedly restart a valid handshake on ordinary retries.

## 补丁内容 / Patch contents

`rtw89-native-metadata.patch` 仅增加三处日志：关联的认证类型/密钥格式/长度、重复关联快捷分支、native DISASSOCIATE 的链路状态。没有改变连接逻辑。日志不输出密码、PMK、密钥字节或密钥散列；原驱动日志仍可能包含网络标识，整份报告仍需留在本地或脱敏。

The patch only logs association authentication/cipher/length metadata, execution of the duplicate-association shortcut, and link state on native DISASSOCIATE. Connection logic is unchanged. It does not log passwords, PMKs, key bytes or key hashes. Existing upstream logging may still expose network identifiers, so complete reports remain private or require redaction.

## 后续构建 / Later build

使用与基准一致的上游源码，在有完整构建条件的 macOS 环境中应用补丁，并按[上游说明](https://github.com/FranciumOS-org/AirPort_RTW89#building)构建和运行测试。应用示例：

Apply to the matching source snapshot on a macOS build host, then follow the [upstream build instructions](https://github.com/FranciumOS-org/AirPort_RTW89#building) and run its tests. Example application:

```sh
git apply --check /path/to/rtw89-native-metadata.patch
git apply /path/to/rtw89-native-metadata.patch
make fetch-firmware
make release
```

这些命令未在本机执行。构建通过后仍需核对产物、备份当前 EFI，再单独安排实机验证。本轮不要求用户重启测试。

These build commands have not been executed here. A successful build still requires artifact checks, an EFI backup and separate hardware validation. No reboot test is requested in this update.
