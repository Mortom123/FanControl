# FanControl
Custom Linux Fancontroller to remap GPU Fans onto SYS_FAN Pins

This script runs on top of `fancontrol` under linux and helps to regulate fan speeds by setting the `/etc/fancontrol` file and restarting the `fancontrol` service, when needed.
My graphics card is broken so I had to remap the GPU fan onto a SYS_FAN Pin and set `fancontrol` params according to the GPU temperature obtained from `nvidia-smi`.
