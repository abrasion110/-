import os
import re
import sys
import pty
import select
import shutil
import subprocess
import requests
from datetime import datetime

os.environ["INPUTRC"] = "/dev/null"
try:
    import readline
    readline.parse_and_bind("set editing-mode emacs")
    readline.parse_and_bind("bind ^I insert-tab")
    for ch in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ":
        readline.parse_and_bind(f'"{ch}": self-insert')
except ImportError:
    pass

# ---------------------------------------------------------
# تنظیمات API اوپن‌روتر و گیت‌هاب
# ---------------------------------------------------------
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
FREE_MODELS_URL = "https://openrouter.ai/api/v1/models"

def get_free_models():
    """لیست مدل‌های رایگان فعال روی OpenRouter را همان لحظه برمی‌گرداند."""
    try:
        res = requests.get(FREE_MODELS_URL, timeout=10)
        res.raise_for_status()
        data = res.json().get("data", [])
        free = [
            m["id"] for m in data
            if m.get("pricing", {}).get("prompt") == "0"
            and m.get("pricing", {}).get("completion") == "0"
        ]
        return free
    except Exception:
        return []

REPO_URL = "https://github.com/abrasion110/-.git"
REPO_PATH = os.path.expanduser("~/agent-runs")

TIER1_DEBUGGER = "meta-llama/llama-3.3-70b-instruct"
TIER2_REVIEWER = "deepseek/deepseek-chat"

INTERACTIVE_ONLY = {
    "nano", "vim", "vi", "micro", "htop", "top", "less",
}

MAX_AI_FIX_ATTEMPTS = 3

INVALID_OUTPUT_MARKERS = (
    "FAILED_COMMAND_OR_CODE:",
    "TERMINAL_ERROR:",
    "SOURCE:",
    "ERROR:",
)

command_log = []


# ---------------------------------------------------------
# مدیریت Git
# ---------------------------------------------------------
def setup_git_repo():
    if not os.path.exists(REPO_PATH):
        os.makedirs(REPO_PATH, exist_ok=True)
    git_dir = os.path.join(REPO_PATH, ".git")
    if not os.path.exists(git_dir):
        subprocess.run(["git", "init"], cwd=REPO_PATH, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "remote", "add", "origin", REPO_URL], cwd=REPO_PATH, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "branch", "-M", "main"], cwd=REPO_PATH, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def commit_and_push(file_name: str, code_content: str):
    setup_git_repo()
    file_path = os.path.join(REPO_PATH, file_name)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(code_content)

    subprocess.run(["git", "add", "."], cwd=REPO_PATH, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    commit_msg = f"Auto-Fix: {file_name} @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=REPO_PATH, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "push", "-u", "origin", "main", "--force"], cwd=REPO_PATH, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def sanitize_project_name(file_name: str) -> str:
    base = os.path.splitext(os.path.basename(file_name))[0]
    base = re.sub(r"[^a-zA-Z0-9._\-]+", "_", base).strip("_")
    return base or "project"


def write_readme(project_dir: str, project_name: str, steps: list):
    readme_path = os.path.join(project_dir, "README.md")
    lines = [f"# {project_name}", "", "## مراحل اجرا", ""]
    if steps:
        for i, step in enumerate(steps, 1):
            lines.append(f"{i}. `{step}`")
    else:
        lines.append("(دستوری ثبت نشده است)")
    lines.append("")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def finish_project(py_file: str, code_content: str, run_command: str):
    global command_log

    setup_git_repo()

    if run_command not in command_log:
        command_log.append(run_command)

    project_name = sanitize_project_name(py_file)
    project_dir = os.path.join(REPO_PATH, project_name)
    os.makedirs(project_dir, exist_ok=True)

    code_path = os.path.join(project_dir, os.path.basename(py_file))
    with open(code_path, "w", encoding="utf-8") as f:
        f.write(code_content)

    write_readme(project_dir, project_name, command_log)

    subprocess.run(["git", "add", "."], cwd=REPO_PATH, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    commit_msg = f"Auto: {project_name} @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=REPO_PATH, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "push", "-u", "origin", "main", "--force"], cwd=REPO_PATH, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    command_log = []


# ---------------------------------------------------------
# پاکسازی و فیلتر کردن خروجی مدل
# ---------------------------------------------------------
def clean_model_output(raw_text: str) -> str:
    lines = raw_text.splitlines()
    clean_lines = []
    for line in lines:
        s = line.strip()
        if s.startswith(("SOURCE:", "ERROR:", "```", "Here is", "Fixed code:", "Explanation:", "FAILED_COMMAND_OR_CODE:", "TERMINAL_ERROR:")):
            continue
        if re.match(r"^[a-zA-Z\s]+:$", s) and not any(k in s for k in ("def", "class", "if", "else", "import", "from")):
            continue
        clean_lines.append(line)
    return "\n".join(clean_lines).strip()


def is_valid_ai_output(text: str) -> bool:
    if not text or not text.strip():
        return False
    for marker in INVALID_OUTPUT_MARKERS:
        if marker in text:
            return False
    return True


def call_openrouter_ai(model_id: str, system_prompt: str, user_content: str):
    key = os.environ.get("OPENROUTER_API_KEY", OPENROUTER_API_KEY)
    if not key:
        return None

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://termux-agent.local",
        "X-Title": "Termux Autonomous Agent",
    }
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.0,
        "max_tokens": 2000,
    }

    try:
        res = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=(10, 45))
    except Exception as e:
        print(f"❌ خطای اتصال به OpenRouter ({model_id}): {e}")
        return None

    if res.status_code != 200:
        print(f"❌ خطای OpenRouter ({model_id}): HTTP {res.status_code} — {res.text[:200]}")
        return None

    try:
        data = res.json()
        raw_out = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as e:
        print(f"❌ پاسخ OpenRouter ({model_id}) ساختار نامعتبر داشت: {e}")
        return None

    cleaned = clean_model_output(raw_out)
    if not is_valid_ai_output(cleaned):
        print(f"❌ خروجی OpenRouter ({model_id}) نامعتبر بود (خالی یا echo پرامپت).")
        return None

    return cleaned


