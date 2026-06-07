import os
import subprocess
import requests
from collections import defaultdict

# --- הגדרות ---
TOPIC_ID = "437" 
FORUM_URL = "https://otzaria.org/forum"

def get_changed_books():
    before_sha = os.environ.get("BEFORE_SHA")
    after_sha = os.environ.get("AFTER_SHA")
    
    if not before_sha or not after_sha or before_sha == "0000000000000000000000000000000000000000":
        git_cmd = ["git", "diff", "--name-status", "HEAD~1", "HEAD"]
    else:
        git_cmd = ["git", "diff", "--name-status", before_sha, after_sha]
        
    try:
        output = subprocess.check_output(git_cmd, text=True)
    except subprocess.CalledProcessError:
        return "לא הצלחתי לשלוף את רשימת השינויים המדויקת מגיט."

    added = defaultdict(list)
    modified = defaultdict(list)
    
    for line in output.strip().split('\n'):
        if not line: continue
        parts = line.split(maxsplit=1)
        if len(parts) < 2: continue
        
        status, filepath = parts[0], parts[1]
        
        if not filepath.startswith("ספרים/"):
            continue
            
        rel_path = filepath[len("ספרים/"):]
        path_parts = rel_path.split('/')
        filename = os.path.splitext(path_parts[-1])[0]
        
        if len(path_parts) == 1:
            folder = "תיקייה ראשית"
        else:
            folder = path_parts[-2]
        
        if status.startswith('A'):
            added[folder].append(filename)
        elif status.startswith('M'):
            modified[folder].append(filename)
            
    msg = ""
    if added:
        msg += "### **נוסף למאגר**\n"
        for folder, books in added.items():
            if folder == "תיקייה ראשית":
                for b in books:
                    msg += f"- {b}\n"
            else:
                msg += f"- {folder}:\n"
                for b in books:
                    msg += f"{b}\n"
            msg += "\n"
            
    if modified:
        msg += "### **עודכן במאגר**\n"
        for folder, books in modified.items():
            if folder == "תיקייה ראשית":
                for b in books:
                    msg += f"- {b}\n"
            else:
                msg += f"- {folder}:\n"
                for b in books:
                    msg += f"{b}\n"
            msg += "\n"
        
    return msg.strip() if msg else "בוצעו עדכונים טכניים במאגר (לא נמצאו שינויים ישירים בספרים)."

def post_to_nodebb(message):
    username = os.environ.get("USER_NAME")
    password = os.environ.get("PASSWORD")
    
    if not username or not password:
        print("שגיאה: חסרים שם משתמש או סיסמה בסודות של גיטאב.")
        return

    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json'
    }
    session.headers.update(headers)
    
    try:
        print(f"1. מתחבר ל-{FORUM_URL} כדי למשוך CSRF Token...")
        config_res = session.get(f"{FORUM_URL}/api/config")
        if config_res.status_code != 200:
            print(f"שגיאה בגישה לשרת ({config_res.status_code})")
            return
            
        csrf_token = config_res.json().get('csrf_token')
        if not csrf_token:
            print("לא נמצא אסימון אבטחה!")
            return
            
        print("2. מבצע לוגין עם השם והסיסמה של הבוט...")
        session.headers.update({'x-csrf-token': csrf_token})
        
        login_data = {
            'username': username,
            'password': password,
            '_csrf': csrf_token
        }
        login_res = session.post(f"{FORUM_URL}/login", data=login_data)
        
        if login_res.status_code != 200:
            print(f"שגיאת התחברות (סטטוס {login_res.status_code}). ודא ששם המשתמש והסיסמה נכונים בהגדרות הסודות.")
            return
            
        print("3. שולח את העדכון לנושא 437...")
        reply_url = f"{FORUM_URL}/api/v3/topics/{TOPIC_ID}"
        reply_data = {"content": message}
        
        post_res = session.post(reply_url, json=reply_data)
        
        if post_res.status_code == 200:
            print("🎉 ההודעה פורסמה בהצלחה בפורום אוצריא!")
        else:
            print(f"שגיאה בעת פרסום ההודעה (סטטוס {post_res.status_code}): {post_res.text}")
            
    except Exception as e:
        print(f"התרחשה שגיאה במהלך התקשורת עם שרת הפורום: {e}")

if __name__ == "__main__":
    tag = os.environ.get("TAG", "גרסה חדשה")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    
    changes_text = get_changed_books()
    
    if "לא נמצאו שינויים ישירים בספרים" not in changes_text:
        final_post = changes_text + '\n\n---\nניתן להוריד באמצעות התוסף "[הורדת מאגרי גיטאב](https://otzaria.org/plugins/6a0081ae54ae49eaed8d6a73)"\n'
        final_post += f'או מ-[עמוד ה-Releases](https://github.com/{repo}/releases/latest).\n\n'
        final_post += '**פוסט זה נכתב ע"י בוט**'
        
        post_to_nodebb(final_post)
    else:
        print("הריצה הסתיימה: לא זוהו שינויים בקבצי הספרים, לכן לא פורסם פוסט בפורום.")
