#!/bin/bash
ip route add 192.168.0.0/16 via 192.168.100.2 dev eth0
ip route add 172.16.0.0/12 via 192.168.100.2 dev eth0
ip route add 10.0.0.0/8 via 192.168.100.2 dev eth0
ip route add 100.64.0.0/10 via 192.168.100.2 dev eth0
ip route add 198.18.0.0/15 via 192.168.100.2 dev eth0