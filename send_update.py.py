import os
import subprocess
import requests
from bs4 import BeautifulSoup
from collections import defaultdict

# --- הגדרות ---
TOPIC_ID = "437"
FORUM_URL = "https://forum.otzaria.org"

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
            
        # מנקה את הקידומת 'ספרים/' כדי לחלץ את שם התיקייה
        rel_path = filepath[len("ספרים/"):]
        path_parts = rel_path.split('/')
        
        # חילוץ שם הקובץ ללא סיומת (למשל מוחק .txt)
        filename = os.path.splitext(path_parts[-1])[0]
        
        if len(path_parts) == 1:
            folder = "תיקייה ראשית"
        else:
            # התיקייה הישירה שבה נמצא הקובץ
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

def post_to_discourse(message):
    username = os.environ.get("USER_NAME")
    password = os.environ.get("PASSWORD")
    
    if not username or not password:
        print("שגיאה: חסרים שם משתמש או סיסמה בסודות של גיטאב.")
        return

    session = requests.Session()
    
    try:
        print("1. מקבל CSRF Token...")
        home_req = session.get(FORUM_URL)
        soup = BeautifulSoup(home_req.text, 'html.parser')
        csrf_token = soup.find('meta', {'name': 'csrf-token'})['content']
        
        headers = {
            'X-CSRF-Token': csrf_token,
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        print("2. מתחבר לפורום...")
        login_data = {'login': username, 'password': password}
        login_req = session.post(f"{FORUM_URL}/session", data=login_data, headers=headers)
        
        if login_req.status_code != 200:
            print("שגיאת התחברות! ודא שהסודות של המשתמש והסיסמה נכונים.")
            return
            
        print("3. מפרסם תגובה בנושא...")
        post_data = {'topic_id': TOPIC_ID, 'raw': message}
        post_req = session.post(f"{FORUM_URL}/posts", data=post_data, headers=headers)
        
        if post_req.status_code == 200:
            print("ההודעה פורסמה בהצלחה!")
        else:
            print(f"שגיאה בפרסום: {post_req.text}")
            
    except Exception as e:
        print(f"שגיאה בתקשורת מול הפורום: {e}")

if __name__ == "__main__":
    tag = os.environ.get("TAG", "גרסה חדשה")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    
    changes_text = get_changed_books()
    
    if "לא נמצאו שינויים ישירים בספרים" not in changes_text:
        final_post = changes_text + f"\n\n---\nניתן להוריד את הקבצים המעודכנים מ-[עמוד ה-Releases](https://github.com/{repo}/releases/latest)."
        post_to_discourse(final_post)
    else:
        print("הריצה הסתיימה: לא זוהו שינויים בקבצי הספרים, לכן לא פורסם פוסט בפורום.")
