"""Aociety 本地模型启动脚本 — 一键启动所有本地推理服务

启动顺序:
  1. R1-Omni-0.5B  (端口 8001) — 文本情感推理
  2. Arousal Service (端口 8002) — 唤醒度/效价分析
  3. 硬件情感后端    (端口 8010) — 情感、TTS 与评估 API

用法:
  python scripts/start_all.py              # 启动所有服务
  python scripts/start_all.py --no-models   # 仅启动主后端（跳过本地模型）
  python scripts/start_all.py --no-backend  # 仅启动本地模型
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 端口配置
PORTS = {
    "main": int(os.environ.get("HARDWARE_CARE_PORT", "8010")),
    "r1_omni": int(os.environ.get("R1_OMNI_PORT", "8001")),
    "arousal": int(os.environ.get("AROUSAL_PORT", "8002")),
}

# 模型路径
MODELS_DIR = PROJECT_ROOT / "models"


def log(msg: str) -> None:
    print(f"[Aociety] {msg}")


def check_models() -> bool:
    """检查本地模型文件是否存在"""
    r1_model = MODELS_DIR / "r1-omni-0.5b"
    arousal_model = MODELS_DIR / "arousal"
    if not r1_model.exists():
        log(f"⚠ R1-Omni 模型未找到: {r1_model}")
        log("  请放入 models/r1-omni-0.5b/ 目录")
        return False
    if not arousal_model.exists():
        log(f"⚠ Arousal 模型未找到: {arousal_model}")
        log("  请放入 models/arousal/ 目录")
        return False
    return True


def start_r1_omni(background: list) -> subprocess.Popen | None:
    """启动 R1-Omni-0.5B 情感推理服务"""
    port = PORTS["r1_omni"]
    model_path = MODELS_DIR / "r1-omni-0.5b"
    log(f"启动 R1-Omni-0.5B → 端口 {port}")
    try:
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "services.r1_omni_server:app",
                "--host", "0.0.0.0",
                "--port", str(port),
                "--log-level", "warning",
            ],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        background.append(proc)
        return proc
    except FileNotFoundError:
        log(f"⚠ R1-Omni 服务启动失败 — 确保模型已部署在 {model_path}")
        return None


def start_arousal_service(background: list) -> subprocess.Popen | None:
    """启动 Arousal 唤醒度分析服务"""
    port = PORTS["arousal"]
    log(f"启动 Arousal Service → 端口 {port}")
    try:
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "services.arousal_server:app",
                "--host", "0.0.0.0",
                "--port", str(port),
                "--log-level", "warning",
            ],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        background.append(proc)
        return proc
    except FileNotFoundError:
        log("⚠ Arousal Service 启动失败")
        return None


def start_main_backend(background: list) -> subprocess.Popen:
    """启动主后端服务"""
    port = PORTS["main"]
    log(f"启动主后端服务 → 端口 {port}")
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "backend.main:app",
            "--host", "0.0.0.0",
            "--port", str(port),
            "--reload",
            "--log-level", "info",
        ],
        cwd=str(PROJECT_ROOT),
    )
    background.append(proc)
    return proc


def wait_for_ports() -> None:
    """等待所有端口就绪"""
    import socket
    for name, port in PORTS.items():
        if name == "main":
            continue  # 最后再等主服务
        for _ in range(30):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    log(f"  ✓ {name} 就绪 ({port})")
                    break
            except (ConnectionRefusedError, OSError):
                time.sleep(0.5)
        else:
            log(f"  ✗ {name} 未就绪 ({port}) — 继续启动")


def main() -> None:
    parser = argparse.ArgumentParser(description="Aociety 本地服务启动器")
    parser.add_argument("--no-models", action="store_true", help="跳过本地模型")
    parser.add_argument("--no-backend", action="store_true", help="跳过主后端")
    args = parser.parse_args()

    log("=" * 50)
    log("Aociety — 统一服务启动")
    log(f"   主后端:  {PORTS['main']}")
    log(f"   R1-Omni: {PORTS['r1_omni']}")
    log(f"   Arousal: {PORTS['arousal']}")
    log("=" * 50)

    background: list[subprocess.Popen] = []

    try:
        # 1. 检查模型
        if not args.no_models:
            check_models()

        # 2. 启动本地模型
        if not args.no_models:
            start_r1_omni(background)
            start_arousal_service(background)
            wait_for_ports()
        else:
            log("跳过本地模型启动")

        # 3. 启动主后端
        if not args.no_backend:
            start_main_backend(background)

        log("所有服务已启动。按 Ctrl+C 停止。")

        # 等待子进程
        for proc in background:
            proc.wait()

    except KeyboardInterrupt:
        log("正在停止所有服务...")
        for proc in background:
            proc.terminate()
        log("所有服务已停止。")


if __name__ == "__main__":
    main()
