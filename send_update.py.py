import os
import subprocess
import requests
from bs4 import BeautifulSoup

# --- הגדרות ---
# כאן אתה מגדיר את מספר הנושא שלך בפורום
TOPIC_ID = "12345" 
FORUM_URL = "https://forum.otzaria.org"

def get_changed_books():
    """פונקציה ששולפת את רשימת הקבצים שהשתנו מגיט"""
    before_sha = os.environ.get("BEFORE_SHA")
    after_sha = os.environ.get("AFTER_SHA")
    
    if not before_sha or not after_sha or before_sha == "0000000000000000000000000000000000000000":
        # אם זה פוש ראשון או חסר מידע, ניקח רק את הקומיט האחרון
        git_cmd = ["git", "diff", "--name-status", "HEAD~1", "HEAD"]
    else:
        git_cmd = ["git", "diff", "--name-status", before_sha, after_sha]
        
    try:
        output = subprocess.check_output(git_cmd, text=True)
    except subprocess.CalledProcessError:
        return "לא הצלחתי לשלוף את רשימת השינויים המדויקת מגיט."

    added = []
    modified = []
    
    # מעבר על הפלט של גיט (שנראה למשל ככה: "A  ספרים/בראשית.txt")
    for line in output.strip().split('\n'):
        if not line: continue
        parts = line.split(maxsplit=1)
        if len(parts) < 2: continue
        
        status, filepath = parts[0], parts[1]
        
        # אנחנו רוצים רק מה שבתוך תיקיית "ספרים"
        if not filepath.startswith("ספרים/"):
            continue
            
        book_name = os.path.basename(filepath)
        
        if status.startswith('A'):
            added.append(book_name)
        elif status.startswith('M'):
            modified.append(book_name)
            
    # בניית הטקסט
    msg = ""
    if added:
        msg += "**ספרים חדשים שנוספו:**\n" + "\n".join([f"* {b}" for b in added]) + "\n\n"
    if modified:
        msg += "**ספרים שעודכנו:**\n" + "\n".join([f"* {b}" for b in modified]) + "\n\n"
        
    return msg if msg else "בוצעו עדכונים טכניים במאגר (לא נמצאו שינויים ישירים בספרים)."

def post_to_discourse(message):
    username = os.environ.get("USER_NAME")
    password = os.environ.get("PASSWORD")
    
    if not username or not password:
        print("שגיאה: חסרים שם משתמש או סיסמה.")
        return

    # פתיחת סשן - כדי לשמור על העוגיות (Cookies) של ההתחברות
    session = requests.Session()
    
    try:
        print("1. מושך את עמוד הבית כדי לקבל CSRF Token...")
        home_req = session.get(FORUM_URL)
        soup = BeautifulSoup(home_req.text, 'html.parser')
        
        # שליפת האסימון החבוי בתוך ה-HTML
        csrf_token = soup.find('meta', {'name': 'csrf-token'})['content']
        
        headers = {
            'X-CSRF-Token': csrf_token,
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        print("2. מבצע התחברות לפורום...")
        login_data = {
            'login': username,
            'password': password
        }
        login_req = session.post(f"{FORUM_URL}/session", data=login_data, headers=headers)
        
        if login_req.status_code != 200:
            print("שגיאת התחברות! ודא ששם המשתמש והסיסמה נכונים.")
            return
            
        print("3. התחברות הצליחה. שולח את התגובה...")
        post_data = {
            'topic_id': TOPIC_ID,
            'raw': message
        }
        post_req = session.post(f"{FORUM_URL}/posts", data=post_data, headers=headers)
        
        if post_req.status_code == 200:
            print("ההודעה פורסמה בהצלחה!")
        else:
            print(f"שגיאה בפרסום ההודעה: {post_req.text}")
            
    except Exception as e:
        print(f"התרחשה שגיאה במהלך התקשורת עם הפורום: {e}")

if __name__ == "__main__":
    tag = os.environ.get("TAG", "גרסה חדשה")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    
    changes_text = get_changed_books()
    
    final_post = f"🎉 **עדכון חדש במאגר הספרים!** (`{tag}`)\n\n"
    final_post += changes_text
    final_post += f"\nניתן להוריד את הקבצים המעודכנים מ-[עמוד ה-Releases](https://github.com/{repo}/releases/latest)."
    
    # אם תרצה שהבוט לא יפרסם כשהוא לא מוצא ספרים ששונו, אפשר לבדוק זאת כאן
    if "לא נמצאו שינויים ישירים בספרים" not in changes_text:
        post_to_discourse(final_post)
    else:
        print("לא פורסם פוסט כי לא זוהו שינויים בקבצי הספרים.")