import os
import sys
import json
import re
import subprocess
from datetime import datetime

# Configure UTF-8 encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass

BRAIN_DIR = os.path.expandvars(r"%USERPROFILE%\.gemini\antigravity-cli\brain")
DEFAULT_PROJECT_DIR = os.path.expandvars(r"%USERPROFILE%")
PROJECTS_ROOT = os.path.join(DEFAULT_PROJECT_DIR, "Projects")

# ANSI Colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'<ADDITIONAL_METADATA>[\s\S]*?</ADDITIONAL_METADATA>', '', text)
    text = re.sub(r'<USER_SETTINGS_CHANGE>[\s\S]*?</USER_SETTINGS_CHANGE>', '', text)
    text = re.sub(r'</?USER_REQUEST>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def normalize_path(p):
    if not p:
        return ""
    p = p.strip('"').strip("'")
    return os.path.normpath(p)

def scan_sessions(limit=40):
    if not os.path.exists(BRAIN_DIR):
        return []
    
    entries = []
    try:
        subdirs = [os.path.join(BRAIN_DIR, d) for d in os.listdir(BRAIN_DIR)]
        subdirs = [d for d in subdirs if os.path.isdir(d)]
        subdirs.sort(key=lambda d: os.path.getmtime(d), reverse=True)
    except Exception:
        return []

    for d in subdirs[:limit]:
        cid = os.path.basename(d)
        log_path = os.path.join(d, ".system_generated", "logs", "transcript.jsonl")
        if not os.path.exists(log_path):
            continue
        
        mtime = datetime.fromtimestamp(os.path.getmtime(d))
        turns = 0
        first_prompt = ""
        last_prompt = ""
        detected_cwd = ""
        detected_git_repo = ""
        all_user_prompts = []
        
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        msg_type = obj.get("type")
                        
                        if msg_type == "USER_INPUT":
                            turns += 1
                            content = clean_text(obj.get("content", ""))
                            if content:
                                all_user_prompts.append(content)
                                if not first_prompt:
                                    first_prompt = content
                                last_prompt = content
                                
                                # Check git repo in user prompt
                                if not detected_git_repo:
                                    git_match = re.search(r'github\.com/[^/\s]+/([a-zA-Z0-9_\-\.]+?)(?:\.git|\s|$)', content)
                                    if git_match:
                                        repo = git_match.group(1).rstrip(".git")
                                        detected_git_repo = repo
                                
                        elif msg_type == "PLANNER_RESPONSE":
                            t_calls = obj.get("tool_calls", [])
                            if t_calls:
                                for tc in t_calls:
                                    args = tc.get("args", {})
                                    if isinstance(args, dict):
                                        c = args.get("Cwd", "")
                                        if c:
                                            c_norm = normalize_path(c)
                                            if c_norm and os.path.isdir(c_norm) and c_norm.lower() != DEFAULT_PROJECT_DIR.lower():
                                                detected_cwd = c_norm
                                                
                                        for key in ["SearchPath", "TargetFile", "AbsolutePath", "CommandLine"]:
                                            val = args.get(key, "")
                                            if val and not detected_cwd:
                                                m = re.search(r'([A-Za-z]:[\\/][^"\'\n]+?[\\/]Projects[\\/][a-zA-Z0-9_\-]+)', val)
                                                if m:
                                                    cand = normalize_path(m.group(1))
                                                    if os.path.isdir(cand):
                                                        detected_cwd = cand
                    except Exception:
                        pass
        except Exception:
            continue
        
        # If no explicit cwd detected, check detected git repo under Projects/
        if not detected_cwd and detected_git_repo:
            candidate_repo_path = os.path.join(PROJECTS_ROOT, detected_git_repo)
            if os.path.isdir(candidate_repo_path):
                detected_cwd = candidate_repo_path
                
        # Determine clean project name
        proj_name = "Chung (Home)"
        if detected_cwd:
            proj_name = os.path.basename(detected_cwd.rstrip(r"\/"))
        elif detected_git_repo:
            proj_name = detected_git_repo

        # Skip empty sessions with 0 prompts
        if turns == 0 and not first_prompt:
            continue

        entries.append({
            "id": cid,
            "mtime": mtime,
            "mtime_str": mtime.strftime("%d/%m/%Y %H:%M"),
            "turns": turns,
            "project_name": proj_name,
            "cwd": normalize_path(detected_cwd or DEFAULT_PROJECT_DIR),
            "first_prompt": first_prompt,
            "last_prompt": last_prompt
        })

    return entries

def print_banner():
    print(f"\n{CYAN}{BOLD}======================================================================{RESET}")
    print(f"{CYAN}{BOLD}       ANTIGRAVITY CLI - TIẾP TỤC PHIÊN LÀM VIỆC (AGY-RESUME)         {RESET}")
    print(f"{CYAN}{BOLD}======================================================================{RESET}")

def display_sessions(sessions):
    for idx, s in enumerate(sessions, 1):
        num_str = f"[{idx}]"
        print(f"{GREEN}{BOLD}{num_str:<5}{RESET} {YELLOW}{s['mtime_str']}{RESET} | {MAGENTA}{BOLD}{s['project_name']}{RESET} ({s['turns']} lượt)")
        print(f"      {DIM}📁 Thư mục:{RESET} {s['cwd']}")
        
        display_prompt = s['last_prompt'] or s['first_prompt'] or "(Chưa có yêu cầu cụ thể)"
        if len(display_prompt) > 115:
            display_prompt = display_prompt[:112] + "..."
        print(f"      {CYAN}💬 Gần nhất:{RESET} {display_prompt}")
        
        if s['first_prompt'] and s['first_prompt'] != s['last_prompt']:
            fp = s['first_prompt']
            if len(fp) > 95:
                fp = fp[:92] + "..."
            print(f"      {DIM}📌 Bắt đầu :{RESET} {fp}")
            
        print(f"      {DIM}🆔 ID: {s['id']}{RESET}")
        print(f"{DIM}----------------------------------------------------------------------{RESET}")

def resume_session(session):
    cid = session["id"]
    cwd = session.get("cwd") or DEFAULT_PROJECT_DIR
    proj = session.get("project_name", "General")
    
    print(f"\n{GREEN}{BOLD}🚀 Đang chuẩn bị tiếp tục phiên làm việc...{RESET}")
    print(f"👉 {BOLD}Dự án:{RESET} {proj}")
    print(f"👉 {BOLD}Thư mục:{RESET} {cwd}")
    print(f"👉 {BOLD}Conversation ID:{RESET} {cid}")
    print(f"{CYAN}{BOLD}======================================================================{RESET}\n")

    if os.path.isdir(cwd):
        try:
            os.chdir(cwd)
        except Exception:
            pass
            
    cmd = ["agy", "--conversation", cid]
    try:
        subprocess.run(cmd, shell=True)
    except KeyboardInterrupt:
        pass

def run_gui_grid(sessions):
    items = []
    for idx, s in enumerate(sessions, 1):
        items.append({
            "STT": idx,
            "ThoiGian": s['mtime_str'],
            "DuAn": s['project_name'],
            "SoLuot": s['turns'],
            "NoiDungGanNhat": (s['last_prompt'] or s['first_prompt'])[:80],
            "ThuMuc": s['cwd'],
            "ConversationId": s['id']
        })
        
    temp_json = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "agy_resume_temp.json")
    try:
        with open(temp_json, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)
    except Exception as e:
        print(f"Lỗi tạo file tạm: {e}")
        return False
        
    ps_cmd = (
        f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        f"$data = Get-Content -Raw -Encoding UTF8 '{temp_json}' | ConvertFrom-Json; "
        f"$sel = $data | Out-GridView -Title 'Chọn phiên làm việc Antigravity (agy) để tiếp tục' -PassThru; "
        f"if ($sel) {{ [Console]::WriteLine($sel.ConversationId) }}"
    )
    
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, encoding="utf-8")
    selected_id = res.stdout.strip()
    
    if os.path.exists(temp_json):
        try: os.remove(temp_json)
        except: pass
        
    if selected_id:
        target = next((s for s in sessions if s["id"] == selected_id), None)
        if target:
            resume_session(target)
            return True
        else:
            resume_session({"id": selected_id, "cwd": DEFAULT_PROJECT_DIR, "project_name": "Direct"})
            return True
    return False

