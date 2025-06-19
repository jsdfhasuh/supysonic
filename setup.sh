#!/bin/sh

# 启动第一个 Python 程序，并将其放入后台执行
python /app/run_daemon.py &
# Check if the socket file exists and remove it
if [ -e /tmp/supysonic/supysonic.sock ]; then
    rm /tmp/supysonic/supysonic.sock
fi
pid1=$!

# 启动第二个 Python 程序，并将其放入后台执行
python /app/run_supysonic.py &
pid2=$!


while true; do
    # 检查第一个程序的状态
    if ! kill -0 "$pid1" 2>/dev/null; then
        echo "run_daemon.py is not running, restarting..."
        rm /tmp/supysonic/supysonic.sock
        python /app/run_daemon.py &
        pid1=$!
    fi

    # 检查第二个程序的状态
    if ! kill -0 "$pid2" 2>/dev/null; then
        echo "run_supysonic.py is not running, restarting..."
        python /app/run_supysonic.py &
        pid2=$!
    fi

    # 等待一段时间再进行下一次检查，以避免过于频繁的检查
    sleep 60
done
