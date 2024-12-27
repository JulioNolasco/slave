#!/bin/sh
sysctl -w net.ipv4.ip_forward=1
iptables -t nat -A POSTROUTING -o wg0 -j MASQUERADE