# ---------------------------------------------------------
# چرخه ۳ مرحله‌ای اصلاح کد و دستورات
# ---------------------------------------------------------
def ask_ai_debugger(code_or_cmd: str, error_log: str):
    sys_tier1 = (
        "You are an automated bash/python command corrector for Termux. "
        "Fix the given failed bash command or python code. "
        "CRITICAL: Output ONLY the raw executable command or python code. "
        "Do NOT write 'SOURCE:', 'ERROR:', explanations, or markdown fences."
    )
    input_tier1 = f"FAILED_COMMAND_OR_CODE:\n{code_or_cmd}\n\nTERMINAL_ERROR:\n{error_log}"
    t1 = call_openrouter_ai(TIER1_DEBUGGER, sys_tier1, input_tier1)
    if t1 is None:
        return None

    sys_tier2 = "Review and optimize this command/code for Termux compatibility. Output ONLY executable syntax."
    t2 = call_openrouter_ai(TIER2_REVIEWER, sys_tier2, t1)
    if t2 is None:
        return t1

    sys_tier3 = "Final security check. Return strictly the executable command/code without any markdown or prose."
    t3 = None
    for free_model in get_free_models():
        t3 = call_openrouter_ai(free_model, sys_tier3, t2)
        if t3 is not None:
            break
    if t3 is None:
        return t2

    return t3


# ---------------------------------------------------------
# مدیریت دستور cd (شامل رفع باگ cd خالی)
# ---------------------------------------------------------
def handle_cd(cmd_str: str):
    parts = cmd_str.split(" ", 1)
    target_dir = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "~"

    try:
        os.chdir(os.path.expanduser(target_dir))
        print(f"📁 دایرکتوری: {os.getcwd()}")
        return 0, ""
    except Exception as e:
        return 1, str(e)


