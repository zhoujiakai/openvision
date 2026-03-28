# Buildroot

## WiFi 联网

网卡名一般是 `wlan0`（以 `ip link` 为准）。

```sh
# 1. 打开无线（若被 rfkill 关掉）
rfkill unblock wifi

# 2. 启用网卡
ip link set wlan0 up

# 3. 写配置（SSID/密码改成你的）
{
  echo 'ctrl_interface=/var/run/wpa_supplicant'
  echo 'update_config=1'
  wpa_passphrase "你的WiFi名" "你的密码"
} > /etc/wpa_supplicant.conf

# 4. 连网（后台）
wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant.conf

# 5. 拿 IP（Buildroot 常用 udhcpc；没有就试 dhclient）
udhcpc -i wlan0
```

连上后：`ip addr show wlan0` 看是否有地址。

---

## WIFI 开机自启

用下面的命令先装好 **`wifi-sta-up.sh` / `wifi-sta-down.sh`**（Buildroot 串口多为 **root**，一般**没有 sudo**，命令前不要加 `sudo`。）：

```sh
cd /userdata/ADK-DLRK3588   # 按你实际路径
mkdir -p /usr/local/bin
install -m 755 wifi-sta-up.sh wifi-sta-down.sh /usr/local/bin/
```

很多 ATK / Buildroot 镜像是 **init + `/etc/init.d/rcS`**，**没有 systemd**，所以会提示 `systemctl: command not found`。请用仓库里的 **`S99wifi-sta`**：

```sh
install -m 755 S99wifi-sta /etc/init.d/S99wifi-sta
/etc/init.d/S99wifi-sta start    # 立刻试一次
reboot                           # 验证开机是否自动连
```

网卡不叫 `wlan0` 时，编辑 **`/etc/init.d/S99wifi-sta`** 里的 `export WLAN_IF=...`。
