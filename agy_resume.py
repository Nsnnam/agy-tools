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

CLI_BASE_DIR = os.path.expandvars(r"%USERPROFILE%\.gemini\antigravity-cli")
BRAIN_DIR = os.path.join(CLI_BASE_DIR, "brain")
CONVERSATIONS_DIR = os.path.join(CLI_BASE_DIR, "conversations")
SUMMARIES_DB_PATH = os.path.join(CLI_BASE_DIR, "conversation_summaries.db")
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
        # Handle ISO strings like 2026-09-04T11:24:20Z or 2026-09-04 18:24:24.123+00:00
        clean_t = t_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_t)
        return dt.astimezone() # convert to local time
    except Exception:
        return None

def format_datetime(dt):
    if not dt:
        return ""
    return dt.strftime("%d/%m/%Y %H:%M:%S")

def format_short_datetime(dt):
    if not dt:
        return ""
    return dt.strftime("%d/%m/%Y %H:%M")

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

def scan_sessions(limit=50):
    if not os.path.exists(BRAIN_DIR):
        return []
    
    summaries_meta = load_summaries_metadata()
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
        
        dir_mtime = datetime.fromtimestamp(os.path.getmtime(d)).astimezone()
        turns = 0
        first_prompt = ""
        first_prompt_time = None
        last_prompt = ""
        last_prompt_time = None
        detected_cwd = ""
        detected_git_repo = ""
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
                        
                        if msg_type == "USER_INPUT":
                            turns += 1
                            content = clean_text(obj.get("content", ""))
                            if content:
                                if not first_prompt:
                                    first_prompt = content
                                    first_prompt_time = step_time
                                last_prompt = content
                                last_prompt_time = step_time
                                
                                # Check git repo in user prompt
                                if not detected_git_repo:
                                    git_match = re.search(r'github\.com/[^/\s]+/([a-zA-Z0-9_\-\.]+?)(?:\.git|\s|$)', content)
                                    if git_match:
                                        repo = git_match.group(1).rstrip(".git")
                                        detected_git_repo = repo
                                
                        elif msg_type == "PLANNER_RESPONSE":
                            txt = clean_text(obj.get("content", ""))
                            if txt:
                                last_assistant_snippet = txt[:150]
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

        # Timestamps
        created_at = first_prompt_time or dir_mtime
        updated_at = last_prompt_time or dir_mtime

        # Extra metadata from summaries db
        meta = summaries_meta.get(cid, {})
        title = meta.get("title") or ""
        parent_id = meta.get("parent_id") or ""
        if not title:
            # Fallback title from first prompt or project
            title = first_prompt[:50] if first_prompt else proj_name

        entries.append({
            "id": cid,
            "title": title,
            "parent_id": parent_id,
            "created_at": created_at,
            "created_at_str": format_datetime(created_at),
            "updated_at": updated_at,
            "updated_at_str": format_datetime(updated_at),
            "turns": turns,
            "project_name": proj_name,
            "cwd": normalize_path(detected_cwd or DEFAULT_PROJECT_DIR),
            "first_prompt": first_prompt,
            "last_prompt": last_prompt,
            "last_assistant": last_assistant_snippet
        })

    return entries

def print_banner():
    print(f"\n{CYAN}{BOLD}======================================================================{RESET}")
    print(f"{CYAN}{BOLD}       ANTIGRAVITY CLI - TIẾP TỤC PHIÊN LÀM VIỆC (AGY-RESUME)         {RESET}")
    print(f"{CYAN}{BOLD}======================================================================{RESET}")

