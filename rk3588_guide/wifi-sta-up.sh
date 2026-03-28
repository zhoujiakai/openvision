#!/bin/sh
# 开机拉起 WiFi：rfkill、up、wpa_supplicant、udhcpc（需已存在 /etc/wpa_supplicant.conf）
set -e
WLAN_IF="${WLAN_IF:-wlan0}"

rfkill unblock wifi 2>/dev/null || true
ip link set "$WLAN_IF" up
wpa_supplicant -B -i "$WLAN_IF" -c /etc/wpa_supplicant.conf
# -b 后台续租；若没有 -b，可改成前台由 systemd Type=simple 另写服务
if command -v udhcpc >/dev/null 2>&1; then
  udhcpc -i "$WLAN_IF" -b
elif command -v dhclient >/dev/null 2>&1; then
  dhclient -nw "$WLAN_IF" 2>/dev/null || dhclient "$WLAN_IF" &
else
  echo "wifi-sta-up: 未找到 udhcpc 或 dhclient" >&2
  exit 1
fi