def main():
    args = sys.argv[1:]
    sessions = scan_sessions(limit=35)
    
    if not sessions:
        print(f"{YELLOW}Không tìm thấy phiên làm việc nào trong hệ thống.{RESET}")
        return

    # Handle direct arguments
    if args:
        first_arg = args[0].strip()
        
        # Check GUI mode
        if first_arg in ["-g", "--gui"]:
            if run_gui_grid(sessions):
                return
            print(f"{YELLOW}Đã hủy chọn qua GUI.{RESET}")
            return
            
        # Check List only mode
        if first_arg in ["-l", "--list"]:
            print_banner()
            display_sessions(sessions[:15])
            return
            
        # Check number selection: agyr 1
        if first_arg.isdigit():
            idx = int(first_arg)
            if 1 <= idx <= len(sessions):
                resume_session(sessions[idx - 1])
                return
            else:
                print(f"{YELLOW}Số thứ tự không hợp lệ (1 - {len(sessions)}).{RESET}")
                return
                
        # Check direct conversation ID
        if len(first_arg) > 20 and "-" in first_arg:
            target = next((s for s in sessions if s["id"] == first_arg), None)
            if target:
                resume_session(target)
            else:
                resume_session({"id": first_arg, "cwd": DEFAULT_PROJECT_DIR, "project_name": "Specified ID"})
            return

        # Check search keyword: agyr <keyword>
        query = " ".join(args).lower()
        matched = [s for s in sessions if query in s['project_name'].lower() or query in s['last_prompt'].lower() or query in s['first_prompt'].lower()]
        if matched:
            print_banner()
            print(f"{GREEN}Tìm thấy {len(matched)} phiên phù hợp với từ khóa '{query}':{RESET}\n")
            display_sessions(matched)
            sessions = matched
        else:
            print(f"{YELLOW}Không tìm thấy phiên nào chứa từ khóa '{query}'. Hiển thị danh sách gần nhất:{RESET}\n")

    # Interactive Loop
    displayed = sessions[:10]
    print_banner()
    display_sessions(displayed)
    
    print(f"\n{BOLD}Tuỳ chọn:{RESET}")
    print(f"- Nhập {GREEN}1 - {len(displayed)}{RESET} hoặc nhấn {GREEN}[Enter]{RESET} để tiếp tục phiên [1]")
    print(f"- Nhập từ khóa (ví dụ: {CYAN}famorg{RESET}, {CYAN}excel{RESET}, {CYAN}ebook{RESET}...) để tìm kiếm")
    print(f"- Nhập {MAGENTA}g{RESET} để mở giao diện bảng chọn GUI (Out-GridView)")
    print(f"- Nhập {YELLOW}q{RESET} để thoát\n")

    while True:
        try:
            choice = input(f"{BOLD}👉 Nhập lựa chọn [Mặc định: 1]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nĐã hủy.")
            return

        if choice == "" or choice == "1":
            resume_session(displayed[0])
            break
        elif choice.lower() in ["q", "exit", "quit"]:
            print("Đã thoát.")
            break
        elif choice.lower() in ["g", "gui"]:
            if run_gui_grid(sessions):
                break
        elif choice.isdigit():
            val = int(choice)
            if 1 <= val <= len(displayed):
                resume_session(displayed[val - 1])
                break
            else:
                print(f"{YELLOW}Vui lòng nhập số từ 1 đến {len(displayed)}.{RESET}")
        else:
            q = choice.lower()
            results = [s for s in sessions if q in s['project_name'].lower() or q in s['last_prompt'].lower() or q in s['first_prompt'].lower()]
            if results:
                print(f"\n{GREEN}--- Kết quả tìm kiếm cho '{choice}' ({len(results)}) ---{RESET}")
                display_sessions(results[:10])
                displayed = results[:10]
            else:
                print(f"{YELLOW}Không tìm thấy kết quả nào cho '{choice}'. Hãy thử từ khóa khác hoặc nhập số.{RESET}")

if __name__ == "__main__":
    main()