# ---------------------------------------------------------
# اجراکننده دستورات
# ---------------------------------------------------------
def run_command_in_pty(cmd_str: str):
    if cmd_str == "cd" or cmd_str.startswith("cd "):
        return handle_cd(cmd_str)

    first_word = cmd_str.split()[0] if cmd_str.split() else ""
    if first_word in ["nano", "vim", "vi", "micro", "htop", "top", "less"]:
        ret = os.system(cmd_str)
        return ret, ""

    master_fd, slave_fd = pty.openpty()
    proc = subprocess.Popen(
        cmd_str,
        shell=True,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
    )
    os.close(slave_fd)

    output_chunks = []
    while True:
        r, _, _ = select.select([master_fd], [], [], 0.1)
        if master_fd in r:
            try:
                data = os.read(master_fd, 1024)
                if not data:
                    break
                sys.stdout.write(data.decode(errors="ignore"))
                sys.stdout.flush()
                output_chunks.append(data)
            except OSError:
                break
        if proc.poll() is not None:
            break

    os.close(master_fd)
    proc.wait()
    full_output = b"".join(output_chunks).decode(errors="ignore")
    return proc.returncode, full_output


# ---------------------------------------------------------
# حلقه اصلی اجرای شل
# ---------------------------------------------------------
def start_agent_shell():
    print("==================================================")
    print("🤖 Termux Autonomous Agent (Nano Direct Fixed)")
    print("==================================================")
    if not os.environ.get("OPENROUTER_API_KEY", OPENROUTER_API_KEY):
        print("⚠️  OPENROUTER_API_KEY تنظیم نشده — اصلاح خودکار با AI غیرفعال است.")
        print("   export OPENROUTER_API_KEY=\"کلید_واقعی_شما\"")
    setup_git_repo()

    while True:
        try:
            cwd = os.path.basename(os.getcwd()) or "/"
            user_input = input(f"\nTermux-Agent [{cwd}] $ ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit"]:
                break

            ret_code, output = run_command_in_pty(user_input)

            if ret_code == 0:
                command_log.append(user_input)

            if ret_code != 0:
                first_word = user_input.split()[0] if user_input.split() else ""

                if first_word in INTERACTIVE_ONLY:
                    if output:
                        print(f"⚠️  {output}")
                    continue

                current_cmd = user_input
                current_output = output
                fixed_this_round = False

                for attempt in range(1, MAX_AI_FIX_ATTEMPTS + 1):
                    fixed_cmd = ask_ai_debugger(current_cmd, current_output)

                    if fixed_cmd is None:
                        print(f"⚠️  اصلاح خودکار (تلش {attempt}/{MAX_AI_FIX_ATTEMPTS}) ممکن نبود:\n{current_output}")
                        break

                    if current_cmd.endswith(".py") and os.path.exists(current_cmd):
                        with open(current_cmd, "w", encoding="utf-8") as f:
                            f.write(fixed_cmd)
                        run_cmd = f"python3 {current_cmd}"
                        new_ret, new_out = run_command_in_pty(run_cmd)
                        if new_ret == 0:
                            finish_project(current_cmd, fixed_cmd, run_cmd)
                            fixed_this_round = True
                            break
                        current_output = new_out
                        continue

                    if fixed_cmd == current_cmd:
                        print(f"⚠️  دستور اصلاح‌نشده باقی ماند:\n{current_output}")
                        break

                    print(f"🔧 [تلاش {attempt}/{MAX_AI_FIX_ATTEMPTS}] اجرای دستور اصلاح‌شده: {fixed_cmd}")
                    new_ret, new_out = run_command_in_pty(fixed_cmd)

                    if new_ret == 0:
                        command_log.append(fixed_cmd)
                        fixed_this_round = True
                        break

                    current_cmd = fixed_cmd
                    current_output = new_out

                if not fixed_this_round and current_output and MAX_AI_FIX_ATTEMPTS > 0:
                    pass

            else:
                if user_input.startswith("python") and user_input.endswith(".py"):
                    py_file = user_input.split()[-1]
                    if os.path.exists(py_file):
                        with open(py_file, "r", encoding="utf-8") as f:
                            content = f.read()
                        finish_project(py_file, content, user_input)

        except KeyboardInterrupt:
            print("\n(برای خروج 'exit' را بنویسید)")
        except Exception as e:
            print(f"⚠️  خطای داخلی agent: {e}")


if __name__ == "__main__":
    start_agent_shell()
