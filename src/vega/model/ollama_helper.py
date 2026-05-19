"""Ollama helper - model discovery, curated list, install/pull logic."""
from __future__ import annotations

import shutil
import subprocess
import sys

import httpx

CURATED_MODELS = {
    "Lightweight (under 5B)": [
        ("llama3.2:3b", "Meta Llama 3.2 3B", "Best small general purpose"),
        ("qwen3.5:4b", "Qwen 3.5 4B", "Newest, highest quality per param"),
        ("gemma3:4b", "Google Gemma 3 4B", "Latest Google, strong all-rounder"),
        ("ministral-3:3b", "Mistral Ministral 3B", "Fastest inference"),
        ("codegemma:2b", "Google CodeGemma 2B", "Code on anything"),
    ],
    "Medium (under 9B)": [
        ("llama3.1:8b", "Meta Llama 3.1 8B", "Most popular, battle-tested"),
        ("qwen3.5:9b", "Qwen 3.5 9B", "Excellent coder for its size"),
        ("mistral:7b", "Mistral 7B", "Fast classic, great latency"),
        ("ministral-3:8b", "Mistral Ministral 8B", "Efficient 8B, fast inference"),
        ("deepseek-r1:7b", "DeepSeek R1 7B", "Reasoning specialist"),
    ],
    "Larger (under 16B)": [
        ("qwen3:14b", "Qwen 3 14B", "Strong all-rounder"),
        ("gemma3:12b", "Google Gemma 3 12B", "Best sub-16B"),
        ("phi4:14b", "Microsoft Phi-4 14B", "Strongest for its size"),
        ("deepseek-r1:14b", "DeepSeek R1 14B", "Reasoning power"),
    ],
}


def check_ollama_installed():
    return shutil.which("ollama") is not None


def check_ollama_running():
    try:
        httpx.get("http://localhost:11434/api/tags", timeout=3)
        return True
    except Exception:
        return False


def list_local_models():
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return []
        lines = r.stdout.strip().split("\n")
        if len(lines) <= 1:
            return []
        models = []
        for line in lines[1:]:
            parts = line.split()
            if parts:
                models.append(parts[0])
        return models
    except Exception:
        return []


def pull_model(name):
    print(f"\nPulling {name}...")
    try:
        p = subprocess.Popen(
            ["ollama", "pull", name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in p.stdout:
            print(line, end="")
            sys.stdout.flush()
        p.wait()
        if p.returncode == 0:
            print(f"\n{name} pulled successfully")
            return True
        print(f"\nFailed to pull {name}")
        return False
    except FileNotFoundError:
        print("ollama command not found")
        return False


def install_ollama():
    print("Installing Ollama...")
    try:
        p = subprocess.Popen(
            ["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in p.stdout:
            print(line, end="")
            sys.stdout.flush()
        p.wait(timeout=120)
        if p.returncode == 0:
            print("Ollama installed successfully")
            return True
        print("Ollama installation failed.")
        return False
    except Exception as e:
        print(f"Install failed: {e}")
        return False


def start_ollama():
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except FileNotFoundError:
        return False


def pick_model_interactive(local_models=None):
    import questionary
    choices = []
    seen = set()
    if local_models:
        choices.append(questionary.Choice(
            f"-- Local models ({len(local_models)} found) --",
            value=None, disabled=True,
        ))
        for m in local_models:
            tag = m if ":" in m else f"{m}:latest"
            if tag not in seen:
                choices.append(questionary.Choice(f"  {tag}", tag))
                seen.add(tag)
    for cat, models in CURATED_MODELS.items():
        choices.append(questionary.Choice(
            f"-- {cat} --",
            value=None, disabled=True,
        ))
        for tag, name, desc in models:
            if tag not in seen:
                choices.append(questionary.Choice(f"  {name}: {desc}", tag))
                seen.add(tag)
    choices.append(questionary.Choice("  Custom - type any model name", "__custom__"))
    result = questionary.select(
        "Select a model (arrow keys, Enter to confirm):",
        choices=choices,
        use_arrow_keys=True,
        use_jk_keys=True,
    ).ask()
    if result == "__custom__":
        c = questionary.text("Enter model name (e.g. qwen3-coder:30b):").ask()
        return c.strip() if c else None
    return result


OLLAMA_CHAT_ENDPOINT = "http://localhost:11434/api/chat"


def ollama_chat(model, messages, temperature=0.7, max_tokens=4096, timeout=120):
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(OLLAMA_CHAT_ENDPOINT, json=payload)
        resp.raise_for_status()
        data = resp.json()
    content = data.get("message", {}).get("content", "")
    pt = data.get("prompt_eval_count", 0)
    et = data.get("eval_count", 0)
    return {
        "content": content,
        "model": model,
        "provider": "ollama",
        "usage": {
            "prompt_tokens": pt,
            "completion_tokens": et,
            "total_tokens": pt + et,
        },
    }
