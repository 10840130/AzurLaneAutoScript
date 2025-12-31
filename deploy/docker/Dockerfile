FROM python:3.7-bullseye

WORKDIR /app/AzurLaneAutoScript

# 先处理依赖（利用缓存）
COPY requirements.txt /tmp/requirements.txt

RUN apt update \
    && apt install -y git adb libgomp1 openssh-client pkg-config libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libswresample-dev libavfilter-dev \
    && git config --global --add safe.directory '*' \
    && pip install --upgrade pip \
    && pip install "cython<3" \
    && pip install --no-build-isolation av==10.0.0 \
    && pip install -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt \
    && rm -r ~/.cache/pip

# --- 关键修改：把当前目录下的所有代码拷贝进去 ---
COPY . . 
# -------------------------------------------

# 建议在 CMD 中加上参数，确保 Web 界面能被外部访问
CMD ["python", "gui.py", "--host", "0.0.0.0", "--port", "22267"]