def display_sessions(sessions):
    for idx, s in enumerate(sessions, 1):
        num_str = f"[{idx}]"
        parent_badge = f" {MAGENTA}[Nhánh từ: {s['parent_id'][:8]}]{RESET}" if s['parent_id'] else ""
        print(f"{GREEN}{BOLD}{num_str:<5}{RESET} {YELLOW}{s['updated_at_str']}{RESET} | {CYAN}{BOLD}{s['project_name']}{RESET} ({s['turns']} lượt){parent_badge}")
        print(f"      {BOLD}📌 Tiêu đề :{RESET} {s['title']}")
        print(f"      {DIM}🕒 Tạo lúc :{RESET} {s['created_at_str']} | {DIM}Sửa cuối:{RESET} {s['updated_at_str']}")
        print(f"      {DIM}📁 Thư mục :{RESET} {s['cwd']}")
        
        # Display initial prompt
        fp = s['first_prompt'] or "(Chưa có)"
        if len(fp) > 115:
            fp = fp[:112] + "..."
        print(f"      {BLUE}🌱 Khởi tạo:{RESET} {fp}")
        
        # Display latest prompt
        lp = s['last_prompt'] or "(Chưa có)"
        if len(lp) > 115:
            lp = lp[:112] + "..."
        print(f"      {GREEN}💬 Gần nhất:{RESET} {lp}")
            
        print(f"      {DIM}🆔 ID: {s['id']}{RESET}")
        print(f"{DIM}----------------------------------------------------------------------{RESET}")

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
    print(f"👉 {BOLD}Dự án        :{RESET} {s['project_name']} | 📁 {s['cwd']}")
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
            # Preview response
            resp_preview = t['response']
            if len(resp_preview) > 250:
                resp_preview = resp_preview[:247] + "..."
            print(f"{BLUE}🤖 Tóm tắt trả lời:{RESET}\n   {resp_preview}")
        print(f"{DIM}----------------------------------------------------------------------{RESET}")

    # View options
    print(f"\n{BOLD}Hành động cho phiên này:{RESET}")
    print(f"  {GREEN}[r] Tiếp tục phiên này với agy (Resume){RESET}")
    print(f"  {MAGENTA}[b] Tạo phân nhánh mới từ phiên này (Branch/Fork){RESET}")
    print(f"  {YELLOW}[q] Quay lại danh sách{RESET}\n")

    while True:
        try:
            act = input(f"{BOLD}👉 Chọn hành động [r/b/q]: {RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return

        if act in ["r", "resume", "1"]:
            resume_session(s)
            break
        elif act in ["b", "branch", "2"]:
            branch_conversation(s)
            break
        elif act in ["q", "quit", "exit", ""]:
            break

def branch_conversation(session):
    old_cid = session["id"]
    new_cid = str(uuid.uuid4())
    old_title = session.get("title") or session.get("project_name") or "Phiên làm việc"

    print(f"\n{MAGENTA}{BOLD}======================================================================{RESET}")
    print(f"{MAGENTA}{BOLD}       TẠO PHÂN NHÁNH CUỘC TRÒ CHUYỆN (CONVERSATION BRANCH)           {RESET}")
    print(f"{MAGENTA}{BOLD}======================================================================{RESET}")
    print(f"👉 {BOLD}Phiên gốc    :{RESET} {old_title}")
    print(f"👉 {BOLD}ID gốc       :{RESET} {old_cid}")
    print(f"👉 {BOLD}Nhánh mới ID :{RESET} {GREEN}{new_cid}{RESET}")

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
            print(f"{YELLOW}Cảnh báo khi nhân bản database: {e}{RESET}")

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
            print(f"{YELLOW}Cảnh báo khi sao chép brain: {e}{RESET}")

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
            print(f"{YELLOW}Cảnh báo khi cập nhật summaries: {e}{RESET}")

    print(f"\n{GREEN}{BOLD}✅ Tạo phân nhánh thành công!{RESET}")
    print(f"🌱 {BOLD}Nhánh mới:{RESET} {branch_title}")
    print(f"🆔 {BOLD}ID mới   :{RESET} {new_cid}")
    print(f"🛡️ {BOLD}Bảo toàn :{RESET} Cuộc trò chuyện gốc ({old_cid}) được giữ nguyên 100%.")
    print(f"🧠 {BOLD}Bộ nhớ   :{RESET} Toàn bộ ngữ cảnh, câu hỏi, file và công việc trước đó đã được nhân bản sang nhánh mới.")

    # Ask to launch immediately
    new_session = dict(session)
    new_session["id"] = new_cid
    new_session["title"] = branch_title
    new_session["parent_id"] = old_cid

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
    print(f"👉 {BOLD}Tiêu đề:{RESET} {title}")
    print(f"👉 {BOLD}Dự án  :{RESET} {proj}")
    print(f"👉 {BOLD}Thư mục:{RESET} {cwd}")
    print(f"👉 {BOLD}ID     :{RESET} {cid}")
    if session.get("parent_id"):
        print(f"👉 {BOLD}Nhánh từ:{RESET} {session['parent_id']}")
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
            "TieuDe": s.get('title') or s.get('project_name'),
            "DuAn": s['project_name'],
            "NgayTao": s['created_at_str'],
            "NgayCapNhat": s['updated_at_str'],
            "SoLuot": s['turns'],
            "YeuCauBanDau": (s['first_prompt'] or "")[:90],
            "YeuCauGanNhat": (s['last_prompt'] or "")[:90],
            "NhanhGoc": s.get('parent_id') or "",
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

def resolve_target_session(sessions, arg):
    arg = arg.strip()
    if arg.isdigit():
        val = int(arg)
        if 1 <= val <= len(sessions):
            return sessions[val - 1]
    for s in sessions:
        if s["id"].lower() == arg.lower() or s["id"].lower().startswith(arg.lower()):
            return s
    return None

def main():
    args = sys.argv[1:]
    sessions = scan_sessions(limit=40)
    
    if not sessions:
        print(f"{YELLOW}Không tìm thấy phiên làm việc nào trong hệ thống.{RESET}")
        return

    # Handle direct arguments
    if args:
        first_arg = args[0].strip().lower()
        
        # Check GUI mode: agyr -g
        if first_arg in ["-g", "--gui"]:
            if run_gui_grid(sessions):
                return
            print(f"{YELLOW}Đã hủy chọn qua GUI.{RESET}")
            return
            
        # Check List only mode: agyr -l
        if first_arg in ["-l", "--list"]:
            print_banner()
            display_sessions(sessions[:15])
            return

        # Check View mode: agyr -v <stt|id>
        if first_arg in ["-v", "--view"]:
            target = None
            if len(args) > 1:
                target = resolve_target_session(sessions, args[1])
            if not target:
                target = sessions[0]
            view_conversation(target)
            return

        # Check Branch mode: agyr -b <stt|id>
        if first_arg in ["-b", "--branch"]:
            target = None
            if len(args) > 1:
                target = resolve_target_session(sessions, args[1])
            if not target:
                target = sessions[0]
            branch_conversation(target)
            return
            
        # Check direct number selection: agyr 1
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
            target = resolve_target_session(sessions, first_arg)
            if target:
                resume_session(target)
            else:
                resume_session({"id": first_arg, "cwd": DEFAULT_PROJECT_DIR, "project_name": "Specified ID"})
            return

        # Check search keyword: agyr <keyword>
        query = " ".join(args).lower()
        matched = [s for s in sessions if query in s['project_name'].lower() or query in s['title'].lower() or query in s['last_prompt'].lower() or query in s['first_prompt'].lower()]
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
    
    print(f"\n{BOLD}Tuỳ chọn thao tác:{RESET}")
    print(f"- {GREEN}1 - {len(displayed)}{RESET} hoặc {GREEN}[Enter]{RESET}    : Tiếp tục phiên [1]")
    print(f"- {CYAN}v <số>{RESET} (ví dụ: {CYAN}v 3{RESET})    : Xem chi tiết câu hỏi & lịch sử phiên")
    print(f"- {MAGENTA}b <số>{RESET} (ví dụ: {MAGENTA}b 3{RESET})    : Tạo phân nhánh mới (Branch/Fork)")
    print(f"- {BLUE}<từ khóa>{RESET}             : Tìm kiếm theo tên dự án, tiêu đề, nội dung")
    print(f"- {MAGENTA}g{RESET}                      : Mở giao diện bảng chọn GUI (Out-GridView)")
    print(f"- {YELLOW}q{RESET}                      : Thoát\n")

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
            results = [s for s in sessions if q in s['project_name'].lower() or q in s['title'].lower() or q in s['last_prompt'].lower() or q in s['first_prompt'].lower()]
            if results:
                print(f"\n{GREEN}--- Kết quả tìm kiếm cho '{choice}' ({len(results)}) ---{RESET}")
                display_sessions(results[:10])
                displayed = results[:10]
            else:
                print(f"{YELLOW}Không tìm thấy kết quả nào cho '{choice}'. Hãy thử từ khóa khác hoặc nhập số.{RESET}")

if __name__ == "__main__":
    main()
