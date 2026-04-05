# 烧录系统

> 教程：`/10、用户手册/02、开发文档/02【正点原子】ATK-DLRK3588嵌入式Linux系统开发手册V1.1.pdf`

## 概念

说明下 **RK3588** 板子和工具。

**板子**

开发板的逻辑结构大概像这样，手头是「正点原子ATK-DL**RK3588**」8G+64G的。

```
  ┌────────────────────────────────────────────────────┐                       
  │            正点原子ATK-DLRK3588 开发板                │                     
  ├────────────────────────────────────────────────────┤
  │                                                    │
  │   ┌──────────────────┐      ┌──────────────────┐   │
  │   │     核心板        │      │     底板          │   │
  │   ├──────────────────┤      ├──────────────────┤   │
  │   │ • RK3588 SoC     │◄─────┤  • 接口扩展       │   │
  │   │ • LPDDR4X 内存    │      │  • 电源管理       │   │
  │   │ • eMMC 存储       │      │  • 外设芯片       │   │
  │   └──────────────────┘      └──────────────────┘   │
  └────────────────────────────────────────────────────┘
```

**系统**

为板子选择一个操作系统，可以是：Ubuntu 22.04、Buildroot、Debian等。正点原子的这个板子**官方不提供ubuntu系统镜像**，只有Buildroot（轻量级）、Debian（完整Linux系统）这两种Linux系统，和Android系统。

Buildroot是一个非常轻量的Linux操作系统：启动快、体积小。它的版本号，像这样：Buildroot 2021.11。所有的版本都是以「Buildroot 年份.月份」来命名，一般两个月出一个新版本。

正点原子有提供Buildroot系统镜像，直接点击几下就把烧录系统这一步做好了。

**工具**

烧系统使用瑞芯微官方专用工具 **RKDevTool**，其他访问板子和传输文件的工具随便用。

- `RKDevTool.exe`：瑞芯微官方专用工具，烧系统要用。
- `Mobaxterm.exe`：通用工具，用来访问板子，进入板子命令行。
- `adb.exe`：文件传输软件，用来给板子传文件，需要串口连接。

**接口**

- **UART接口**：用来查看系统启动日志，就是板子启动过程中看这么一下，后面就没啥用了。另外的两个`TYPE-C`接口在板子启动过程中是死的，板子启动完了，它俩才活过来，因此，只有`UART`接口能看系统**启动日志**。
- **TYPE-C0接口**：烧系统、传文件，都需要连着这个接口。
- **电源接口**：接通电源。

- **RST按键**：板子重启。
- **POWERON按键**：板子开机关机。

## 操作

usb线连通板子`UART口`和windows电脑`usb口`，板子接通电源。在windows中打开`RKDevTool.exe`（瑞芯微工具），选择从正点原子官网下载好的buildroot_r8镜像（r8表示rk3588，r6表rk3568，这不是正式命名，不用管），右键加载配置，点击执行，就搞定了。

用Mobaxterm进入板子查看Buildroot版本：`cat /etc/os-release`，可以看到板子上装的是`Buildroot 2021.11`版本的系统。**rk3588是2022年发布的**，操作系统用这个Buildroot 2021.11版本应该是合适的。

Python每年10月发布一个大版本，**Python3.10是2021年发布的**，最新的版本是2025年发布的Python3.14。

Buildroot 2021.11上预装的是Python3.10，Buildroot 2021.11 上运行python3.10应该是合适的。





# Buildroot系统

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



