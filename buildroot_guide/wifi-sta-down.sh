#!/bin/sh
# 停止 WiFi 客户端（供 systemd stop 使用）
WLAN_IF="${WLAN_IF:-wlan0}"

wpa_cli -i "$WLAN_IF" terminate 2>/dev/null || killall wpa_supplicant 2>/dev/null || true
if command -v udhcpc >/dev/null 2>&1; then
  killall udhcpc 2>/dev/null || true
fi
if command -v dhclient >/dev/null 2>&1; then
  dhclient -r "$WLAN_IF" 2>/dev/null || true
fi
