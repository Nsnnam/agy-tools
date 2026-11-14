import os
import sys
import json
import re
import uuid
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone

# Configure UTF-8 encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass

from datetime import datetime, timezone

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
except ImportError:
    tk = None
    ttk = None
    messagebox = None
    filedialog = None

CLI_BASE_DIR = os.path.expandvars(r"%USERPROFILE%\.gemini\antigravity-cli")
BRAIN_DIR = os.path.join(CLI_BASE_DIR, "brain")
CONVERSATIONS_DIR = os.path.join(CLI_BASE_DIR, "conversations")
SUMMARIES_DB_PATH = os.path.join(CLI_BASE_DIR, "conversation_summaries.db")
CUSTOM_NAMES_PATH = os.path.join(CLI_BASE_DIR, "custom_project_names.json")
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

def parse_iso_time(t_str):
    if not t_str:
        return None
    try:
        clean_t = t_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_t)
        return dt.astimezone()
    except Exception:
        return None

def format_datetime(dt):
    if not dt:
        return ""
    return dt.strftime("%d/%m/%Y %H:%M:%S")

def format_iso_datetime(dt):
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def format_short_datetime(dt):
    if not dt:
        return ""
    return dt.strftime("%d/%m/%Y %H:%M")

def load_custom_names():
    """Tải danh sách tên dự án, phiên bản, tiêu đề và thư mục tùy chỉnh."""
    if not os.path.exists(CUSTOM_NAMES_PATH):
        return {}
    try:
        with open(CUSTOM_NAMES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_custom_names(data):
    """Lưu danh sách cấu hình tùy chỉnh ra file JSON."""
    try:
        with open(CUSTOM_NAMES_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Lỗi lưu custom names: {e}")
        return False

def update_session_names(cid, new_project_name=None, new_title=None, new_version=None, new_cwd=None):
    """
    Cập nhật Tên dự án (project_name), Tiêu đề (title), Phiên bản (version) và Thư mục chính (cwd).
    Đồng bộ cả custom_project_names.json và SQLite conversation_summaries.db.
    """
    custom_names = load_custom_names()
    if cid not in custom_names:
        custom_names[cid] = {}
        
    clean_proj = new_project_name.strip() if new_project_name is not None else ""
    clean_title = new_title.strip() if new_title is not None else ""
    clean_ver = new_version.strip() if new_version is not None else ""
    clean_cwd = normalize_path(new_cwd) if new_cwd is not None else ""
    
    if clean_proj:
        custom_names[cid]["project_name"] = clean_proj
    if clean_title:
        custom_names[cid]["title"] = clean_title
    if clean_ver:
        custom_names[cid]["version"] = clean_ver
    if clean_cwd:
        custom_names[cid]["cwd"] = clean_cwd
        
    custom_names[cid]["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_custom_names(custom_names)
    
    # Cập nhật trực tiếp vào conversation_summaries.db của Antigravity CLI
    if os.path.exists(SUMMARIES_DB_PATH) and clean_title:
        try:
            con = sqlite3.connect(SUMMARIES_DB_PATH)
            cur = con.cursor()
            cur.execute("UPDATE conversation_summaries SET title = ? WHERE conversation_id = ?", (clean_title, cid))
            con.commit()
            con.close()
        except Exception as e:
            print(f"Lỗi update summaries DB: {e}")
            
    return True

def detect_project_version(cwd, transcript_path=None, custom_version=None):
    """
    Tự động nhận diện phiên bản tương ứng mới nhất của từng dự án/tool.
    Quét từ:
    1. Cấu hình người dùng đặt thủ công (custom_version)
    2. package.json ("version")
    3. manifest.json (Chrome Extension "version")
    4. pyproject.toml / Cargo.toml / setup.py
    5. VERSION / version.txt / version.json
    6. Header file chính WordPress plugin (* Version: x.y.z)
    7. Git commit log mới nhất (mẫu vX.Y.Z hoặc release: vX.Y.Z)
    8. Git tags mới nhất
    9. Nội dung trao đổi gần nhất trong transcript
    """
    if custom_version:
        return custom_version

    is_generic_home = False
    if cwd:
        norm_cwd = normalize_path(cwd).lower().rstrip(r"\/")
        if norm_cwd in [DEFAULT_PROJECT_DIR.lower().rstrip(r"\/"), r"c:\users\admin"]:
            is_generic_home = True

    if cwd and os.path.isdir(cwd) and not is_generic_home:
        # 1. package.json
        p_json = os.path.join(cwd, "package.json")
        if os.path.isfile(p_json):
            try:
                with open(p_json, "r", encoding="utf-8") as f:
                    v = json.load(f).get("version")
                    if v:
                        v_str = str(v).strip()
                        return v_str if v_str.startswith("v") else f"v{v_str}"
            except Exception:
                pass

        # 2. manifest.json (Chrome Extension)
        m_json = os.path.join(cwd, "manifest.json")
        if os.path.isfile(m_json):
            try:
                with open(m_json, "r", encoding="utf-8") as f:
                    v = json.load(f).get("version")
                    if v:
                        v_str = str(v).strip()
                        return v_str if v_str.startswith("v") else f"v{v_str}"
            except Exception:
                pass

        # 3. pyproject.toml
        pyproj = os.path.join(cwd, "pyproject.toml")
        if os.path.isfile(pyproj):
            try:
                with open(pyproj, "r", encoding="utf-8") as f:
                    m = re.search(r'version\s*=\s*["\']([^"\']+)["\']', f.read())
                    if m:
                        v_str = m.group(1).strip()
                        return v_str if v_str.startswith("v") else f"v{v_str}"
            except Exception:
                pass

        # 4. Cargo.toml
        cargo = os.path.join(cwd, "Cargo.toml")
        if os.path.isfile(cargo):
            try:
                with open(cargo, "r", encoding="utf-8") as f:
                    m = re.search(r'version\s*=\s*["\']([^"\']+)["\']', f.read())
                    if m:
                        v_str = m.group(1).strip()
                        return v_str if v_str.startswith("v") else f"v{v_str}"
            except Exception:
                pass

        # 5. VERSION or version.txt or version.json
        for vname in ["VERSION", "version.txt", "version.json", "VERSION.md"]:
            vp = os.path.join(cwd, vname)
            if os.path.isfile(vp):
                try:
                    with open(vp, "r", encoding="utf-8") as f:
                        c = f.read().strip()
                        if vname.endswith(".json"):
                            c = json.loads(c).get("version", "")
                        m = re.search(r'v?(\d+\.\d+(?:\.\d+)?)', c)
                        if m:
                            return f"v{m.group(1)}"
                except Exception:
                    pass

        # 6. WordPress plugin main file header
        try:
            for fname in os.listdir(cwd):
                if fname.endswith(".php"):
                    php_file = os.path.join(cwd, fname)
                    with open(php_file, "r", encoding="utf-8", errors="ignore") as f:
                        content_head = f.read(2048)
                        m = re.search(r'Version:\s*([0-9\.]+)', content_head, re.IGNORECASE)
                        if m:
                            return f"v{m.group(1)}"
        except Exception:
            pass

        # 7. Git commit messages / tags
        if os.path.isdir(os.path.join(cwd, ".git")):
            try:
                res = subprocess.run(
                    ["git", "-C", cwd, "log", "-n", "8", "--pretty=format:%s"],
                    capture_output=True, text=True, timeout=2
                )
                if res.returncode == 0 and res.stdout:
                    m = re.search(r'\b(?:v|release:\s*v?|ver\s*v?)(\d+\.\d+(?:\.\d+)?)\b', res.stdout, re.IGNORECASE)
                    if m:
                        return f"v{m.group(1)}"
            except Exception:
                pass

            try:
                res = subprocess.run(
                    ["git", "-C", cwd, "describe", "--tags", "--abbrev=0"],
                    capture_output=True, text=True, timeout=2
                )
                if res.returncode == 0 and res.stdout.strip():
                    return res.stdout.strip()
            except Exception:
                pass

    # 8. Transcript fallback (tìm mẫu phiên bản do user hoặc assistant xác nhận trực tiếp)
    if transcript_path and os.path.isfile(transcript_path):
        try:
            with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
                matches = []
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                        m_type = obj.get("type")
                        if m_type in ["USER_INPUT", "PLANNER_RESPONSE"]:
                            txt = clean_text(obj.get("content", ""))
                            # Tìm mẫu: phiên bản v1.2.3 hoặc v1.2.3 hoặc release: v1.2.3
                            found = re.findall(r'\b(?:phiên\s*bản|version|release)\s*[:=]?\s*v?(\d+\.\d+(?:\.\d+)?)\b', txt, re.IGNORECASE)
                            if found:
                                matches.extend(found)
                    except Exception:
                        pass
                if matches:
                    return f"v{matches[-1]}"
        except Exception:
            pass

    return "-"

def load_summaries_metadata():
    summaries = {}
    if not os.path.exists(SUMMARIES_DB_PATH):
        return summaries
    try:
        con = sqlite3.connect(SUMMARIES_DB_PATH)
        cur = con.cursor()
        rows = cur.execute("SELECT conversation_id, title, parent_conversation_id, last_modified_time FROM conversation_summaries").fetchall()
        for cid, title, parent_id, lmt in rows:
            summaries[cid] = {
                "title": (title or "").strip(),
                "parent_id": (parent_id or "").strip(),
                "last_modified_time": lmt
            }
        con.close()
    except Exception:
        pass
    return summaries

def scan_sessions(limit=None):
    """
    Quét toàn bộ lịch sử các phiên làm việc trong BRAIN_DIR.
    Mặc định limit=None để quét 100% tất cả phiên, không bỏ sót phiên nào.
    Tự động sắp xếp theo thời gian hoạt động thực tế mới nhất lên đầu.
    """
    if not os.path.exists(BRAIN_DIR):
        return []
    
    summaries_meta = load_summaries_metadata()
    custom_names = load_custom_names()
    entries = []
    
    def get_activity_time(d):
        log_path = os.path.join(d, ".system_generated", "logs", "transcript.jsonl")
        if os.path.exists(log_path):
            try:
                return os.path.getmtime(log_path)
            except Exception:
                pass
        try:
            return os.path.getmtime(d)
        except Exception:
            return 0

    try:
        subdirs = [os.path.join(BRAIN_DIR, d) for d in os.listdir(BRAIN_DIR)]
        subdirs = [d for d in subdirs if os.path.isdir(d)]
        # Sắp xếp sơ bộ theo mtime của file transcript.jsonl
        subdirs.sort(key=get_activity_time, reverse=True)
    except Exception:
        return []

    if limit is not None and limit > 0:
        subdirs = subdirs[:limit]

    for d in subdirs:
        cid = os.path.basename(d)
        log_path = os.path.join(d, ".system_generated", "logs", "transcript.jsonl")
        if not os.path.exists(log_path):
            continue
        
        file_mtime = datetime.fromtimestamp(os.path.getmtime(log_path)).astimezone()
        dir_mtime = datetime.fromtimestamp(os.path.getmtime(d)).astimezone()
        turns = 0
        first_prompt = ""
        first_prompt_time = None
        last_prompt = ""
        last_prompt_time = None
        last_step_time = None
        detected_cwd = ""
        git_repos = []
        last_assistant_snippet = ""
        
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        msg_type = obj.get("type")
                        t_iso = obj.get("created_at")
                        step_time = parse_iso_time(t_iso) if t_iso else None
                        if step_time:
                            last_step_time = step_time
                        
                        if msg_type == "USER_INPUT":
                            turns += 1
                            content = clean_text(obj.get("content", ""))
                            if content:
                                if not first_prompt:
                                    first_prompt = content
                                    first_prompt_time = step_time
                                last_prompt = content
                                last_prompt_time = step_time
                                
                                # Tìm tất cả các Git Repo có trong yêu cầu
                                git_matches = re.finditer(r'github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-]+?)(?:\.git)?(?=[^a-zA-Z0-9_\-]|$)', content)
                                for m in git_matches:
                                    owner, repo = m.group(1), m.group(2)
                                    full_r = f"https://github.com/{owner}/{repo}"
                                    if full_r not in git_repos:
                                        git_repos.append(full_r)
                                
                                # Nhận diện đường dẫn dự án có trong yêu cầu
                                if not detected_cwd:
                                    m_proj = re.search(r'([A-Za-z]:[\\/][^"\'\n]+?[\\/]Projects[\\/]([a-zA-Z0-9_\-]+))', content)
                                    if m_proj:
                                        cand = normalize_path(m_proj.group(1))
                                        if os.path.isdir(cand) and not cand.lower().startswith(CLI_BASE_DIR.lower()):
                                            detected_cwd = cand
                                            
                        elif msg_type == "PLANNER_RESPONSE":
                            txt = clean_text(obj.get("content", ""))
                            if txt:
                                last_assistant_snippet = txt[:350]
                            # Tìm git repo trong phản hồi trợ lý
                            git_matches = re.finditer(r'github\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-]+?)(?:\.git)?(?=[^a-zA-Z0-9_\-]|$)', txt)
                            for m in git_matches:
                                owner, repo = m.group(1), m.group(2)
                                full_r = f"https://github.com/{owner}/{repo}"
                                if full_r not in git_repos:
                                    git_repos.append(full_r)

                            t_calls = obj.get("tool_calls", [])
                            if t_calls:
                                for tc in t_calls:
                                    args = tc.get("args", {})
                                    if isinstance(args, dict):
                                        c = args.get("Cwd", "")
                                        if c:
                                            c_norm = normalize_path(c)
                                            if c_norm and os.path.isdir(c_norm):
                                                # Bỏ qua thư mục nội bộ CLI hoặc thư mục gốc user
                                                if not c_norm.lower().startswith(CLI_BASE_DIR.lower()) and c_norm.lower() != DEFAULT_PROJECT_DIR.lower():
                                                    detected_cwd = c_norm
                                                    
                                        for key in ["SearchPath", "TargetFile", "AbsolutePath", "CommandLine"]:
                                            val = str(args.get(key, ""))
                                            if val and not detected_cwd:
                                                m_path = re.search(r'([A-Za-z]:[\\/][^"\'\n]+?[\\/]Projects[\\/]([a-zA-Z0-9_\-]+))', val)
                                                if m_path:
                                                    cand = normalize_path(m_path.group(1))
                                                    if os.path.isdir(cand) and not cand.lower().startswith(CLI_BASE_DIR.lower()):
                                                        detected_cwd = cand
                    except Exception:
                        pass
        except Exception:
            continue
            
        # Nếu chưa tìm thấy CWD nhưng có Git Repo, kiểm tra thư mục ~/Projects/<repo>
        if not detected_cwd and git_repos:
            for gr in git_repos:
                repo_basename = gr.split('/')[-1]
                candidate_repo_path = os.path.join(PROJECTS_ROOT, repo_basename)
                if os.path.isdir(candidate_repo_path):
                    detected_cwd = candidate_repo_path
                    break
                    
        # Áp dụng cấu hình tùy chỉnh của người dùng nếu có
        custom_entry = custom_names.get(cid, {})
        if custom_entry.get("cwd"):
            detected_cwd = custom_entry["cwd"]

        # Xác định thư mục cuối cùng
        final_cwd = normalize_path(detected_cwd or DEFAULT_PROJECT_DIR)

        # Xác định tên dự án
        proj_name = "Chung (Home)"
        if detected_cwd:
            proj_name = os.path.basename(detected_cwd.rstrip(r"\/"))
        elif git_repos:
            proj_name = git_repos[0].split('/')[-1]

        # Bỏ qua các session hoàn toàn trống không có lượt hỏi nào
        if turns == 0 and not first_prompt:
            continue

        # Thời gian
        created_at = first_prompt_time or dir_mtime
        updated_at = last_step_time or last_prompt_time or file_mtime or dir_mtime

        # Metadata từ SQLite summaries
        meta = summaries_meta.get(cid, {})
        title = meta.get("title") or ""
        parent_id = meta.get("parent_id") or ""
        if not title:
            title = first_prompt[:50] if first_prompt else proj_name

        # Áp dụng Tên dự án & Tiêu đề tùy chỉnh nếu có
        if custom_entry.get("project_name"):
            proj_name = custom_entry["project_name"]
        if custom_entry.get("title"):
            title = custom_entry["title"]

        # Nhận diện phiên bản tương ứng mới nhất
        version = detect_project_version(final_cwd, log_path, custom_version=custom_entry.get("version"))

        git_repo_str = ", ".join(git_repos)

        entries.append({
            "id": cid,
            "title": title,
            "version": version,
            "parent_id": parent_id,
            "created_at": created_at,
            "created_at_str": format_datetime(created_at),
            "created_iso": format_iso_datetime(created_at),
            "updated_at": updated_at,
            "updated_at_str": format_datetime(updated_at),
            "updated_iso": format_iso_datetime(updated_at),
            "turns": turns,
            "project_name": proj_name,
            "cwd": final_cwd,
            "git_repos": git_repos,
            "git_repo_str": git_repo_str,
            "first_prompt": first_prompt,
            "last_prompt": last_prompt,
            "last_assistant": last_assistant_snippet
        })

    # Sắp xếp toàn bộ theo thời gian cập nhật thực tế mới nhất lên đầu
    entries.sort(key=lambda s: s["updated_at"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return entries

def print_banner():
    print(f"\n{CYAN}{BOLD}======================================================================{RESET}")
    print(f"{CYAN}{BOLD}       ANTIGRAVITY CLI - TIẾP TỤC PHIÊN LÀM VIỆC (AGY-RESUME)         {RESET}")
    print(f"{CYAN}{BOLD}======================================================================{RESET}")

def display_sessions(sessions):
    for idx, s in enumerate(sessions, 1):
        num_str = f"[{idx}]"
        parent_badge = f" {MAGENTA}[Nhánh từ: {s['parent_id'][:8]}]{RESET}" if s['parent_id'] else ""
        ver_str = f" {YELLOW}[{s.get('version', '-')}]" if s.get('version') and s.get('version') != '-' else ""
        print(f"{GREEN}{BOLD}{num_str:<5}{RESET} {YELLOW}{s['updated_at_str']}{RESET} | {CYAN}{BOLD}{s['project_name']}{RESET}{ver_str}{RESET} ({s['turns']} lượt){parent_badge}")
        print(f"      {BOLD}📌 Tiêu đề   :{RESET} {s['title']}")
        if s.get('version') and s.get('version') != '-':
            print(f"      {YELLOW}🏷️ Phiên bản :{RESET} {BOLD}{s['version']}{RESET}")
        print(f"      {DIM}📁 Thư mục   :{RESET} {s['cwd']}")
        if s.get('git_repo_str'):
            print(f"      {BLUE}🔗 Git Repo  :{RESET} {s['git_repo_str']}")
        print(f"      {DIM}🕒 Tạo lúc   :{RESET} {s['created_at_str']} | {DIM}Sửa cuối:{RESET} {s['updated_at_str']}")
        
        # Display initial prompt
        fp = s['first_prompt'] or "(Chưa có)"
        if len(fp) > 115:
            fp = fp[:112] + "..."
        print(f"      {BLUE}🌱 Khởi tạo  :{RESET} {fp}")
        
        # Display latest prompt
        lp = s['last_prompt'] or "(Chưa có)"
        if len(lp) > 115:
            lp = lp[:112] + "..."
        print(f"      {GREEN}💬 Gần nhất  :{RESET} {lp}")
            
        print(f"      {DIM}🆔 ID: {s['id']}{RESET}")
        print(f"{DIM}----------------------------------------------------------------------{RESET}")

def cli_rename_session(session):
    """Đổi tên dự án, phiên bản, tiêu đề và thư mục từ dòng lệnh."""
    cid = session["id"]
    curr_proj = session.get("project_name", "")
    curr_title = session.get("title", "")
    curr_ver = session.get("version", "-")
    curr_cwd = session.get("cwd", "")
    
    print(f"\n{CYAN}{BOLD}======================================================================{RESET}")
    print(f"{CYAN}{BOLD}              ĐỔI TÊN DỰ ÁN & TIÊU ĐỀ PHIÊN LÀM VIỆC                  {RESET}")
    print(f"{CYAN}{BOLD}======================================================================{RESET}")
    print(f"👉 {BOLD}ID           :{RESET} {cid}")
    print(f"👉 {BOLD}Dự án hiện tại:{RESET} {YELLOW}{curr_proj}{RESET}")
    print(f"👉 {BOLD}Phiên bản    :{RESET} {YELLOW}{curr_ver}{RESET}")
    print(f"👉 {BOLD}Tiêu đề hiện tại:{RESET} {YELLOW}{curr_title}{RESET}")
    print(f"👉 {BOLD}Thư mục chính:{RESET} {YELLOW}{curr_cwd}{RESET}\n")
    
    try:
        new_proj = input(f"{BOLD}📌 Nhập tên dự án mới [Enter để giữ '{curr_proj}']: {RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nĐã hủy.")
        return
        
    try:
        new_ver = input(f"{BOLD}🏷️ Nhập phiên bản mới [Enter để giữ '{curr_ver}']: {RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nĐã hủy.")
        return
        
    try:
        new_title = input(f"{BOLD}📝 Nhập tiêu đề mới [Enter để giữ '{curr_title}']: {RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nĐã hủy.")
        return
        
    try:
        new_cwd = input(f"{BOLD}📁 Nhập thư mục chính mới [Enter để giữ '{curr_cwd}']: {RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nĐã hủy.")
        return
        
    final_proj = new_proj if new_proj else curr_proj
    final_title = new_title if new_title else curr_title
    final_ver = new_ver if new_ver else curr_ver
    final_cwd = new_cwd if new_cwd else curr_cwd
    
    update_session_names(cid, final_proj, final_title, final_ver, final_cwd)
    session["project_name"] = final_proj
    session["title"] = final_title
    session["version"] = final_ver
    session["cwd"] = final_cwd
    
    print(f"\n{GREEN}{BOLD}✅ Đã cập nhật thành công!{RESET}")
    print(f"👉 {BOLD}Dự án mới   :{RESET} {GREEN}{final_proj}{RESET}")
    print(f"👉 {BOLD}Phiên bản   :{RESET} {GREEN}{final_ver}{RESET}")
    print(f"👉 {BOLD}Tiêu đề mới :{RESET} {GREEN}{final_title}{RESET}")
    print(f"👉 {BOLD}Thư mục mới :{RESET} {GREEN}{final_cwd}{RESET}\n")

def load_conversation_details(session):
    cid = session["id"]
    log_path = os.path.join(BRAIN_DIR, cid, ".system_generated", "logs", "transcript.jsonl")
    if not os.path.exists(log_path):
        return None

    turns_list = []
    current_turn = None

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    m_type = obj.get("type")
                    t_iso = obj.get("created_at", "")
                    step_dt = parse_iso_time(t_iso)
                    time_str = format_datetime(step_dt) if step_dt else ""

                    if m_type == "USER_INPUT":
                        if current_turn:
                            turns_list.append(current_turn)
                        prompt = clean_text(obj.get("content", ""))
                        current_turn = {
                            "prompt": prompt,
                            "time": time_str,
                            "tools": [],
                            "response": ""
                        }
                    elif m_type == "PLANNER_RESPONSE" and current_turn:
                        res_txt = clean_text(obj.get("content", ""))
                        if res_txt:
                            current_turn["response"] = res_txt
                        for tc in obj.get("tool_calls", []):
                            t_name = tc.get("name", "")
                            t_summary = tc.get("args", {}).get("toolAction") or tc.get("args", {}).get("toolSummary") or ""
                            if t_name:
                                current_turn["tools"].append(f"{t_name} ({t_summary})" if t_summary else t_name)
                except Exception:
                    pass
        if current_turn:
            turns_list.append(current_turn)
    except Exception as e:
        print(f"Lỗi đọc transcript: {e}")
        return None

    # Check artifacts / scratch files
    artifacts = []
    brain_path = os.path.join(BRAIN_DIR, cid)
    scratch_path = os.path.join(brain_path, "scratch")
    if os.path.exists(scratch_path):
        for sf in os.listdir(scratch_path):
            if not sf.endswith(".metadata.json"):
                artifacts.append(f"scratch/{sf}")
    for root, dirs, files in os.walk(brain_path):
        if ".system_generated" in root or ".user_uploaded" in root or ".tempmediaStorage" in root or "scratch" in root:
            continue
        for f in files:
            artifacts.append(f)

    return {
        "session": session,
        "turns": turns_list,
        "artifacts": artifacts
    }

def view_conversation(session):
    details = load_conversation_details(session)
    if not details:
        print(f"{YELLOW}Không thể tải chi tiết cuộc trò chuyện {session['id']}.{RESET}")
        return

    s = details["session"]
    turns = details["turns"]
    artifacts = details["artifacts"]

    print(f"\n{CYAN}{BOLD}======================================================================{RESET}")
    print(f"{CYAN}{BOLD}              CHI TIẾT CUỘC TRÒ CHUYỆN & CÁC CÂU HỎI                  {RESET}")
    print(f"{CYAN}{BOLD}======================================================================{RESET}")
    print(f"👉 {BOLD}Tiêu đề      :{RESET} {s['title']}")
    print(f"👉 {BOLD}Dự án        :{RESET} {s['project_name']} | 🏷️ {s.get('version', '-')}")
    print(f"👉 {BOLD}Thư mục chính:{RESET} 📁 {s['cwd']}")
    if s.get('git_repo_str'):
        print(f"👉 {BOLD}Git Repo     :{RESET} {s['git_repo_str']}")
    print(f"👉 {BOLD}Conversation :{RESET} {s['id']}")
    if s['parent_id']:
        print(f"👉 {BOLD}Phân nhánh từ:{RESET} {MAGENTA}{s['parent_id']}{RESET}")
    print(f"👉 {BOLD}Thời gian    :{RESET} Tạo lúc {s['created_at_str']} | Cập nhật {s['updated_at_str']}")
    print(f"👉 {BOLD}Tổng số câu hỏi/lượt:{RESET} {len(turns)} lượt trao đổi")

    if artifacts:
        print(f"\n📂 {BOLD}File & Artifacts sinh ra trong phiên ({len(artifacts)}):{RESET}")
        for af in artifacts[:10]:
            print(f"   - {af}")
        if len(artifacts) > 10:
            print(f"   ... và {len(artifacts) - 10} file khác.")

    print(f"\n{YELLOW}{BOLD}--- LỊCH SỬ CÂU HỎI & PHẢN HỒI ({len(turns)} lượt) ---{RESET}")
    for idx, t in enumerate(turns, 1):
        print(f"\n{GREEN}{BOLD}[LƯỢT {idx}] {t['time']}{RESET}")
        print(f"{CYAN}{BOLD}👤 Câu hỏi / Yêu cầu:{RESET}")
        print(f"   {t['prompt']}")

        if t['tools']:
            unique_tools = list(dict.fromkeys(t['tools']))
            print(f"{DIM}🛠  Công cụ thực thi ({len(unique_tools)}):{RESET} {', '.join(unique_tools[:5])}")

        if t['response']:
            resp_preview = t['response']
            if len(resp_preview) > 300:
                resp_preview = resp_preview[:297] + "..."
            print(f"{BLUE}🤖 Tóm tắt trả lời:{RESET}\n   {resp_preview}")
        print(f"{DIM}----------------------------------------------------------------------{RESET}")

    # View options
    print(f"\n{BOLD}Hành động cho phiên này:{RESET}")
    print(f"  {GREEN}[r] Tiếp tục phiên này với agy (Resume){RESET}")
    print(f"  {YELLOW}[rn] Đổi tên dự án / Tiêu đề (Rename){RESET}")
    print(f"  {MAGENTA}[b] Tạo phân nhánh mới từ phiên này (Branch/Fork){RESET}")
    print(f"  {YELLOW}[q] Quay lại danh sách{RESET}\n")

    while True:
        try:
            act = input(f"{BOLD}👉 Chọn hành động [r/rn/b/q]: {RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return

        if act in ["r", "resume", "1"]:
            resume_session(s)
            break
        elif act in ["rn", "rename", "2"]:
            cli_rename_session(s)
            break
        elif act in ["b", "branch", "3"]:
            branch_conversation(s)
            break
        elif act in ["q", "quit", "exit", ""]:
            break

def perform_branch_clone(old_session, branch_title):
    """Thực hiện clone database và thư mục brain cho phân nhánh mới."""
    old_cid = old_session["id"]
    new_cid = str(uuid.uuid4())
    
    # 1. Clone conversation SQLite DB
    old_db = os.path.join(CONVERSATIONS_DIR, f"{old_cid}.db")
    new_db = os.path.join(CONVERSATIONS_DIR, f"{new_cid}.db")
    if os.path.exists(old_db):
        try:
            shutil.copyfile(old_db, new_db)
            con = sqlite3.connect(new_db)
            cur = con.cursor()
            cur.execute("UPDATE trajectory_meta SET cascade_id = ? WHERE cascade_id = ?", (new_cid, old_cid))
            
            tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            if 'steps' in tables:
                cols = [d[0] for d in cur.execute("SELECT * FROM steps LIMIT 1").description]
                target_cols = [c for c in ['step_payload', 'metadata', 'render_info', 'task_details', 'error_details'] if c in cols]
                for col in target_cols:
                    rows = cur.execute(f"SELECT idx, {col} FROM steps WHERE {col} IS NOT NULL").fetchall()
                    for idx, val in rows:
                        if isinstance(val, bytes) and old_cid.encode('utf-8') in val:
                            new_val = val.replace(old_cid.encode('utf-8'), new_cid.encode('utf-8'))
                            cur.execute(f"UPDATE steps SET {col} = ? WHERE idx = ?", (new_val, idx))
                        elif isinstance(val, str) and old_cid in val:
                            new_val = val.replace(old_cid, new_cid)
                            cur.execute(f"UPDATE steps SET {col} = ? WHERE idx = ?", (new_val, idx))
            con.commit()
            con.close()
        except Exception as e:
            print(f"Cảnh báo khi nhân bản database: {e}")

    # 2. Clone Brain directory
    old_brain = os.path.join(BRAIN_DIR, old_cid)
    new_brain = os.path.join(BRAIN_DIR, new_cid)
    if os.path.exists(old_brain):
        try:
            shutil.copytree(old_brain, new_brain, dirs_exist_ok=True)
            text_exts = ('.jsonl', '.json', '.txt', '.md', '.log', '.py', '.js', '.ts', '.html', '.css', '.pbtxt', '.yaml', '.yml')
            for root, dirs, files in os.walk(new_brain):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in text_exts or f in ['transcript.jsonl', 'transcript_full.jsonl']:
                        fpath = os.path.join(root, f)
                        try:
                            with open(fpath, 'r', encoding='utf-8', errors='ignore') as file:
                                content = file.read()
                            if old_cid in content:
                                new_content = content.replace(old_cid, new_cid)
                                with open(fpath, 'w', encoding='utf-8') as file:
                                    file.write(new_content)
                        except Exception:
                            pass
        except Exception as e:
            print(f"Cảnh báo khi sao chép brain: {e}")

    # 3. Update conversation_summaries.db
    if os.path.exists(SUMMARIES_DB_PATH):
        try:
            con = sqlite3.connect(SUMMARIES_DB_PATH)
            cur = con.cursor()
            row = cur.execute("SELECT * FROM conversation_summaries WHERE conversation_id = ?", (old_cid,)).fetchone()
            if row:
                cols = [d[0] for d in cur.execute("SELECT * FROM conversation_summaries LIMIT 1").description]
                row_dict = dict(zip(cols, row))
                row_dict['conversation_id'] = new_cid
                row_dict['parent_conversation_id'] = old_cid
                row_dict['title'] = branch_title
                now_iso = datetime.now(timezone.utc).isoformat()
                row_dict['last_modified_time'] = now_iso
                row_dict['last_user_input_time'] = now_iso
                
                placeholders = ', '.join(['?'] * len(cols))
                col_names = ', '.join(cols)
                values = [row_dict.get(c) for c in cols]
                cur.execute(f"INSERT OR REPLACE INTO conversation_summaries ({col_names}) VALUES ({placeholders})", values)
                con.commit()
            con.close()
        except Exception as e:
            print(f"Cảnh báo khi cập nhật summaries: {e}")

    new_session = dict(old_session)
    new_session["id"] = new_cid
    new_session["title"] = branch_title
    new_session["parent_id"] = old_cid
    return new_session

def branch_conversation(session):
    old_cid = session["id"]
    old_title = session.get("title") or session.get("project_name") or "Phiên làm việc"

    print(f"\n{MAGENTA}{BOLD}======================================================================{RESET}")
    print(f"{MAGENTA}{BOLD}       TẠO PHÂN NHÁNH CUỘC TRÒ CHUYỆN (CONVERSATION BRANCH)           {RESET}")
    print(f"{MAGENTA}{BOLD}======================================================================{RESET}")
    print(f"👉 {BOLD}Phiên gốc    :{RESET} {old_title}")
    print(f"👉 {BOLD}ID gốc       :{RESET} {old_cid}")

    # Ask for branch title/note
    default_branch_title = f"[Nhánh] {old_title} ({datetime.now().strftime('%d/%m %H:%M')})"
    print(f"\nNhập tiêu đề hoặc ghi chú cho nhánh mới.")
    try:
        user_title = input(f"{BOLD}👉 Tiêu đề nhánh [Mặc định: {default_branch_title}]: {RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nĐã hủy tạo nhánh.")
        return None

    branch_title = user_title if user_title else default_branch_title
    print(f"\n{CYAN}⏳ Đang sao chép toàn bộ bộ nhớ, ngữ cảnh và lịch sử sang nhánh mới...{RESET}")

    new_session = perform_branch_clone(session, branch_title)

    print(f"\n{GREEN}{BOLD}✅ Tạo phân nhánh thành công!{RESET}")
    print(f"🌱 {BOLD}Nhánh mới:{RESET} {branch_title}")
    print(f"🆔 {BOLD}ID mới   :{RESET} {new_session['id']}")
    print(f"🛡️ {BOLD}Bảo toàn :{RESET} Cuộc trò chuyện gốc ({old_cid}) được giữ nguyên 100%.")
    print(f"🧠 {BOLD}Bộ nhớ   :{RESET} Toàn bộ ngữ cảnh, câu hỏi, file và công việc trước đó đã được nhân bản sang nhánh mới.")

    try:
        launch = input(f"\n{BOLD}👉 Bạn có muốn khởi chạy ngay nhánh này với agy? [Y/n]: {RESET}").strip().lower()
    except (KeyboardInterrupt, EOFError):
        launch = "n"

    if launch != "n":
        resume_session(new_session)

    return new_session

def resume_session(session):
    cid = session["id"]
    cwd = session.get("cwd") or DEFAULT_PROJECT_DIR
    proj = session.get("project_name", "General")
    title = session.get("title", proj)
    
    print(f"\n{GREEN}{BOLD}🚀 Đang tiếp tục phiên làm việc...{RESET}")
    print(f"👉 {BOLD}Tiêu đề      :{RESET} {title}")
    print(f"👉 {BOLD}Dự án        :{RESET} {proj}")
    if session.get("version") and session.get("version") != "-":
        print(f"👉 {BOLD}Phiên bản    :{RESET} {session['version']}")
    print(f"👉 {BOLD}Thư mục chính:{RESET} {cwd}")
    print(f"👉 {BOLD}ID           :{RESET} {cid}")
    if session.get("git_repo_str"):
        print(f"👉 {BOLD}Git          :{RESET} {session['git_repo_str']}")
    if session.get("parent_id"):
        print(f"👉 {BOLD}Nhánh từ     :{RESET} {session['parent_id']}")
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

# ==============================================================================
# GIAO DIỆN ĐỒ HỌA GUI (TKINTER) - ĐẦY ĐỦ CHỨC NĂNG, PHIÊN BẢN & LINK THƯ MỤC
# ==============================================================================

class RenameDialog:
    """Hộp thoại đổi tên dự án, phiên bản, tiêu đề và thư mục chính trên GUI."""
    def __init__(self, parent, session, on_saved_callback):
        self.session = session
        self.on_saved = on_saved_callback
        
        self.top = tk.Toplevel(parent)
        self.top.title("✏️ Cập nhật thông tin dự án & phiên làm việc - agyr")
        self.top.geometry("620x520")
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.grab_set()
        
        # Căn giữa cửa sổ con theo cửa sổ cha
        self.top.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w, h = 620, 520
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.top.geometry(f"{w}x{h}+{x}+{y}")
        
        main_frame = ttk.Frame(self.top, padding=16)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        header_lbl = ttk.Label(
            main_frame,
            text="✏️ CẬP NHẬT THÔNG TIN DỰ ÁN & PHIÊN LÀM VIỆC",
            font=("Segoe UI", 11, "bold"),
            foreground="#0969da"
        )
        header_lbl.pack(anchor=tk.W, pady=(0, 10))
        
        info_frame = ttk.LabelFrame(main_frame, text="Thông tin hệ thống", padding=8)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(info_frame, text=f"🆔 ID: {session['id']}", font=("Segoe UI", 8), foreground="#57606a").pack(anchor=tk.W)
        if session.get('git_repo_str'):
            ttk.Label(info_frame, text=f"🔗 Git: {session['git_repo_str']}", font=("Segoe UI", 8), foreground="#0969da").pack(anchor=tk.W)
        
        # Form fields
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Row 1: Tên dự án & Phiên bản
        row1_frame = ttk.Frame(form_frame)
        row1_frame.pack(fill=tk.X, pady=(2, 4))
        
        # Tên dự án
        proj_col = ttk.Frame(row1_frame)
        proj_col.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Label(proj_col, text="📌 Tên dự án (Project Name):", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(2, 2))
        self.ent_project = ttk.Entry(proj_col, font=("Segoe UI", 10))
        self.ent_project.pack(fill=tk.X)
        self.ent_project.insert(0, session.get("project_name", ""))
        
        # Phiên bản
        ver_col = ttk.Frame(row1_frame)
        ver_col.pack(side=tk.RIGHT, fill=tk.X, padx=(0, 0))
        ttk.Label(ver_col, text="🏷️ Phiên bản (Version):", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(2, 2))
        self.ent_version = ttk.Entry(ver_col, font=("Segoe UI", 10), width=16)
        self.ent_version.pack(fill=tk.X)
        curr_v = session.get("version", "")
        self.ent_version.insert(0, "" if curr_v == "-" else curr_v)
        
        ttk.Label(form_frame, text="   Gợi ý phiên bản: v1.38.6, v2.1.0, 1.0.0... (hoặc để tự động nhận diện)", font=("Segoe UI", 8), foreground="#656d76").pack(anchor=tk.W, pady=(0, 8))
        
        # Row 2: Tiêu đề phiên
        ttk.Label(form_frame, text="📝 Tiêu đề phiên (Title):", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(2, 2))
        self.ent_title = ttk.Entry(form_frame, font=("Segoe UI", 10))
        self.ent_title.pack(fill=tk.X, pady=(0, 2))
        self.ent_title.insert(0, session.get("title", ""))
        ttk.Label(form_frame, text="   Mô tả ngắn mục tiêu phiên làm việc để dễ tìm kiếm", font=("Segoe UI", 8), foreground="#656d76").pack(anchor=tk.W, pady=(0, 8))
        
        # Row 3: Thư mục chính (CWD)
        ttk.Label(form_frame, text="📁 Thư mục chính của dự án (Project Directory):", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(2, 2))
        cwd_frame = ttk.Frame(form_frame)
        cwd_frame.pack(fill=tk.X, pady=(0, 2))
        
        self.ent_cwd = ttk.Entry(cwd_frame, font=("Segoe UI", 10))
        self.ent_cwd.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.ent_cwd.insert(0, session.get("cwd", ""))
        
        btn_browse = ttk.Button(cwd_frame, text="📁 Duyệt...", command=self.browse_folder)
        btn_browse.pack(side=tk.RIGHT)
        
        ttk.Label(form_frame, text="   Đường dẫn thư mục nguồn chính trên máy tính (sẽ được mở khi bấm link)", font=("Segoe UI", 8), foreground="#656d76").pack(anchor=tk.W, pady=(0, 12))
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(8, 0))
        
        btn_cancel = ttk.Button(btn_frame, text="Hủy bỏ (Esc)", command=self.top.destroy)
        btn_cancel.pack(side=tk.RIGHT, padx=(6, 0))
        
        btn_save = ttk.Button(btn_frame, text="💾 Lưu thay đổi (Enter)", command=self.save)
        btn_save.pack(side=tk.RIGHT)
        
        self.top.bind("<Return>", lambda e: self.save())
        self.top.bind("<Escape>", lambda e: self.top.destroy())
        
        self.ent_project.focus_set()
        self.ent_project.select_range(0, tk.END)

    def browse_folder(self):
        initial = self.ent_cwd.get().strip() or DEFAULT_PROJECT_DIR
        if not os.path.isdir(initial):
            initial = DEFAULT_PROJECT_DIR
        selected = filedialog.askdirectory(parent=self.top, initialdir=initial, title="Chọn thư mục chính của dự án")
        if selected:
            self.ent_cwd.delete(0, tk.END)
            self.ent_cwd.insert(0, normalize_path(selected))

    def save(self):
        new_proj = self.ent_project.get().strip()
        new_ver = self.ent_version.get().strip()
        new_title = self.ent_title.get().strip()
        new_cwd = self.ent_cwd.get().strip()
        
        if not new_proj and not new_title:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập ít nhất Tên dự án hoặc Tiêu đề mới.", parent=self.top)
            return
            
        update_session_names(self.session["id"], new_proj, new_title, new_ver, new_cwd)
        if new_proj:
            self.session["project_name"] = new_proj
        if new_title:
            self.session["title"] = new_title
        if new_ver:
            self.session["version"] = new_ver
        if new_cwd:
            self.session["cwd"] = normalize_path(new_cwd)
            
        if self.on_saved:
            self.on_saved(self.session)
            
        self.top.destroy()

class ViewDetailDialog:
    """Hộp thoại xem chi tiết lịch sử câu hỏi và trả lời của phiên."""
    def __init__(self, parent, session):
        self.top = tk.Toplevel(parent)
        self.top.title(f"🔍 Chi tiết phiên: {session.get('project_name')} - {session.get('title')}")
        self.top.geometry("880x620")
        self.top.transient(parent)
        
        # Center dialog
        self.top.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w, h = 880, 620
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.top.geometry(f"{w}x{h}+{x}+{y}")
        
        main_frame = ttk.Frame(self.top, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header Info
        header_frame = ttk.LabelFrame(main_frame, text="Thông tin tổng quan", padding=8)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        ver_badge = f" [{session.get('version')}]" if session.get('version') and session.get('version') != '-' else ""
        ttk.Label(header_frame, text=f"📌 Dự án: {session.get('project_name')}{ver_badge} | Tiêu đề: {session.get('title')}", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"📁 Thư mục chính: {session['cwd']}", font=("Segoe UI", 9)).pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"🆔 Conversation ID: {session['id']}", font=("Segoe UI", 9)).pack(anchor=tk.W)
        if session.get('git_repo_str'):
            ttk.Label(header_frame, text=f"🔗 Git Repo: {session['git_repo_str']}", font=("Segoe UI", 9), foreground="#0969da").pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"🕒 Tạo lúc: {session['created_at_str']} | Cập nhật cuối: {session['updated_at_str']} | Lượt: {session['turns']}", font=("Segoe UI", 9), foreground="#57606a").pack(anchor=tk.W)
        
        # Text view
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.txt = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set, font=("Consolas", 10), padx=8, pady=8)
        self.txt.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.txt.yview)
        
        # Load details
        details = load_conversation_details(session)
        if details:
            turns = details.get("turns", [])
            self.txt.insert(tk.END, f"=== LỊCH SỬ CÁC LƯỢT TRAO ĐỔI ({len(turns)} lượt) ===\n\n")
            for idx, t in enumerate(turns, 1):
                self.txt.insert(tk.END, f"--------------------------------------------------------------------------------\n")
                self.txt.insert(tk.END, f"[LƯỢT {idx}] Thời gian: {t.get('time', '')}\n")
                self.txt.insert(tk.END, f"👤 YÊU CẦU CỦA BẠN:\n{t.get('prompt', '')}\n\n")
                if t.get('tools'):
                    self.txt.insert(tk.END, f"🛠 CÔNG CỤ ĐÃ GỌI: {', '.join(t['tools'])}\n\n")
                if t.get('response'):
                    self.txt.insert(tk.END, f"🤖 PHẢN HỒI CỦA TRỢ LÝ:\n{t.get('response', '')}\n\n")
            
            artifacts = details.get("artifacts", [])
            if artifacts:
                self.txt.insert(tk.END, f"\n=== CÁC FILE / ARTIFACTS TRONG PHIÊN ({len(artifacts)}) ===\n")
                for af in artifacts:
                    self.txt.insert(tk.END, f" - {af}\n")
        else:
            self.txt.insert(tk.END, "Không thể tải chi tiết phiên làm việc này.")
            
        self.txt.config(state=tk.DISABLED)
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(8, 0))
        
        btn_open = ttk.Button(btn_frame, text="📁 Mở thư mục dự án", command=lambda: self.open_folder(session['cwd']))
        btn_open.pack(side=tk.LEFT)
        
        btn_close = ttk.Button(btn_frame, text="Đóng (Esc)", command=self.top.destroy)
        btn_close.pack(side=tk.RIGHT)
        self.top.bind("<Escape>", lambda e: self.top.destroy())

    def open_folder(self, cwd):
        if cwd and os.path.isdir(cwd):
            subprocess.Popen(["explorer", cwd])

class BranchDialog:
    """Hộp thoại tạo phân nhánh (Fork) mới trên GUI."""
    def __init__(self, parent, session, on_branched_callback):
        self.session = session
        self.on_branched = on_branched_callback
        
        self.top = tk.Toplevel(parent)
        self.top.title("🌿 Tạo phân nhánh mới (Branch/Fork) - agyr")
        self.top.geometry("520x260")
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.grab_set()
        
        # Center dialog
        self.top.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        w, h = 520, 260
        x = px + max(0, (pw - w) // 2)
        y = py + max(0, (ph - h) // 2)
        self.top.geometry(f"{w}x{h}+{x}+{y}")
        
        main_frame = ttk.Frame(self.top, padding=16)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="🌿 TẠO PHÂN NHÁNH CUỘC TRÒ CHUYỆN (FORK)", font=("Segoe UI", 11, "bold"), foreground="#8250df").pack(anchor=tk.W, pady=(0, 6))
        ttk.Label(main_frame, text=f"Phiên gốc: {session.get('project_name')} - {session.get('title')}", font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(0, 10))
        
        default_title = f"[Nhánh] {session.get('title') or session.get('project_name')} ({datetime.now().strftime('%d/%m %H:%M')})"
        ttk.Label(main_frame, text="Tiêu đề hoặc ghi chú cho nhánh mới:", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(4, 2))
        self.ent_title = ttk.Entry(main_frame, font=("Segoe UI", 10))
        self.ent_title.pack(fill=tk.X, pady=(0, 15))
        self.ent_title.insert(0, default_title)
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        btn_cancel = ttk.Button(btn_frame, text="Hủy (Esc)", command=self.top.destroy)
        btn_cancel.pack(side=tk.RIGHT, padx=(6, 0))
        
        btn_fork = ttk.Button(btn_frame, text="🌿 Tạo nhánh ngay", command=self.create_branch)
        btn_fork.pack(side=tk.RIGHT)
        
        self.top.bind("<Return>", lambda e: self.create_branch())
        self.top.bind("<Escape>", lambda e: self.top.destroy())
        self.ent_title.focus_set()

    def create_branch(self):
        title = self.ent_title.get().strip()
        if not title:
            title = f"Nhánh mới ({datetime.now().strftime('%d/%m %H:%M')})"
        new_session = perform_branch_clone(self.session, title)
        if self.on_branched:
            self.on_branched(new_session)
        self.top.destroy()

class SessionManagerGUI:
    """Giao diện đồ họa bảng điều khiển phiên làm việc Antigravity."""
    def __init__(self, sessions):
        self.sessions = list(sessions)
        self.filtered_sessions = list(sessions)
        self.selected_target = None
        self.sort_column = "updated"
        self.sort_desc = True

        self.root = tk.Tk()
        self.root.title("Antigravity Session Manager (agyr) - Quản lý phiên làm việc & Dự án")
        self.root.geometry("1280x720")
        self.root.minsize(980, 520)
        
        # Căn giữa màn hình
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = 1280, 720
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        
        # Áp dụng theme hệ thống
        self.style = ttk.Style()
        try:
            self.style.theme_use("vista")
        except Exception:
            pass
            
        self.style.configure("Treeview", font=("Segoe UI", 9), rowheight=26)
        self.style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        
        self.setup_ui()
        self.populate_table(self.filtered_sessions)

    def setup_ui(self):
        # Top Toolbar Frame
        top_frame = ttk.Frame(self.root, padding=8)
        top_frame.pack(fill=tk.X)
        
        # Search Box
        ttk.Label(top_frame, text="🔍 Tìm kiếm:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(4, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.filter_table())
        self.search_entry = ttk.Entry(top_frame, textvariable=self.search_var, width=30, font=("Segoe UI", 9))
        self.search_entry.pack(side=tk.LEFT, padx=(0, 2))
        
        btn_clear = ttk.Button(top_frame, text="✖", width=3, command=self.clear_search)
        btn_clear.pack(side=tk.LEFT, padx=(0, 10))
        
        # Action Buttons
        btn_resume = ttk.Button(top_frame, text="🚀 Tiếp tục (Enter)", command=self.on_resume)
        btn_resume.pack(side=tk.LEFT, padx=3)
        
        btn_rename = ttk.Button(top_frame, text="✏️ Đổi tên / Sửa (F2)", command=self.on_rename)
        btn_rename.pack(side=tk.LEFT, padx=3)
        
        btn_folder = ttk.Button(top_frame, text="📁 Mở thư mục", command=self.on_open_folder)
        btn_folder.pack(side=tk.LEFT, padx=3)
        
        btn_branch = ttk.Button(top_frame, text="🌿 Phân nhánh", command=self.on_branch)
        btn_branch.pack(side=tk.LEFT, padx=3)
        
        btn_view = ttk.Button(top_frame, text="🔍 Xem chi tiết", command=self.on_view_details)
        btn_view.pack(side=tk.LEFT, padx=3)
        
        btn_refresh = ttk.Button(top_frame, text="🔄 Làm mới", command=self.on_refresh)
        btn_refresh.pack(side=tk.RIGHT, padx=4)

        # Center Treeview Table
        tree_frame = ttk.Frame(self.root, padding=(8, 0, 8, 4))
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Cột: STT, Dự án, Phiên bản, Tiêu đề, Thư mục chính, Cập nhật, Lượt, Git Repo, Yêu cầu gần nhất, ID
        cols = ("stt", "project", "version", "title", "cwd_link", "updated", "turns", "git", "last_prompt", "id")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        
        # Setup Columns & Headings (hỗ trợ click để sort)
        self.tree.heading("stt", text="#", command=lambda: self.sort_by("stt"))
        self.tree.heading("project", text="📌 Dự án", command=lambda: self.sort_by("project"))
        self.tree.heading("version", text="🏷️ Phiên bản", command=lambda: self.sort_by("version"))
        self.tree.heading("title", text="📝 Tiêu đề", command=lambda: self.sort_by("title"))
        self.tree.heading("cwd_link", text="📁 Thư mục chính (Click để mở)", command=lambda: self.sort_by("cwd_link"))
        self.tree.heading("updated", text="🕒 Ngày cập nhật", command=lambda: self.sort_by("updated"))
        self.tree.heading("turns", text="Lượt", command=lambda: self.sort_by("turns"))
        self.tree.heading("git", text="🔗 Git Repo", command=lambda: self.sort_by("git"))
        self.tree.heading("last_prompt", text="💬 Yêu cầu gần nhất", command=lambda: self.sort_by("last_prompt"))
        self.tree.heading("id", text="🆔 ID", command=lambda: self.sort_by("id"))
        
        self.tree.column("stt", width=42, anchor="center")
        self.tree.column("project", width=165, anchor="w")
        self.tree.column("version", width=85, anchor="center")
        self.tree.column("title", width=220, anchor="w")
        self.tree.column("cwd_link", width=225, anchor="w")
        self.tree.column("updated", width=135, anchor="center")
        self.tree.column("turns", width=45, anchor="center")
        self.tree.column("git", width=175, anchor="w")
        self.tree.column("last_prompt", width=250, anchor="w")
        self.tree.column("id", width=95, anchor="center")
        
        # Alternating row colors
        self.tree.tag_configure("odd", background="#ffffff")
        self.tree.tag_configure("even", background="#f8f9fa")
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Status Bar
        status_frame = ttk.Frame(self.root, padding=(10, 6))
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.lbl_status = ttk.Label(status_frame, text="", font=("Segoe UI", 9))
        self.lbl_status.pack(side=tk.LEFT)
        
        self.lbl_msg = ttk.Label(status_frame, text="Sẵn sàng (Nhấn F2 để đổi tên/phiên bản, double-click cột Thư mục để mở Explorer)", font=("Segoe UI", 9), foreground="#0969da")
        self.lbl_msg.pack(side=tk.RIGHT)
        
        # Event Bindings
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Return>", lambda e: self.on_resume())
        self.tree.bind("<F2>", lambda e: self.on_rename())
        self.tree.bind("<<TreeviewSelect>>", self.on_selection_change)
        self.tree.bind("<Button-3>", self.on_right_click)
        
        # Context Menu
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="🚀 Tiếp tục phiên này (Enter)", command=self.on_resume)
        self.context_menu.add_command(label="📁 Mở thư mục chính trong Explorer", command=self.on_open_folder)
        self.context_menu.add_command(label="✏️ Đổi tên dự án / Phiên bản / Tiêu đề (F2)", command=self.on_rename)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🌿 Tạo phân nhánh mới (Branch)", command=self.on_branch)
        self.context_menu.add_command(label="🔍 Xem chi tiết lịch sử câu hỏi", command=self.on_view_details)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="📋 Sao chép đường dẫn thư mục chính", command=self.on_copy_cwd)
        self.context_menu.add_command(label="📋 Sao chép Conversation ID", command=self.on_copy_id)
        self.context_menu.add_command(label="📋 Sao chép lệnh tiếp tục (agy --conversation ...)", command=self.on_copy_cmd)

    def populate_table(self, sessions_to_show):
        self.tree.delete(*self.tree.get_children())
        for idx, s in enumerate(sessions_to_show, 1):
            tag = "even" if idx % 2 == 0 else "odd"
            parent_badge = f" [Nhánh: {s['parent_id'][:6]}]" if s.get('parent_id') else ""
            ver_text = s.get("version", "-")
            self.tree.insert("", "end", iid=s["id"], tags=(tag,), values=(
                idx,
                s.get("project_name", "") + parent_badge,
                ver_text,
                s.get("title", ""),
                s.get("cwd", ""),
                s.get("updated_iso", ""),
                s.get("turns", 0),
                s.get("git_repo_str", ""),
                (s.get("last_prompt", "") or "")[:150],
                s.get("id", "")[:12] + "..."
            ))
            
        self.lbl_status.config(text=f"Tổng số: {len(self.sessions)} phiên | Đang hiển thị: {len(sessions_to_show)} phiên")
        if sessions_to_show:
            first_id = sessions_to_show[0]["id"]
            if self.tree.exists(first_id):
                self.tree.selection_set(first_id)
                self.tree.focus(first_id)

    def filter_table(self):
        q = self.search_var.get().strip().lower()
        if not q:
            self.filtered_sessions = list(self.sessions)
        else:
            self.filtered_sessions = [
                s for s in self.sessions
                if q in s.get("project_name", "").lower()
                or q in s.get("version", "").lower()
                or q in s.get("title", "").lower()
                or q in s.get("git_repo_str", "").lower()
                or q in s.get("cwd", "").lower()
                or q in s.get("id", "").lower()
                or q in s.get("first_prompt", "").lower()
                or q in s.get("last_prompt", "").lower()
                or q in s.get("last_assistant", "").lower()
            ]
        self.populate_table(self.filtered_sessions)

    def clear_search(self):
        self.search_var.set("")
        self.search_entry.focus_set()

    def sort_by(self, col):
        if self.sort_column == col:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_column = col
            self.sort_desc = False
            
        key_map = {
            "stt": lambda s: 0,
            "project": lambda s: s.get("project_name", "").lower(),
            "version": lambda s: s.get("version", "").lower(),
            "title": lambda s: s.get("title", "").lower(),
            "cwd_link": lambda s: s.get("cwd", "").lower(),
            "updated": lambda s: s.get("updated_iso", ""),
            "turns": lambda s: s.get("turns", 0),
            "git": lambda s: s.get("git_repo_str", "").lower(),
            "last_prompt": lambda s: s.get("last_prompt", "").lower(),
            "id": lambda s: s.get("id", "").lower()
        }
        
        sort_fn = key_map.get(col, lambda s: s.get("updated_iso", ""))
        self.filtered_sessions.sort(key=sort_fn, reverse=self.sort_desc)
        self.populate_table(self.filtered_sessions)
        arrow = "▼" if self.sort_desc else "▲"
        self.lbl_msg.config(text=f"Sắp xếp theo '{col}' {arrow}")

    def get_selected_session(self):
        sel = self.tree.selection()
        if not sel:
            return None
        sel_id = sel[0]
        return next((s for s in self.sessions if s["id"] == sel_id), None)

    def on_selection_change(self, event):
        s = self.get_selected_session()
        if s:
            disp_cwd = s.get('cwd', '')
            if len(disp_cwd) > 40: disp_cwd = disp_cwd[:37] + "..."
            ver_text = f" | Phiên bản: {s.get('version')}" if s.get('version') and s.get('version') != '-' else ""
            self.lbl_msg.config(text=f"Dự án: {s.get('project_name')}{ver_text} | Thư mục: {disp_cwd}")

    def on_double_click(self, event):
        # Kiểm tra xem người dùng double click vào cột nào
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            col = self.tree.identify_column(event.x)
            # Cột #5 là cột "cwd_link" (Thư mục chính)
            if col == "#5":
                self.on_open_folder()
                return
        self.on_resume()

    def on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.tree.focus(item)
            self.context_menu.post(event.x_root, event.y_root)

    def on_resume(self):
        s = self.get_selected_session()
        if s:
            self.selected_target = s
            self.root.destroy()
        else:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một phiên làm việc để tiếp tục.", parent=self.root)

    def on_rename(self):
        s = self.get_selected_session()
        if not s:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một phiên làm việc để cập nhật thông tin.", parent=self.root)
            return
            
        def on_saved(updated_session):
            # Cập nhật trực tiếp trên bảng Treeview
            sel_id = updated_session["id"]
            if self.tree.exists(sel_id):
                vals = list(self.tree.item(sel_id, "values"))
                vals[1] = updated_session.get("project_name", "")
                vals[2] = updated_session.get("version", "-")
                vals[3] = updated_session.get("title", "")
                vals[4] = updated_session.get("cwd", "")
                self.tree.item(sel_id, values=vals)
            ver_str = f" [{updated_session.get('version')}]" if updated_session.get('version') and updated_session.get('version') != '-' else ""
            self.lbl_msg.config(text=f"✅ Đã cập nhật thành công: {updated_session.get('project_name')}{ver_str} - {updated_session.get('title')}")
            
        RenameDialog(self.root, s, on_saved)

    def on_view_details(self):
        s = self.get_selected_session()
        if not s:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một phiên làm việc để xem chi tiết.", parent=self.root)
            return
        ViewDetailDialog(self.root, s)

    def on_branch(self):
        s = self.get_selected_session()
        if not s:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một phiên làm việc để tạo nhánh.", parent=self.root)
            return
            
        def on_branched(new_session):
            self.sessions.insert(0, new_session)
            self.filter_table()
            if self.tree.exists(new_session["id"]):
                self.tree.selection_set(new_session["id"])
                self.tree.focus(new_session["id"])
            self.lbl_msg.config(text=f"🌿 Đã tạo nhánh mới: {new_session.get('title')}")
            
        BranchDialog(self.root, s, on_branched)

    def on_open_folder(self):
        s = self.get_selected_session()
        if not s:
            return
        cwd = s.get("cwd") or DEFAULT_PROJECT_DIR
        if os.path.isdir(cwd):
            try:
                subprocess.Popen(["explorer", cwd])
                self.lbl_msg.config(text=f"📁 Đã mở thư mục chính: {cwd}")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể mở thư mục: {e}", parent=self.root)
        else:
            messagebox.showwarning("Cảnh báo", f"Thư mục không tồn tại: {cwd}", parent=self.root)

    def on_copy_cwd(self):
        s = self.get_selected_session()
        if s and s.get("cwd"):
            self.root.clipboard_clear()
            self.root.clipboard_append(s["cwd"])
            self.lbl_msg.config(text=f"📋 Đã sao chép đường dẫn: {s['cwd']}")

    def on_copy_id(self):
        s = self.get_selected_session()
        if s:
            self.root.clipboard_clear()
            self.root.clipboard_append(s["id"])
            self.lbl_msg.config(text=f"📋 Đã sao chép ID: {s['id']}")

    def on_copy_cmd(self):
        s = self.get_selected_session()
        if s:
            cmd = f"agy --conversation {s['id']}"
            self.root.clipboard_clear()
            self.root.clipboard_append(cmd)
            self.lbl_msg.config(text=f"📋 Đã sao chép lệnh: {cmd}")

    def on_refresh(self):
        self.lbl_msg.config(text="Đang quét lại toàn bộ phiên làm việc...")
        self.root.update_idletasks()
        self.sessions = scan_sessions(limit=None)
        self.filter_table()
        self.lbl_msg.config(text=f"Đã làm mới danh sách ({len(self.sessions)} phiên)")

def run_gui_app(sessions):
    """
    Khởi chạy giao diện Tkinter GUI tương tác hiện đại.
    Hỗ trợ đổi tên dự án, xem phiên bản, mở thư mục chính, tìm kiếm, phân nhánh và tiếp tục phiên.
    Nếu môi trường không hỗ trợ Tkinter thì tự động fallback về Out-GridView.
    """
    if tk is None:
        return run_gui_grid(sessions)
    try:
        app = SessionManagerGUI(sessions)
        app.root.mainloop()
        if app.selected_target:
            resume_session(app.selected_target)
            return True
        return False
    except Exception as e:
        print(f"{YELLOW}Không thể khởi chạy GUI Tkinter ({e}). Chuyển sang Out-GridView...{RESET}")
        return run_gui_grid(sessions)

def run_gui_grid(sessions):
    """
    Hiển thị giao diện GUI bảng chọn Out-GridView của PowerShell (Fallback).
    Bao gồm cột PhienBan và ThuMucChinh.
    """
    items = []
    for idx, s in enumerate(sessions, 1):
        items.append({
            "STT": idx,
            "DuAn": s['project_name'],
            "PhienBan": s.get('version', '-'),
            "ThuMucChinh": s['cwd'],
            "TieuDe": s.get('title') or s.get('project_name'),
            "NgayCapNhat": s['updated_iso'],
            "NgayTao": s['created_iso'],
            "SoLuot": s['turns'],
            "GitRepo": s.get('git_repo_str') or "",
            "YeuCauGanNhat": (s['last_prompt'] or "")[:350],
            "PhanHoiCuoi": (s.get('last_assistant') or "")[:350],
            "YeuCauBanDau": (s['first_prompt'] or "")[:250],
            "NhanhGoc": s.get('parent_id') or "",
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
        f"$sel = $data | Out-GridView -Title 'Chọn phiên làm việc Antigravity (agy) để tiếp tục [Tổng số: {len(items)} phiên]' -PassThru; "
        f"if ($sel) {{ if ($sel -is [array]) {{ [Console]::WriteLine($sel[0].ConversationId) }} else {{ [Console]::WriteLine($sel.ConversationId) }} }}"
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

def resolve_target_session(sessions, arg):
    arg = arg.strip()
    if arg.isdigit():
        val = int(arg)
        if 1 <= val <= len(sessions):
            return sessions[val - 1]
    for s in sessions:
        if s["id"].lower() == arg.lower() or s["id"].lower().startswith(arg.lower()):
            return s
    for s in sessions:
        if arg.lower() in s["project_name"].lower() or arg.lower() in s["title"].lower():
            return s
    return None

def main():
    args = sys.argv[1:]
    # Quét toàn bộ phiên làm việc không giới hạn
    sessions = scan_sessions(limit=None)
    
    if not sessions:
        print(f"{YELLOW}Không tìm thấy phiên làm việc nào trong hệ thống.{RESET}")
        return

    # Xử lý các tham số dòng lệnh trực tiếp
    if args:
        first_arg = args[0].strip().lower()
        
        # Chế độ GUI: agyr -g / agyr --gui
        if first_arg in ["-g", "--gui"]:
            if run_gui_app(sessions):
                return
            print(f"{YELLOW}Đã đóng giao diện GUI.{RESET}")
            return

        # Chế độ Out-GridView: agyr --grid / agyr -ogv
        if first_arg in ["--grid", "-ogv"]:
            if run_gui_grid(sessions):
                return
            print(f"{YELLOW}Đã hủy chọn qua Out-GridView.{RESET}")
            return
            
        # Chế độ Đổi tên từ dòng lệnh: agyr -rn <stt|id> / agyr rename <stt|id>
        if first_arg in ["-rn", "--rename", "rn", "rename"]:
            target = None
            if len(args) > 1:
                target = resolve_target_session(sessions, args[1])
            if not target:
                target = sessions[0]
            cli_rename_session(target)
            return

        # Chế độ Liệt kê: agyr -l / agyr --list
        if first_arg in ["-l", "--list"]:
            print_banner()
            display_sessions(sessions)
            return

        # Chế độ Xem chi tiết: agyr -v <stt|id|từ khóa>
        if first_arg in ["-v", "--view"]:
            target = None
            if len(args) > 1:
                target = resolve_target_session(sessions, args[1])
            if not target:
                target = sessions[0]
            view_conversation(target)
            return

        # Chế độ Phân nhánh: agyr -b <stt|id|từ khóa>
        if first_arg in ["-b", "--branch"]:
            target = None
            if len(args) > 1:
                target = resolve_target_session(sessions, args[1])
            if not target:
                target = sessions[0]
            branch_conversation(target)
            return
            
        # Chọn số thứ tự trực tiếp: agyr 1
        if first_arg.isdigit():
            idx = int(first_arg)
            if 1 <= idx <= len(sessions):
                resume_session(sessions[idx - 1])
                return
            else:
                print(f"{YELLOW}Số thứ tự không hợp lệ (1 - {len(sessions)}).{RESET}")
                return
                
        # Chọn Conversation ID trực tiếp
        if len(first_arg) > 20 and "-" in first_arg:
            target = resolve_target_session(sessions, first_arg)
            if target:
                resume_session(target)
            else:
                resume_session({"id": first_arg, "cwd": DEFAULT_PROJECT_DIR, "project_name": "Specified ID"})
            return

        # Tìm kiếm từ khóa: agyr <keyword>
        query = " ".join(args).lower()
        matched = [
            s for s in sessions 
            if query in s['project_name'].lower() 
            or query in s.get('version', '').lower()
            or query in s['title'].lower() 
            or query in s['last_prompt'].lower() 
            or query in s['first_prompt'].lower()
            or query in s['cwd'].lower()
            or query in s['id'].lower()
            or query in s.get('git_repo_str', '').lower()
            or query in s.get('last_assistant', '').lower()
        ]
        if matched:
            print_banner()
            print(f"{GREEN}Tìm thấy {len(matched)} phiên phù hợp với từ khóa '{query}':{RESET}\n")
            display_sessions(matched)
            sessions = matched
        else:
            print(f"{YELLOW}Không tìm thấy phiên nào chứa từ khóa '{query}'. Hiển thị danh sách gần nhất:{RESET}\n")

    # Interactive Loop (Terminal)
    displayed = sessions[:15]
    print_banner()
    display_sessions(displayed)
    
    print(f"\n{BOLD}Tuỳ chọn thao tác:{RESET}")
    print(f"- {GREEN}1 - {len(displayed)}{RESET} hoặc {GREEN}[Enter]{RESET}    : Tiếp tục phiên [1]")
    print(f"- {YELLOW}rn <số>{RESET} (ví dụ: {YELLOW}rn 1{RESET})   : ✏️ Đổi tên dự án, phiên bản & tiêu đề")
    print(f"- {CYAN}v <số>{RESET} (ví dụ: {CYAN}v 1{RESET})    : Xem chi tiết câu hỏi & lịch sử phiên")
    print(f"- {MAGENTA}b <số>{RESET} (ví dụ: {MAGENTA}b 1{RESET})    : Tạo phân nhánh mới (Branch/Fork)")
    print(f"- {BLUE}<từ khóa>{RESET}             : Tìm kiếm (tên dự án, phiên bản, tiêu đề, git, nội dung...)")
    print(f"- {MAGENTA}all{RESET}                      : Xem toàn bộ {len(sessions)} phiên làm việc")
    print(f"- {MAGENTA}g{RESET}                        : Mở giao diện đồ họa GUI (Session Manager)")
    print(f"- {YELLOW}q{RESET}                        : Thoát\n")

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
            if run_gui_app(sessions):
                break
        elif choice.lower() in ["all", "tatca", "tat ca"]:
            print_banner()
            print(f"{GREEN}Toàn bộ {len(sessions)} phiên làm việc trong hệ thống:{RESET}\n")
            display_sessions(sessions)
            displayed = sessions
        elif choice.lower().startswith("rn ") or choice.lower() == "rn" or choice.lower().startswith("rename"):
            parts = choice.split()
            target_idx = 1
            if len(parts) > 1 and parts[1].isdigit():
                target_idx = int(parts[1])
            if 1 <= target_idx <= len(displayed):
                cli_rename_session(displayed[target_idx - 1])
                # Cập nhật danh sách hiển thị
                sessions = scan_sessions(limit=None)
                displayed = sessions[:15]
            else:
                print(f"{YELLOW}Số thứ tự không hợp lệ.{RESET}")
        elif choice.lower().startswith("v ") or choice.lower() == "v":
            parts = choice.split()
            target_idx = 1
            if len(parts) > 1 and parts[1].isdigit():
                target_idx = int(parts[1])
            if 1 <= target_idx <= len(displayed):
                view_conversation(displayed[target_idx - 1])
                break
            else:
                print(f"{YELLOW}Số thứ tự không hợp lệ.{RESET}")
        elif choice.lower().startswith("b ") or choice.lower() == "b":
            parts = choice.split()
            target_idx = 1
            if len(parts) > 1 and parts[1].isdigit():
                target_idx = int(parts[1])
            if 1 <= target_idx <= len(displayed):
                branch_conversation(displayed[target_idx - 1])
                break
            else:
                print(f"{YELLOW}Số thứ tự không hợp lệ.{RESET}")
        elif choice.isdigit():
            val = int(choice)
            if 1 <= val <= len(displayed):
                resume_session(displayed[val - 1])
                break
            else:
                print(f"{YELLOW}Vui lòng nhập số từ 1 đến {len(displayed)}.{RESET}")
        else:
            q = choice.lower()
            results = [
                s for s in sessions 
                if q in s['project_name'].lower() 
                or q in s.get('version', '').lower()
                or q in s['title'].lower() 
                or q in s['last_prompt'].lower() 
                or q in s['first_prompt'].lower()
                or q in s['cwd'].lower()
                or q in s['id'].lower()
                or q in s.get('git_repo_str', '').lower()
                or q in s.get('last_assistant', '').lower()
            ]
            if results:
                print(f"\n{GREEN}--- Tìm thấy {len(results)} phiên phù hợp với '{choice}' ---{RESET}")
                display_sessions(results)
                displayed = results
            else:
                print(f"{YELLOW}Không tìm thấy kết quả nào cho '{choice}'. Hãy thử từ khóa khác hoặc nhập số.{RESET}")

if __name__ == "__main__":
    main()
