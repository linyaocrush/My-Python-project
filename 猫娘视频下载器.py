import customtkinter as ctk 
import tkinter as tk 
from tkinter import messagebox ,colorchooser ,filedialog 
import os ,json ,threading ,subprocess ,shutil ,urllib .request ,io ,re ,random 
import sqlite3 ,datetime ,webbrowser ,time 
import sys
import traceback
import hashlib
import glob
from collections import Counter
from PIL import Image
from typing import Optional ,List ,Any 
from pydantic import BaseModel ,Field ,field_validator
import pickle
import queue
from concurrent.futures import ThreadPoolExecutor
import logging 

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR ="data"
THEMES_DIR =os .path .join (DATA_DIR ,"themes")
COOKIES_DIR =os .path .join (DATA_DIR ,"cookies")

for d in [DATA_DIR ,THEMES_DIR ,COOKIES_DIR ]:
    try :
        if not os .path .exists (d ):
            os .makedirs (d )
    except Exception as e :
        print (f"Failed to create directory {d}: {e}")

CFG_FILE =os .path .join (DATA_DIR ,"config.json")
DB_FILE =os .path .join (DATA_DIR ,"neko_history.db")
ACTIVE_THEME_FILE =os .path .join (DATA_DIR ,"active_theme.json")

ctk .set_appearance_mode ("Light")
ctk .set_default_color_theme ("blue")

BASE_THEME_TEMPLATE ={
"mode":"Light",
"main_bg":"#FFF0F5",
"panel_bg":"#F8F8F8",
"secondary":"#FFFFFF",
"text":"#333333",
"accent":"#FF69B4",
"btn_add_bg":"#87CEEB",
"btn_add_fg":"#FFFFFF",
"btn_now_bg":"#FFA500",
"btn_now_fg":"#FFFFFF",
"btn_start_bg":"#FF69B4",
"btn_start_fg":"#FFFFFF"
}

DEFAULT_PRESETS ={
"猫娘粉 (Neko Pink)":BASE_THEME_TEMPLATE .copy (),
"深邃夜 (Deep Dark)":{
"mode":"Dark","main_bg":"#1A1A1A","panel_bg":"#232323","secondary":"#2B2B2B","text":"#E0E0E0","accent":"#7B68EE",
"btn_add_bg":"#4682B4","btn_add_fg":"#FFFFFF",
"btn_now_bg":"#CD853F","btn_now_fg":"#FFFFFF",
"btn_start_bg":"#7B68EE","btn_start_fg":"#FFFFFF"
},
"清爽蓝 (Fresh Blue)":{
"mode":"Light","main_bg":"#F0F8FF","panel_bg":"#E6F2FF","secondary":"#FFFFFF","text":"#222222","accent":"#1E90FF",
"btn_add_bg":"#1E90FF","btn_add_fg":"#FFFFFF",
"btn_now_bg":"#32CD32","btn_now_fg":"#FFFFFF",
"btn_start_bg":"#4169E1","btn_start_fg":"#FFFFFF"
}
}

CURRENT_THEME =BASE_THEME_TEMPLATE .copy ()

class ThemeManager :
    def __init__ (self ):
        self .init_defaults ()
        self .load_active_theme ()

    def init_defaults (self ):
        if not os .listdir (THEMES_DIR ):
            for name ,data in DEFAULT_PRESETS .items ():
                self .save_preset (name ,data )

    def get_all_presets (self ):
        files =[f .replace (".json","")for f in os .listdir (THEMES_DIR )if f .endswith (".json")]
        return sorted (files )

    def load_preset (self ,name ):
        path =os .path .join (THEMES_DIR ,f"{name}.json")
        if os .path .exists (path ):
            try :
                with open (path ,"r",encoding ="utf-8")as f :
                    data =json .load (f )
                    temp =BASE_THEME_TEMPLATE .copy ()
                    temp .update (data )
                    return temp 
            except :
                pass 
        return DEFAULT_PRESETS .get (name ,BASE_THEME_TEMPLATE .copy ())

    def save_preset (self ,name ,data ):
        valid_name =re .sub (r'[\\/*?:"<>|]',"",name ).strip ()
        if not valid_name :valid_name ="Untitled_Theme"
        path =os .path .join (THEMES_DIR ,f"{valid_name}.json")
        try :
            with open (path ,"w",encoding ="utf-8")as f :
                json .dump (data ,f ,indent =4 )
            return True 
        except Exception as e :
            print (f"Theme save error: {e}")
            return False 

    def load_active_theme (self ):
        global CURRENT_THEME 
        active_name ="猫娘粉 (Neko Pink)"
        if os .path .exists (ACTIVE_THEME_FILE ):
            try :
                with open (ACTIVE_THEME_FILE ,"r",encoding ="utf-8")as f :
                    cfg =json .load (f )
                    active_name =cfg .get ("active",active_name )
            except :pass 

        CURRENT_THEME =self .load_preset (active_name )
        ctk .set_appearance_mode (CURRENT_THEME ["mode"])
        if CURRENT_THEME ["mode"]=="Dark":
            ctk .set_default_color_theme ("dark-blue")
        else :
            ctk .set_default_color_theme ("blue")

    def set_active_theme_record (self ,name ):
        try :
            with open (ACTIVE_THEME_FILE ,"w",encoding ="utf-8")as f :
                json .dump ({"active":name },f )
        except :pass 

theme_manager =ThemeManager ()

# 缓存管理器
class CacheManager:
    def __init__(self, cache_dir="cache"):
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, "ui_cache.pkl")
        self.code_hash_file = os.path.join(cache_dir, "code_hash.txt")
        
        # 创建缓存目录
        os.makedirs(cache_dir, exist_ok=True)
        
    def get_code_hash(self):
        """获取当前代码的哈希值"""
        try:
            with open(__file__, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"获取代码哈希失败: {e}")
            return None
    
    def is_cache_valid(self):
        """检查缓存是否有效"""
        try:
            if not os.path.exists(self.cache_file) or not os.path.exists(self.code_hash_file):
                return False
            
            with open(self.code_hash_file, 'r') as f:
                cached_hash = f.read().strip()
            
            current_hash = self.get_code_hash()
            return cached_hash == current_hash and current_hash is not None
        except Exception as e:
            logger.error(f"检查缓存有效性失败: {e}")
            return False
    
    def save_cache(self, data):
        """保存缓存"""
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(data, f)
            
            current_hash = self.get_code_hash()
            if current_hash:
                with open(self.code_hash_file, 'w') as f:
                    f.write(current_hash)
            
            logger.info("缓存保存成功")
            return True
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
            return False
    
    def load_cache(self):
        """加载缓存"""
        try:
            if not self.is_cache_valid():
                return None
            
            with open(self.cache_file, 'rb') as f:
                data = pickle.load(f)
            
            logger.info("缓存加载成功")
            return data
        except Exception as e:
            logger.error(f"加载缓存失败: {e}")
            return None
    
    def clear_cache(self):
        """清除缓存"""
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
            if os.path.exists(self.code_hash_file):
                os.remove(self.code_hash_file)
            logger.info("缓存清除成功")
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")

# 启动屏类
class LoadingScreen(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("猫娘视频下载器 - 加载中...")
        self.geometry("400x300")
        self.configure(fg_color="#FFF0F5")
        self.overrideredirect(True)  # 无边框
        
        # 居中显示
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - 400) // 2
        y = (screen_height - 300) // 2
        self.geometry(f"400x300+{x}+{y}")
        
        self.loading_queue = queue.Queue()
        self.is_loading = True
        self.after_ids = []  # 存储所有after回调的ID
        
        # 窗口销毁时的回调
        self.protocol("WM_DELETE_WINDOW", self.close)
        
        self.setup_ui()
        
    def setup_ui(self):
        # 主框架
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(expand=True, fill="both", padx=30, pady=30)
        
        # 标题
        title_label = ctk.CTkLabel(
            main_frame,
            text="🐾 猫娘视频下载器",
            font=("微软雅黑", 24, "bold"),
            text_color="#FF69B4"
        )
        title_label.pack(pady=(20, 10))
        
        # 副标题
        subtitle_label = ctk.CTkLabel(
            main_frame,
            text="正在初始化...",
            font=("微软雅黑", 12),
            text_color="#666666"
        )
        subtitle_label.pack(pady=(0, 30))
        
        # 进度条
        self.progress = ctk.CTkProgressBar(main_frame, width=300, height=8)
        self.progress.pack(pady=(0, 20))
        self.progress.set(0)
        
        # 状态文本
        self.status_label = ctk.CTkLabel(
            main_frame,
            text="正在检查缓存...",
            font=("微软雅黑", 10),
            text_color="#888888"
        )
        self.status_label.pack()
        
        # 动画猫娘
        self.neko_frames = ["🐱", "😸", "😺", "🐈", "😻"]
        self.neko_label = ctk.CTkLabel(
            main_frame,
            text=self.neko_frames[0],
            font=("Arial", 32)
        )
        self.neko_label.pack(pady=(20, 0))
        
        self.animate_neko()
        
    def safe_after(self, ms, func):
        """安全的after方法，记录回调ID"""
        try:
            if self and self.winfo_exists():
                after_id = self.after(ms, func)
                self.after_ids.append(after_id)
                return after_id
        except Exception as e:
            logger.error(f"safe_after错误: {e}")
        return None
    
    def cancel_all_after(self):
        """取消所有after回调"""
        try:
            for after_id in self.after_ids:
                if self and self.winfo_exists():
                    self.after_cancel(after_id)
            self.after_ids.clear()
        except Exception as e:
            logger.error(f"取消after回调错误: {e}")
    
    def animate_neko(self):
        try:
            if not self.is_loading or not self or not self.winfo_exists():
                return
            
            current_frame = self.neko_frames[0]
            self.neko_frames = self.neko_frames[1:] + [current_frame]
            self.neko_label.configure(text=current_frame)
            self.safe_after(500, self.animate_neko)
        except Exception as e:
            logger.error(f"动画执行错误: {e}")
    
    def update_progress(self, value, status=""):
        try:
            if self.is_loading and self and self.winfo_exists():
                self.loading_queue.put((value, status))
        except Exception as e:
            logger.error(f"更新进度错误: {e}")
        
    def process_updates(self):
        try:
            if not self.is_loading or not self or not self.winfo_exists():
                return
            
            try:
                while True:
                    value, status = self.loading_queue.get_nowait()
                    self.progress.set(value)
                    if status:
                        self.status_label.configure(text=status)
            except queue.Empty:
                pass
            
            if self.is_loading and self and self.winfo_exists():
                self.safe_after(100, self.process_updates)
        except Exception as e:
            logger.error(f"处理更新错误: {e}")
    
    def close(self):
        """安全关闭：停止动画并退出循环"""
        self.is_loading = False
        try:
            # 1. 停止所有 CustomTkinter 的后台定时任务
            self.cancel_all_after() # 确保取消所有定时器
            self.withdraw() # 先隐藏窗口，防止用户再次操作
            
            # 2. 强力销毁 Tcl 解释器
            self.quit()
            self.destroy()
            
            # 3. 给系统一点点时间（0.1秒）彻底清理内存
            import time
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"彻底关闭加载屏时发生意外: {e}")

FONT_N =("微软雅黑",12 )
FONT_B =("微软雅黑",12 ,"bold")
FONT_T =("微软雅黑",24 ,"bold")
FONT_S =("微软雅黑",10 )
FONT_LOG =("Consolas",14 )
FONT_Q_TITLE =("微软雅黑",13 ,"bold")
FONT_Q_DESC =("微软雅黑",12 )

def safe_run (func ):
    def wrapper (*args ,**kwargs ):
        try :
            return func (*args ,**kwargs )
        except Exception as e :
            self_obj =args [0 ]if args else None 
            func_name =func .__name__ 
            print (f"❌ Error inside [{func_name}]: {e}")
            print (traceback .format_exc ())
            if self_obj and hasattr (self_obj ,'log'):
                err_msg =str (e )
                self_obj .log (f"💥 崩溃拦截 [{func_name}]: {err_msg[:60]}...","sad")
            return False 
    return wrapper 

class HistoryRecord (BaseModel ):
    id :int 
    title :str ="Unknown Title"
    uploader :str ="Unknown Uploader"
    uploader_url :Optional [str ]=""
    webpage_url :Optional [str ]=""
    file_size :int =0 
    download_date :str 
    duration :int =0 
    elapsed_seconds :float =0.0 

    @field_validator ('title','uploader',mode ='before')
    @classmethod 
    def handle_none_strings (cls ,v ):return v if v is not None else "Unknown"

    @field_validator ('file_size','duration',mode ='before')
    @classmethod 
    def handle_none_ints (cls ,v ):return v if v is not None else 0 

    @field_validator ('elapsed_seconds',mode ='before')
    @classmethod 
    def handle_none_floats (cls ,v ):return v if v is not None else 0.0 

    @property 
    def size_mb (self )->float :return self .file_size /(1024 *1024 )

    @property 
    def speed_mb_s (self )->float :
        return (self .size_mb /self .elapsed_seconds )if self .elapsed_seconds >0 else 0.0 

def show_windows_toast (title ,msg ):
    def _run ():
        ps_script =f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode('{title}')) > $null
        $textNodes.Item(1).AppendChild($template.CreateTextNode('{msg}')) > $null
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Neko Downloader")
        $notification = [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime]::new($template)
        $notifier.Show($notification)
        """
        try :subprocess .run (["powershell","-Command",ps_script ],capture_output =True ,creationflags =subprocess .CREATE_NO_WINDOW if os .name =='nt'else 0 )
        except :pass 
    threading .Thread (target =_run ,daemon =True ).start ()

class NekoDB :
    def __init__ (self ):
        self .conn =sqlite3 .connect (DB_FILE ,check_same_thread =False )
        self .cursor =self .conn .cursor ()
        self .lock =threading .Lock ()
        self .init_table ()
        self .upgrade_table ()
        self .upgrade_resume_support ()

    def init_table (self ):
        self .cursor .execute ('''
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                uploader TEXT,
                uploader_url TEXT,
                webpage_url TEXT,
                file_size INTEGER,
                download_date TIMESTAMP,
                duration INTEGER DEFAULT 0,
                elapsed_seconds REAL DEFAULT 0
            )
        ''')
        self .cursor .execute ('CREATE INDEX IF NOT EXISTS idx_uploader ON downloads (uploader)')
        self .cursor .execute ('CREATE INDEX IF NOT EXISTS idx_date ON downloads (download_date)')
        self .cursor .execute ('CREATE INDEX IF NOT EXISTS idx_url ON downloads (webpage_url)')
        self .cursor .execute ('''
            CREATE VIEW IF NOT EXISTS stats_view AS
            SELECT 
                COUNT(*) as total_count,
                SUM(file_size) as total_size,
                date(download_date) as d,
                strftime('%H', download_date) as hour,
                CASE 
                    WHEN duration < 300 THEN 'short'
                    WHEN duration < 1800 THEN 'medium'
                    ELSE 'long'
                END as dur_type
            FROM downloads
            GROUP BY d, hour, dur_type
        ''')
        self .conn .commit ()

    def upgrade_table (self ):
        try :self .cursor .execute ("ALTER TABLE downloads ADD COLUMN duration INTEGER DEFAULT 0")
        except :pass 
        try :self .cursor .execute ("ALTER TABLE downloads ADD COLUMN elapsed_seconds REAL DEFAULT 0")
        except :pass 
        self .cursor .execute ('CREATE INDEX IF NOT EXISTS idx_uploader ON downloads (uploader)')
        self .cursor .execute ('CREATE INDEX IF NOT EXISTS idx_date ON downloads (download_date)')
        self .cursor .execute ('CREATE INDEX IF NOT EXISTS idx_url ON downloads (webpage_url)')
        self .conn .commit ()

    def upgrade_resume_support (self ):
        try :self .cursor .execute ("ALTER TABLE downloads ADD COLUMN download_status TEXT DEFAULT 'pending'")
        except :pass 
        try :self .cursor .execute ("ALTER TABLE downloads ADD COLUMN progress_percentage REAL DEFAULT 0.0")
        except :pass 
        try :self .cursor .execute ("ALTER TABLE downloads ADD COLUMN downloaded_bytes INTEGER DEFAULT 0")
        except :pass 
        try :self .cursor .execute ("ALTER TABLE downloads ADD COLUMN total_bytes INTEGER DEFAULT 0")
        except :pass 
        try :self .cursor .execute ("ALTER TABLE downloads ADD COLUMN temp_file_path TEXT")
        except :pass 
        try :self .cursor .execute ("ALTER TABLE downloads ADD COLUMN session_id TEXT")
        except :pass 

        self .cursor .execute ("""
            CREATE TABLE IF NOT EXISTS resume_sessions (
                session_id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                output_path TEXT NOT NULL,
                temp_file TEXT NOT NULL,
                downloaded_bytes INTEGER DEFAULT 0,
                total_bytes INTEGER DEFAULT 0,
                last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                download_params TEXT,
                status TEXT DEFAULT 'active',
                title TEXT DEFAULT 'Unknown'
            )
        """)
        self .cursor .execute ('CREATE INDEX IF NOT EXISTS idx_session_status ON resume_sessions (status)')
        self .cursor .execute ('CREATE INDEX IF NOT EXISTS idx_session_update ON resume_sessions (last_update)')
        self .conn .commit ()

    def save_resume_session (self ,session_id ,url ,output_path ,temp_file ,downloaded_bytes ,total_bytes ,download_params ,title ):
        with self .lock :
            self .cursor .execute ("""
                INSERT OR REPLACE INTO resume_sessions 
                (session_id, url, output_path, temp_file, downloaded_bytes, total_bytes, download_params, title, last_update)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,(session_id ,url ,output_path ,temp_file ,downloaded_bytes ,total_bytes ,json .dumps (download_params ),title ,datetime .datetime .now ().strftime ("%Y-%m-%d %H:%M:%S")))
            self .conn .commit ()

    def get_pending_resume_sessions (self ):
        self .cursor .execute ("SELECT * FROM resume_sessions WHERE status = 'active' ORDER BY last_update DESC")
        return self .cursor .fetchall ()

    def complete_resume_session (self ,session_id ):
        with self .lock :
            self .cursor .execute ("DELETE FROM resume_sessions WHERE session_id = ?",(session_id ,))
            self .conn .commit ()

    def add_record (self ,meta ,size_bytes ,elapsed ):
        with self .lock :
            try :
                now =datetime .datetime .now ().strftime ("%Y-%m-%d %H:%M:%S")
                duration =meta .get ('duration',0 )or 0 
                self .cursor .execute ('''
                    INSERT INTO downloads (title, uploader, uploader_url, webpage_url, file_size, download_date, duration, elapsed_seconds, download_status, progress_percentage, downloaded_bytes, total_bytes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', 100.0, ?, ?)
                ''',(meta .get ('title','Unknown'),meta .get ('uploader','Unknown'),meta .get ('uploader_url','')or meta .get ('channel_url',''),meta .get ('webpage_url',''),size_bytes ,now ,duration ,elapsed ,size_bytes ,size_bytes ))
                self .conn .commit ()
                return True 
            except Exception as e :
                print (f"DB Error: {e}")
                return False 

    def get_today_count (self ):
        try :
            today =datetime .datetime .now ().strftime ("%Y-%m-%d")
            self .cursor .execute ("SELECT COUNT(*) FROM downloads WHERE date(download_date) = ?",(today ,))
            return self .cursor .fetchone ()[0 ]
        except :return 0 

    def get_full_stats (self ):
        self .cursor .execute ("SELECT file_size, download_date, elapsed_seconds, duration, webpage_url FROM downloads")
        rows =self .cursor .fetchall ()
        stats ={
        "total_count":len (rows ),"total_size":sum (r [0 ]for r in rows if r [0 ]),"total_time":sum (r [2 ]for r in rows if r [2 ]),
        "today_count":0 ,"today_size":0 ,"week_count":0 ,"week_size":0 ,"month_count":0 ,"month_size":0 ,
        "hours":Counter (),"platforms":Counter (),"durations":{"short":0 ,"medium":0 ,"long":0 }
        }
        now =datetime .datetime .now ()
        for r in rows :
            size =r [0 ]or 0 
            dt_str =r [1 ]
            try :dt =datetime .datetime .strptime (dt_str ,"%Y-%m-%d %H:%M:%S")
            except :continue 
            if dt .date ()==now .date ():stats ["today_count"]+=1 ;stats ["today_size"]+=size 
            if (now -dt ).days <7 :stats ["week_count"]+=1 ;stats ["week_size"]+=size 
            if (now -dt ).days <30 :stats ["month_count"]+=1 ;stats ["month_size"]+=size 
            stats ["hours"][dt .hour ]+=1 
            dur =r [3 ]or 0 
            if dur <300 :stats ["durations"]["short"]+=1 
            elif dur <1800 :stats ["durations"]["medium"]+=1 
            else :stats ["durations"]["long"]+=1 
            url =(r [4 ]or "").lower ()
            if "bilibili"in url :stats ["platforms"]["B站"]+=1 
            elif "youtube"in url or "youtu.be"in url :stats ["platforms"]["YouTube"]+=1 
            elif "douyin"in url :stats ["platforms"]["抖音"]+=1 
            elif "tiktok"in url :stats ["platforms"]["TikTok"]+=1 
            elif "twitter"in url or "x.com"in url :stats ["platforms"]["推特(X)"]+=1 
            else :stats ["platforms"]["其他"]+=1 
        return stats 

    def get_top_uploaders (self ,limit =5 ):
        self .cursor .execute ('SELECT uploader, COUNT(*) as count FROM downloads GROUP BY uploader ORDER BY count DESC LIMIT ?',(limit ,))
        return self .cursor .fetchall ()

    def get_all_uploaders (self ):
        self .cursor .execute ("SELECT DISTINCT uploader FROM downloads ORDER BY uploader")
        return [r [0 ]for r in self .cursor .fetchall ()if r [0 ]]

    def search_history (self ,keyword ="",uploader_filter ="全部",platform_filter ="全部",limit =50 )->List [HistoryRecord ]:
        sql ="SELECT * FROM downloads WHERE 1=1"
        params =[]
        if keyword :sql +=" AND title LIKE ?";params .append (f"%{keyword}%")
        if uploader_filter and uploader_filter !="全部":sql +=" AND uploader = ?";params .append (uploader_filter )
        if platform_filter and platform_filter !="全部":
            if platform_filter =="B站 (Bilibili)":sql +=" AND webpage_url LIKE '%bilibili%'"
            elif platform_filter =="油管 (YouTube)":sql +=" AND (webpage_url LIKE '%youtube%' OR webpage_url LIKE '%youtu.be%')"
            elif platform_filter =="抖音 (Douyin)":sql +=" AND webpage_url LIKE '%douyin%'"
            elif platform_filter =="推特 (X)":sql +=" AND (webpage_url LIKE '%twitter%' OR webpage_url LIKE '%x.com%')"
        sql +=" ORDER BY download_date DESC LIMIT ?"
        params .append (limit )
        self .cursor .execute (sql ,tuple (params ))
        rows =self .cursor .fetchall ()
        records =[]
        for r in rows :
            try :records .append (HistoryRecord (id =r [0 ],title =r [1 ],uploader =r [2 ],uploader_url =r [3 ],webpage_url =r [4 ],file_size =r [5 ],download_date =r [6 ],duration =r [7 ],elapsed_seconds =r [8 ]))
            except Exception as e :print (f"Data conversion error for row {r[0]}: {e}")
        return records 

class NekoMoodManager :
    def __init__ (self ,db ):
        self .db =db 
        self .mood ="normal"
        self .last_interaction =time .time ()
        self .download_success_today =0 
        self .greetings ={
        "normal":[
        "主人喵~ 今天想抓哪只视频小老鼠？","喵~ 随时待命！","尾巴摇摇~ 等待指令喵。",
        "只要是Master想要的，我都会努力去抓！","今天天气真好，适合抓老鼠（视频）~"
        ],
        "happy":[
        "哇！今天收获不错呢！","主人最棒了喵！再多喂我一点链接嘛~","呼噜呼噜... 开心~",
        "这种感觉... 是丰收的喜悦喵！"
        ],
        "excited":[
        "哇呜！主人手速超快喵！🔥","停不下来了喵！还有吗还有吗？",
        "今天是大丰收！Master 最强！💖","猫娘的引擎正在全速运转！"
        ],
        "lonely":[
        "...好安静... 主人还在吗喵？","呜呜... 只有我一只猫在这里...",
        "尾巴都不摇了... 理理我嘛...","Master 是不是去别的猫那里了..."
        ],
        "sleepy":[
        "哈欠... 熬夜会掉毛的哦...","Master，该睡觉了喵... zzz",
        "虽然很困，但为了 Master 还能坚持一下...","月亮都睡了喵..."
        ],
        "sad":[
        "呜... 刚才那个没抓到...","对不起 Master，我搞砸了...",
        "别生气... 我下次会更努力的...","心情低落... 需要摸摸头..."
        ]
        }
        self .update_counts_from_db ()

    def update_counts_from_db (self ):
        try :
            self .download_success_today =self .db .get_today_count ()
        except :pass 

    def interact (self ):
        self .last_interaction =time .time ()
        if self .mood =="lonely"or self .mood =="sleepy":
            self .mood ="normal"
            self .update_logic ()

    def report_success (self ):
        self .interact ()
        self .download_success_today +=1 
        self .mood ="happy"
        self .update_logic ()

    def report_fail (self ):
        self .interact ()
        self .mood ="sad"

    def update_logic (self ):
        now =time .time ()
        idle =now -self .last_interaction 
        hour =datetime .datetime .now ().hour 
        if self .mood =="sad"and idle <10 :return 
        if (hour >=23 or hour <6 )and idle >60 :
            self .mood ="sleepy"
            return 
        if idle >300 :
            self .mood ="lonely"
            return 
        if self .download_success_today >=10 :
            self .mood ="excited"
        elif self .download_success_today >=3 :
            self .mood ="happy"
        else :
            self .mood ="normal"

    def get_greeting (self ):
        self .update_logic ()
        msgs =self .greetings .get (self .mood ,self .greetings ["normal"])
        return f"[{self.mood.upper()}] {random.choice(msgs)}"

class ResumeManagerWindow (ctk .CTkToplevel ):
    def __init__ (self ,parent ,db ):
        super ().__init__ (parent )
        self .title ("🔄 续传管理")
        self .geometry ("800x600")
        self .db =db 
        self .transient (parent )
        self .grab_set ()
        self .configure (fg_color =CURRENT_THEME ["main_bg"])
        self .parent =parent 
        self .setup_ui ()
        self .load_pending_sessions ()

    def setup_ui (self ):
        title_frame =ctk .CTkFrame (self ,fg_color ="transparent")
        title_frame .pack (fill ="x",padx =20 ,pady =15 )
        ctk .CTkLabel (title_frame ,text ="🔄 断点续传管理",font =FONT_T ,text_color =CURRENT_THEME ["accent"]).pack ()
        control_frame =ctk .CTkFrame (self ,fg_color ="transparent")
        control_frame .pack (fill ="x",padx =20 ,pady =10 )
        ctk .CTkButton (control_frame ,text ="🔄 全部续传",width =120 ,fg_color ="#4CAF50",command =self .resume_all ).pack (side ="left",padx =(0 ,10 ))
        ctk .CTkButton (control_frame ,text ="🗑️ 清理失效",width =120 ,fg_color ="#FF9800",command =self .clean_invalid_sessions ).pack (side ="left",padx =5 )
        ctk .CTkButton (control_frame ,text ="❌ 全部删除",width =120 ,fg_color ="#F44336",command =self .delete_all ).pack (side ="left",padx =5 )
        self .scroll_frame =ctk .CTkScrollableFrame (self ,fg_color =CURRENT_THEME ["panel_bg"])
        self .scroll_frame .pack (fill ="both",expand =True ,padx =20 ,pady =10 )

    def load_pending_sessions (self ):
        for widget in self .scroll_frame .winfo_children ():widget .destroy ()
        sessions =self .db .get_pending_resume_sessions ()
        if not sessions :
            ctk .CTkLabel (self .scroll_frame ,text ="✨ 没有待续传的任务",font =FONT_N ,text_color =CURRENT_THEME ["text"]).pack (pady =20 )
            return 
        for session in sessions :self .create_session_item (session )

    def create_session_item (self ,session ):
        item_frame =ctk .CTkFrame (self .scroll_frame ,fg_color =CURRENT_THEME ["secondary"],corner_radius =10 )
        item_frame .pack (fill ="x",pady =5 ,padx =5 )
        info_frame =ctk .CTkFrame (item_frame ,fg_color ="transparent")
        info_frame .pack (side ="left",fill ="both",expand =True ,padx =10 ,pady =8 )
        title_text =session [9 ]if len (session )>9 and session [9 ]else session [1 ]
        if len (title_text )>60 :title_text =title_text [:60 ]+"..."
        url_label =ctk .CTkLabel (info_frame ,text =title_text ,font =FONT_B ,text_color =CURRENT_THEME ["text"],anchor ="w")
        url_label .pack (fill ="x")
        downloaded =session [4 ]if session [4 ]else 0 
        total =session [5 ]if session [5 ]else 0 
        progress =(downloaded /total *100 )if total >0 else 0 
        progress_text =f"进度: {downloaded//1024//1024}MB / {total//1024//1024}MB ({progress:.1f}%)"
        if session [6 ]:progress_text +=f" | 最后更新: {session[6][:16]}"
        progress_label =ctk .CTkLabel (info_frame ,text =progress_text ,font =FONT_S ,text_color ="gray",anchor ="w")
        progress_label .pack (fill ="x")
        progress_bar =ctk .CTkProgressBar (info_frame ,progress_color =CURRENT_THEME ["accent"],height =8 )
        progress_bar .pack (fill ="x",pady =(5 ,0 ))
        progress_bar .set (progress /100 )
        button_frame =ctk .CTkFrame (item_frame ,fg_color ="transparent")
        button_frame .pack (side ="right",padx =10 ,pady =8 )
        ctk .CTkButton (button_frame ,text ="▶️ 续传",width =80 ,height =30 ,fg_color ="#4CAF50",command =lambda s =session :self .resume_session (s )).pack (pady =2 )
        ctk .CTkButton (button_frame ,text ="❌ 删除",width =80 ,height =30 ,fg_color ="#F44336",command =lambda s =session :self .delete_session (s )).pack (pady =2 )

    def resume_session (self ,session ):
        try :
            download_params =json .loads (session [7 ])if session [7 ]else {}
            if not os .path .exists (session [3 ]):
                pass 
            threading .Thread (target =self .parent .start_resume_download ,args =(session ,download_params ),daemon =True ).start ()
            self .destroy ()
        except Exception as e :messagebox .showerror ("续传失败",f"续传失败: {str(e)}")

    def delete_session (self ,session ):
        if messagebox .askyesno ("确认删除","确定要删除这个续传会话吗？"):
            try :
                if os .path .exists (session [3 ]):os .remove (session [3 ])
                self .db .cursor .execute ("DELETE FROM resume_sessions WHERE session_id = ?",(session [0 ],))
                self .db .conn .commit ()
                self .load_pending_sessions ()
            except Exception as e :messagebox .showerror ("删除失败",f"删除失败: {str(e)}")

    def resume_all (self ):
        sessions =self .db .get_pending_resume_sessions ()
        for session in sessions :self .resume_session (session )

    def clean_invalid_sessions (self ):
        sessions =self .db .get_pending_resume_sessions ()
        cleaned =0 
        for session in sessions :
            if not os .path .exists (session [3 ]):
                self .db .cursor .execute ("DELETE FROM resume_sessions WHERE session_id = ?",(session [0 ],))
                cleaned +=1 
        self .db .conn .commit ()
        if cleaned >0 :messagebox .showinfo ("清理完成",f"已清理 {cleaned} 个失效会话");self .load_pending_sessions ()
        else :messagebox .showinfo ("清理完成","没有发现失效会话")

    def delete_all (self ):
        if messagebox .askyesno ("确认删除","确定要删除所有续传会话吗？这将删除所有临时下载文件。"):
            sessions =self .db .get_pending_resume_sessions ()
            for session in sessions :
                try :
                    if os .path .exists (session [3 ]):os .remove (session [3 ])
                except :pass 
            self .db .cursor .execute ("DELETE FROM resume_sessions")
            self .db .conn .commit ()
            self .load_pending_sessions ()

class ThemeEditorWindow (ctk .CTkToplevel ):
    def __init__ (self ,parent ):
        super ().__init__ (parent )
        self .title ("🎨 魔法调色板 (Theme Editor)")
        self .geometry ("550x750")
        self .transient (parent )
        self .grab_set ()
        self .configure (fg_color =CURRENT_THEME ["main_bg"])
        # 强制让 Toplevel 窗口先在系统中注册
        self.after(10, self._create_widgets)
    
    def _create_widgets(self):
        # 把原本 __init__ 里的组件创建代码挪到这里
        # 这样可以确保 parent 窗口已经完全稳定
        self .presets =theme_manager .get_all_presets ()
        self .active_name ="猫娘粉 (Neko Pink)"
        for name in self .presets :
            if theme_manager .load_preset (name )==CURRENT_THEME :
                self .active_name =name 
                break 
        top_f =ctk .CTkFrame (self ,fg_color ="transparent");top_f .pack (fill ="x",padx =20 ,pady =15 )
        ctk .CTkLabel (top_f ,text ="选择主题:",font =FONT_B ,text_color =CURRENT_THEME ["text"]).pack (side ="left")
        self .c_theme =ctk .CTkComboBox (top_f ,values =self .presets ,width =220 ,font =FONT_N ,command =self .on_theme_select ,text_color =CURRENT_THEME ["text"],fg_color =CURRENT_THEME ["panel_bg"]);self .c_theme .pack (side ="left",padx =10 );self .c_theme .set (self .active_name )
        save_f =ctk .CTkFrame (self ,fg_color ="transparent");save_f .pack (fill ="x",padx =20 ,pady =(0 ,10 ))
        ctk .CTkLabel (save_f ,text ="另存为新名:",font =FONT_N ,text_color =CURRENT_THEME ["text"]).pack (side ="left")
        self .e_new_name =ctk .CTkEntry (save_f ,width =200 ,placeholder_text ="输入名字以新建...",text_color =CURRENT_THEME ["text"],fg_color =CURRENT_THEME ["panel_bg"]);self .e_new_name .pack (side ="left",padx =10 )
        self .scroll =ctk .CTkScrollableFrame (self ,fg_color =CURRENT_THEME ["panel_bg"]);self .scroll .pack (fill ="both",expand =True ,padx =20 ,pady =5 )
        ctk .CTkLabel (self .scroll ,text ="--- 🌏 全局基础色 ---",font =FONT_B ,text_color =CURRENT_THEME ["accent"]).pack (pady =5 )
        self .create_color_row ("主题模式 (Mode)","mode_switch")
        self .create_color_row ("主背景色 (Main BG)","main_bg")
        self .create_color_row ("面板背景 (Panel BG)","panel_bg")
        self .create_color_row ("卡片背景 (Card BG)","secondary")
        self .create_color_row ("文字颜色 (Text)","text")
        self .create_color_row ("强调色 (Accent)","accent")
        ctk .CTkLabel (self .scroll ,text ="--- 🔘 核心按钮自定义 ---",font =FONT_B ,text_color =CURRENT_THEME ["accent"]).pack (pady =(15 ,5 ))
        self .create_color_row ("📥 放进篮子 (背景)","btn_add_bg")
        self .create_color_row ("📥 放进篮子 (文字)","btn_add_fg")
        self .create_color_row ("⚡ 立即抓取 (背景)","btn_now_bg")
        self .create_color_row ("⚡ 立即抓取 (文字)","btn_now_fg")
        self .create_color_row ("🚀 叼回窝里 (背景)","btn_start_bg")
        self .create_color_row ("🚀 叼回窝里 (文字)","btn_start_fg")
        self .load_to_editor (self .active_name )
        btn_f =ctk .CTkFrame (self ,fg_color ="transparent");btn_f .pack (pady =20 )
        ctk .CTkButton (btn_f ,text ="💾 保存并重启",fg_color =CURRENT_THEME ["accent"],width =150 ,font =FONT_B ,command =self .save_theme ).pack ()

    def create_color_row (self ,label ,key ):
        row =ctk .CTkFrame (self .scroll ,fg_color ="transparent");row .pack (fill ="x",padx =5 ,pady =4 )
        ctk .CTkLabel (row ,text =label ,font =FONT_N ,width =160 ,anchor ="w",text_color =CURRENT_THEME ["text"]).pack (side ="left")
        if key =="mode_switch":
            self .seg_mode =ctk .CTkSegmentedButton (row ,values =["Light","Dark"],selected_color =CURRENT_THEME ["accent"],text_color =CURRENT_THEME ["text"])
            self .seg_mode .pack (side ="right",fill ="x",expand =True )
        else :
            preview =ctk .CTkLabel (row ,text ="",width =40 ,height =24 ,fg_color ="#FFFFFF",corner_radius =5 );preview .pack (side ="right",padx =5 )
            ctk .CTkButton (row ,text ="🎨",width =40 ,height =24 ,fg_color =CURRENT_THEME ["accent"],command =lambda :self .pick_color (key ,preview )).pack (side ="right")
            setattr (self ,f"preview_{key}",preview );setattr (self ,f"val_{key}","#FFFFFF")

    def load_to_editor (self ,theme_name ):
        data =theme_manager .load_preset (theme_name )
        if hasattr (self ,"seg_mode"):self .seg_mode .set (data .get ("mode","Light"))
        all_keys =[k for k in BASE_THEME_TEMPLATE .keys ()if k !="mode"]
        for key in all_keys :
            if hasattr (self ,f"preview_{key}"):
                color =data .get (key ,"#FFFFFF")
                getattr (self ,f"preview_{key}").configure (fg_color =color )
                setattr (self ,f"val_{key}",color )

    def on_theme_select (self ,choice ):self .e_new_name .delete (0 ,"end");self .load_to_editor (choice )
    def pick_color (self ,key ,preview_widget ):
        curr =getattr (self ,f"val_{key}")
        color =colorchooser .askcolor (initialcolor =curr ,title =f"Color: {key}")
        if color [1 ]:preview_widget .configure (fg_color =color [1 ]);setattr (self ,f"val_{key}",color [1 ])

    def save_theme (self ):
        new_data ={"mode":self .seg_mode .get ()}
        all_keys =[k for k in BASE_THEME_TEMPLATE .keys ()if k !="mode"]
        for k in all_keys :new_data [k ]=getattr (self ,f"val_{k}")
        target_name =self .e_new_name .get ().strip ()
        if not target_name :target_name =self .c_theme .get ()
        if target_name in DEFAULT_PRESETS and target_name ==self .c_theme .get ()and new_data !=DEFAULT_PRESETS [target_name ]:
             if not messagebox .askyesno ("修改内置预设",f"'{target_name}' 是内置预设，修改它将自动保存为新文件。\n是否继续？"):return 
        if theme_manager .save_preset (target_name ,new_data ):
            theme_manager .set_active_theme_record (target_name )
            if messagebox .askyesno ("保存成功",f"主题 '{target_name}' 已保存！\n需要重启生效，立即重启？"):
                python =sys .executable ;os .execl (python ,python ,*sys .argv )
            else :self .destroy ()

class StatsWindow (ctk .CTkToplevel ):
    def __init__ (self ,parent ,db ):
        super ().__init__ (parent );self .title ("📊 喵喵的大数据");self .geometry ("1050x750");self .minsize (900 ,650 );self .db =db ;self .transient (parent )
        self .configure (fg_color =CURRENT_THEME ["main_bg"])
        self .grid_columnconfigure (0 ,weight =1 );self .grid_rowconfigure (1 ,weight =1 )
        title_frame =ctk .CTkFrame (self ,fg_color ="transparent");title_frame .grid (row =0 ,column =0 ,pady =(15 ,5 ))
        ctk .CTkLabel (title_frame ,text ="📅 记忆回廊 & 全域统计",font =("微软雅黑",20 ,"bold"),text_color =CURRENT_THEME ["accent"]).pack ()
        self .tabview =ctk .CTkTabview (self ,segmented_button_selected_color =CURRENT_THEME ["accent"])
        self .tabview .grid (row =1 ,column =0 ,padx =15 ,pady =(0 ,15 ),sticky ="nsew")
        self .tab_stats =self .tabview .add ("📊 详细战报");self .tab_history =self .tabview .add ("📜 历史清单")
        for t in [self .tab_stats ,self .tab_history ]:t .grid_columnconfigure (0 ,weight =1 )
        self .tab_stats .grid_rowconfigure (0 ,weight =1 );self .tab_history .grid_rowconfigure (2 ,weight =1 )
        self .build_stats_tab ();self .build_history_tab ()

    def build_stats_tab (self ):
        data =self .db .get_full_stats ()
        main_frame =ctk .CTkFrame (self .tab_stats ,fg_color ="transparent");main_frame .grid (row =0 ,column =0 ,sticky ="nsew")
        main_frame .grid_columnconfigure (0 ,weight =1 );main_frame .grid_rowconfigure (0 ,weight =1 );main_frame .grid_rowconfigure (1 ,weight =1 );main_frame .grid_rowconfigure (2 ,weight =4 )
        card_frame =ctk .CTkFrame (main_frame ,fg_color ="transparent");card_frame .grid (row =0 ,column =0 ,sticky ="nsew",pady =5 )
        for i in range (4 ):card_frame .grid_columnconfigure (i ,weight =1 )
        t_gb =data ["total_size"]/(1024 **3 );spd =(data ["total_size"]/data ["total_time"]/(1024 **2 ))if data ["total_time"]>0 else 0 ;hrs =data ["total_time"]/3600 
        c_bg =CURRENT_THEME ["panel_bg"]
        self .mk_card (card_frame ,0 ,"📦 总搬运量",f"{t_gb:.2f} GB",c_bg ,"#1E90FF")
        self .mk_card (card_frame ,1 ,"⚡ 平均速度",f"{spd:.1f} MB/s",c_bg ,"#00CB82")
        self .mk_card (card_frame ,2 ,"⏳ 抓老鼠耗时",f"{hrs:.1f} 小时",c_bg ,"#FF8C00")
        self .mk_card (card_frame ,3 ,"🎬 视频总数",f"{data['total_count']} 个",c_bg ,CURRENT_THEME ["accent"])
        p_frame =ctk .CTkFrame (main_frame ,fg_color =CURRENT_THEME ["secondary"],corner_radius =10 )
        p_frame .grid (row =1 ,column =0 ,sticky ="nsew",pady =5 );p_frame .grid_columnconfigure ((0 ,1 ,2 ),weight =1 )
        self .mk_period (p_frame ,0 ,"📅 今日",data ['today_count'],data ['today_size'])
        self .mk_period (p_frame ,1 ,"📅 本周",data ['week_count'],data ['week_size'])
        self .mk_period (p_frame ,2 ,"📅 本月",data ['month_count'],data ['month_size'])
        charts =ctk .CTkFrame (main_frame ,fg_color ="transparent");charts .grid (row =2 ,column =0 ,sticky ="nsew",pady =5 )
        charts .grid_columnconfigure ((0 ,1 ),weight =1 );charts .grid_rowconfigure ((0 ,1 ),weight =1 )
        self .mk_chart_box (charts ,0 ,0 ,"🕒 活跃时段",lambda p :self .draw_bar (p ,data ["hours"]))
        self .mk_chart_box (charts ,0 ,1 ,"🌍 平台分布",lambda p :self .draw_list (p ,data ["platforms"]))
        d_map ={"短 (<5m)":data ["durations"]["short"],"中 (5-30m)":data ["durations"]["medium"],"长 (>30m)":data ["durations"]["long"]}
        self .mk_chart_box (charts ,1 ,0 ,"📏 时长分布",lambda p :self .draw_list (p ,d_map ))
        ranks =self .db .get_top_uploaders ();tup ={n :c for n ,c in ranks }
        self .mk_chart_box (charts ,1 ,1 ,"🏆 Top UP主",lambda p :self .draw_list (p ,tup ))

    def mk_card (self ,p ,c ,t ,v ,bg ,fg ):
        f =ctk .CTkFrame (p ,fg_color =bg ,corner_radius =10 );f .grid (row =0 ,column =c ,sticky ="nsew",padx =3 )
        f .grid_columnconfigure (0 ,weight =1 );f .grid_rowconfigure ((0 ,3 ),weight =1 )
        ctk .CTkLabel (f ,text =t ,font =("微软雅黑",11 ),text_color ="#666").grid (row =1 ,column =0 )
        ctk .CTkLabel (f ,text =v ,font =("Arial",18 ,"bold"),text_color =fg ).grid (row =2 ,column =0 )

    def mk_period (self ,p ,c ,t ,count ,size ):
        f =ctk .CTkFrame (p ,fg_color ="transparent");f .grid (row =0 ,column =c ,sticky ="ns",padx =10 ,pady =5 )
        ctk .CTkLabel (f ,text =t ,font =("微软雅黑",12 ,"bold"),text_color ="gray").pack ()
        ctk .CTkLabel (f ,text =f"{count}个",font =("Arial",18 ,"bold"),text_color =CURRENT_THEME ["accent"]).pack ()
        ctk .CTkLabel (f ,text =f"({size//1048576} MB)",font =("Arial",10 ),text_color ="#888").pack ()

    def mk_chart_box (self ,p ,r ,c ,t ,func ):
        f =ctk .CTkFrame (p ,fg_color =CURRENT_THEME ["secondary"],corner_radius =10 );f .grid (row =r ,column =c ,sticky ="nsew",padx =4 ,pady =4 )
        f .grid_rowconfigure (1 ,weight =1 );f .grid_columnconfigure (0 ,weight =1 )
        ctk .CTkLabel (f ,text =t ,font =("微软雅黑",11 ,"bold"),text_color ="#888",anchor ="w").grid (row =0 ,column =0 ,sticky ="w",padx =10 ,pady =5 )
        c_frame =ctk .CTkFrame (f ,fg_color ="transparent");c_frame .grid (row =1 ,column =0 ,sticky ="nsew",padx =5 ,pady =5 )
        func (c_frame )

    def draw_bar (self ,p ,cnt ):
        periods =[("深夜",range (0 ,6 )),("早晨",range (6 ,12 )),("午后",range (12 ,18 )),("夜晚",range (18 ,24 ))]
        sums =[sum (cnt [h ]for h in rng )for _ ,rng in periods ];mx =max (sums )if sums and max (sums )>0 else 1 
        for i ,(n ,_ )in enumerate (periods ):
            p .grid_rowconfigure (i ,weight =1 );p .grid_columnconfigure (1 ,weight =1 )
            ctk .CTkLabel (p ,text =n ,width =35 ,font =("微软雅黑",10 ),text_color =CURRENT_THEME ["text"],anchor ="w").grid (row =i ,column =0 )
            pb =ctk .CTkProgressBar (p ,height =10 ,progress_color =CURRENT_THEME ["accent"]);pb .grid (row =i ,column =1 ,sticky ="ew",padx =5 );pb .set (sums [i ]/mx )
            ctk .CTkLabel (p ,text =str (sums [i ]),width =25 ,font =("Arial",10 ),text_color =CURRENT_THEME ["text"],anchor ="e").grid (row =i ,column =2 )

    def draw_list (self ,p ,d ):
        items =sorted (d .items (),key =lambda x :x [1 ],reverse =True )[:5 ]
        if not items :ctk .CTkLabel (p ,text ="无数据",text_color ="#ccc").pack (expand =True );return 
        mx =items [0 ][1 ]if items [0 ][1 ]>0 else 1 
        for i ,(k ,v )in enumerate (items ):
            p .grid_rowconfigure (i ,weight =1 );p .grid_columnconfigure (1 ,weight =1 )
            ctk .CTkLabel (p ,text =k [:12 ],width =80 ,font =("微软雅黑",10 ),text_color =CURRENT_THEME ["text"],anchor ="w").grid (row =i ,column =0 )
            pb =ctk .CTkProgressBar (p ,height =10 ,progress_color ="#87CEEB");pb .grid (row =i ,column =1 ,sticky ="ew",padx =5 );pb .set (v /mx )
            ctk .CTkLabel (p ,text =str (v ),width =25 ,font =("Arial",10 ),text_color =CURRENT_THEME ["text"],anchor ="e").grid (row =i ,column =2 )

    def build_history_tab (self ):
        c =ctk .CTkFrame (self .tab_history ,fg_color ="transparent");c .grid (row =0 ,column =0 ,sticky ="ew",padx =5 ,pady =5 )
        self .search_var =tk .StringVar ();self .search_var .trace ("w",lambda *a :self .refresh_history_delayed ())
        ctk .CTkEntry (c ,textvariable =self .search_var ,width =250 ,text_color =CURRENT_THEME ["text"],fg_color =CURRENT_THEME ["panel_bg"]).pack (side ="left",padx =5 )
        self .filter_visible =False 
        self .btn_toggle_filter =ctk .CTkButton (c ,text ="🌪️ 筛选",width =60 ,fg_color ="#9370DB",command =self .toggle_filters );self .btn_toggle_filter .pack (side ="left",padx =5 )
        ctk .CTkButton (c ,text ="🔄",width =40 ,fg_color ="gray",command =self .refresh_history ).pack (side ="right",padx =5 )
        self .filter_frame =ctk .CTkFrame (self .tab_history ,fg_color =CURRENT_THEME ["panel_bg"],corner_radius =6 )
        all_ups =["全部"]+self .db .get_all_uploaders ()
        plats =["全部","B站 (Bilibili)","油管 (YouTube)","抖音 (Douyin)","推特 (X)"]
        ctk .CTkLabel (self .filter_frame ,text ="平台:",text_color =CURRENT_THEME ["text"]).pack (side ="left",padx =5 )
        self .c_plat_filter =ctk .CTkComboBox (self .filter_frame ,values =plats ,width =120 ,command =lambda x :self .refresh_history (),text_color =CURRENT_THEME ["text"],fg_color =CURRENT_THEME ["main_bg"]);self .c_plat_filter .pack (side ="left")
        ctk .CTkLabel (self .filter_frame ,text ="UP主:",text_color =CURRENT_THEME ["text"]).pack (side ="left",padx =5 )
        self .c_up_filter =ctk .CTkComboBox (self .filter_frame ,values =all_ups ,width =150 ,command =lambda x :self .refresh_history (),text_color =CURRENT_THEME ["text"],fg_color =CURRENT_THEME ["main_bg"]);self .c_up_filter .pack (side ="left")
        ctk .CTkButton (self .filter_frame ,text ="重置",width =50 ,fg_color ="#CD5C5C",command =self .reset_filters ).pack (side ="left",padx =10 )
        self .hist_scroll =ctk .CTkScrollableFrame (self .tab_history ,fg_color ="transparent");self .hist_scroll .grid (row =2 ,column =0 ,sticky ="nsew",padx =5 ,pady =5 )
        self .refresh_history ()

    def toggle_filters (self ):
        if self .filter_visible :self .filter_frame .grid_forget ();self .filter_visible =False ;self .btn_toggle_filter .configure (fg_color ="#9370DB")
        else :self .filter_frame .grid (row =1 ,column =0 ,sticky ="ew",padx =10 ,pady =5 );self .filter_visible =True ;self .btn_toggle_filter .configure (fg_color =CURRENT_THEME ["accent"])
    def reset_filters (self ):self .c_plat_filter .set ("全部");self .c_up_filter .set ("全部");self .search_var .set ("");self .refresh_history ()
    def refresh_history_delayed (self ):
        if hasattr (self ,'_after_id'):self .after_cancel (self ._after_id )
        self ._after_id =self .after (500 ,self .refresh_history )
    def refresh_history (self ):
        for w in self .hist_scroll .winfo_children ():w .destroy ()
        recs =self .db .search_history (self .search_var .get ().strip (),self .c_up_filter .get (),self .c_plat_filter .get ())
        if not recs :ctk .CTkLabel (self .hist_scroll ,text ="🔍 无结果",text_color =CURRENT_THEME ["text"]).pack (pady =20 );return 
        for r in recs :
            item =ctk .CTkFrame (self .hist_scroll ,fg_color =CURRENT_THEME ["secondary"],corner_radius =6 );item .pack (fill ="x",pady =2 ,padx =5 )
            f =ctk .CTkFrame (item ,fg_color ="transparent");f .pack (side ="left",fill ="x",expand =True ,padx =8 ,pady =4 )
            ctk .CTkLabel (f ,text =r .title ,font =("微软雅黑",12 ,"bold"),text_color =CURRENT_THEME ["text"],anchor ="w").pack (fill ="x")
            ctk .CTkLabel (f ,text =f"{r.uploader} | {r.download_date} | {r.size_mb:.1f}MB | ⏱ {r.duration}s",font =("微软雅黑",10 ),text_color ="gray",anchor ="w").pack (fill ="x")
            act =ctk .CTkFrame (item ,fg_color ="transparent");act .pack (side ="right",padx =5 )
            if r .webpage_url :ctk .CTkButton (act ,text ="📺",width =30 ,height =24 ,fg_color ="#87CEEB",command =lambda u =r .webpage_url :webbrowser .open (u )).pack (side ="left",padx =1 )
            if r .uploader_url :ctk .CTkButton (act ,text ="🏠",width =30 ,height =24 ,fg_color ="#DDA0DD",command =lambda u =r .uploader_url :webbrowser .open (u )).pack (side ="left",padx =1 )

class SettingsWindow (ctk .CTkToplevel ):
    def __init__ (self ,parent ,callback ):
        super ().__init__ (parent );self .title ("⚙️ 设置");self .geometry ("600x350");self .callback =callback ;self .transient (parent );self .grab_set ()
        self .configure (fg_color =CURRENT_THEME ["main_bg"])
        ctk .CTkLabel (self ,text ="🔧 路径配置",font =FONT_B ,text_color =CURRENT_THEME ["accent"]).pack (pady =10 )
        self .mk_path_row ("yt-dlp.exe:","ytdlp","https://github.com/yt-dlp/yt-dlp/releases",parent .cfg .get ('ytdlp_path',''))
        self .mk_path_row ("ffmpeg bin:","ffmpeg","https://www.gyan.dev/ffmpeg/builds/",parent .cfg .get ('ffmpeg_path',''),is_dir =True )
        btn_box =ctk .CTkFrame (self ,fg_color ="transparent");btn_box .pack (pady =20 )
        ctk .CTkButton (btn_box ,text ="💾 保存",fg_color =CURRENT_THEME ["accent"],command =self .save ).pack (side ="left",padx =10 )
        ctk .CTkButton (btn_box ,text ="❌ 取消",fg_color ="gray",command =self .destroy ).pack (side ="left",padx =10 )
    def mk_path_row (self ,lbl ,key ,url ,val ,is_dir =False ):
        f =ctk .CTkFrame (self ,fg_color ="transparent");f .pack (fill ="x",padx =20 ,pady =10 )
        t =ctk .CTkFrame (f ,fg_color ="transparent");t .pack (fill ="x")
        ctk .CTkLabel (t ,text =lbl ,width =100 ,anchor ="w",text_color =CURRENT_THEME ["text"]).pack (side ="left")
        ctk .CTkButton (t ,text ="⬇️ 下载",width =60 ,height =20 ,fg_color ="#9370DB",command =lambda :webbrowser .open (url )).pack (side ="right")
        b =ctk .CTkFrame (f ,fg_color ="transparent");b .pack (fill ="x",pady =2 )
        e =ctk .CTkEntry (b ,width =350 ,fg_color =CURRENT_THEME ["panel_bg"],text_color =CURRENT_THEME ["text"]);e .pack (side ="left",padx =5 );setattr (self ,f"e_{key}",e )
        sys_path =shutil .which ("ffmpeg"if "ffmpeg"in key else "yt-dlp")
        cmd =self .browse_dir if is_dir else self .browse_file 
        btn =ctk .CTkButton (b ,text ="📂",width =50 ,command =lambda :cmd (e ),fg_color =CURRENT_THEME ["accent"]);btn .pack (side ="left")
        if sys_path :e .insert (0 ,sys_path );e .configure (state ="disabled");btn .configure (state ="disabled");ctk .CTkLabel (b ,text ="✅ 系统环境",text_color ="green").pack (side ="left",padx =5 )
        else :e .insert (0 ,val )
    def browse_file (self ,e ):
        f =filedialog .askopenfilename (filetypes =[("Executables","*.exe"),("All","*.*")])
        if f :
            e .delete (0 ,"end")
            e .insert (0 ,f )
    def browse_dir (self ,e ):
        d =filedialog .askdirectory ()
        if d :
            e .delete (0 ,"end")
            e .insert (0 ,d )
    def save (self ):self .callback (self .e_ytdlp .get (),self .e_ffmpeg .get ());self .destroy ()

class SponsorSelectWindow (ctk .CTkToplevel ):
    def __init__ (self ,parent ,current_cats ,callback ):
        super ().__init__ (parent );self .title ("🍽️ 挑食菜单");self .geometry ("450x550");self .callback =callback ;self .transient (parent );self .grab_set ();self .configure (fg_color =CURRENT_THEME ["main_bg"])
        self .cats_map ={"all":"🌐 全部一口吞 (All)","sponsor":"💰 恰饭广告 (Sponsor)","selfpromo":"🗣️ 自卖自夸 (Self Promo)","intro":"🎞️ 啰嗦片头 (Intro)","outro":"🎬 啰嗦片尾 (Outro)","intermission":"🚻 中场尿点 (Intermission)","preview":"🔍 剧透预告 (Preview)","filler":"💤 水时长 (Filler)","music_offtopic":"🎶 乱放BGM (Music Offtopic)"}
        self .vars ={};ctk .CTkLabel (self ,text ="主人喵~ 不想吃哪几段？",font =FONT_B ,text_color =CURRENT_THEME ["accent"]).pack (pady =15 )
        scroll =ctk .CTkScrollableFrame (self ,fg_color ="transparent");scroll .pack (fill ="both",expand =True ,padx =20 ,pady =5 )
        self .all_var =ctk .BooleanVar (value ="all"in current_cats );self .cb_all =ctk .CTkCheckBox (scroll ,text =self .cats_map ["all"],variable =self .all_var ,font =FONT_N ,border_color =CURRENT_THEME ["accent"],fg_color =CURRENT_THEME ["accent"],command =self .on_all_click ,text_color =CURRENT_THEME ["text"]);self .cb_all .pack (anchor ="w",pady =5 );self .vars ["all"]=self .all_var 
        ctk .CTkFrame (scroll ,height =2 ,fg_color ="#ddd").pack (fill ="x",pady =10 )
        for key ,label in self .cats_map .items ():
            if key =="all":continue 
            v =ctk .BooleanVar (value =(key in current_cats )and ("all"not in current_cats ))
            ctk .CTkCheckBox (scroll ,text =label ,variable =v ,font =FONT_N ,border_color ="#9370DB",fg_color ="#9370DB",command =lambda k =key :self .on_item_click (k ),text_color =CURRENT_THEME ["text"]).pack (anchor ="w",pady =5 );self .vars [key ]=v 
        ctk .CTkButton (self ,text ="👌 就这么定了",fg_color =CURRENT_THEME ["accent"],width =150 ,font =FONT_B ,command =self .confirm ).pack (pady =20 )
    def on_all_click (self ):
        if self .all_var .get ():
            for k ,v in self .vars .items ():
                if k !="all":v .set (False )
    def on_item_click (self ,key ):
        if self .vars [key ].get ():self .all_var .set (False )
    def confirm (self ):
        s =["all"]if self .all_var .get ()else [k for k ,v in self .vars .items ()if k !="all"and v .get ()]
        self .callback (s if s else ["all"]);self .destroy ()

class BatchUrlWindow (ctk .CTkToplevel ):
    def __init__ (self ,parent ,callback ):
        super ().__init__ (parent );self .title ("📚 批量喂食");self .geometry ("600x500");self .callback =callback ;self .transient (parent );self .grab_set ();self .configure (fg_color =CURRENT_THEME ["main_bg"])
        ctk .CTkLabel (self ,text ="请把链接统统贴在这里 (一行一个) 喵！👇",font =FONT_B ,text_color =CURRENT_THEME ["accent"]).pack (pady =15 )
        self .txt_urls =ctk .CTkTextbox (self ,font =FONT_LOG ,width =550 ,height =350 ,fg_color =CURRENT_THEME ["panel_bg"],text_color =CURRENT_THEME ["text"]);self .txt_urls .pack (pady =5 )
        btn_f =ctk .CTkFrame (self ,fg_color ="transparent");btn_f .pack (pady =15 )
        ctk .CTkButton (btn_f ,text ="❌ 算了",fg_color ="gray",width =100 ,command =self .destroy ).pack (side ="left",padx =10 )
        ctk .CTkButton (btn_f ,text ="✅ 全部吞掉",fg_color =CURRENT_THEME ["accent"],width =150 ,font =FONT_B ,command =self .confirm ).pack (side ="left",padx =10 )
    def confirm (self ):
        c =self .txt_urls .get ("1.0","end").strip ()
        if not c :self .destroy ();return 
        self .callback ([l .strip ()for l in c .split ('\n')if l .strip ()]);self .destroy ()

class TemplateEditorWindow (ctk .CTkToplevel ):
    def __init__ (self ,parent ,tmpl_on ,current_tmpl ,callback ):
        super ().__init__ (parent );self .title ("🏷️ 命名模板");self .geometry ("600x600");self .callback =callback ;self .transient (parent );self .grab_set ();self .configure (fg_color =CURRENT_THEME ["main_bg"])
        ctk .CTkLabel (self ,text ="主人喵~ 想怎么给猎物取名？",font =FONT_B ,text_color =CURRENT_THEME ["accent"]).pack (pady =15 )
        self .sw_on =ctk .CTkSwitch (self ,text ="启用自定义重命名",font =FONT_N ,progress_color =CURRENT_THEME ["accent"],text_color =CURRENT_THEME ["text"]);self .sw_on .pack (pady =5 )
        if tmpl_on :self .sw_on .select ()
        self .e_tmpl =ctk .CTkEntry (self ,font =FONT_LOG ,width =500 ,height =40 ,fg_color =CURRENT_THEME ["panel_bg"],text_color =CURRENT_THEME ["text"]);self .e_tmpl .insert (0 ,current_tmpl );self .e_tmpl .pack (pady =10 )
        scroll =ctk .CTkScrollableFrame (self ,fg_color ="transparent",width =550 ,height =350 );scroll .pack (pady =10 )
        tags =[("📄 标题","%(title)s"),("👤 UP主","%(uploader)s"),("📅 日期","%(upload_date)s"),("🆔 视频ID","%(id)s"),("📺 频道名","%(channel)s"),("🔢 列表序号","%(playlist_index)s"),("⏱️ 时长","%(duration)s"),("📐 分辨率","%(resolution)s"),("📂 原文件名","%(original_filename)s")]
        for i ,(t ,v )in enumerate (tags ):ctk .CTkButton (scroll ,text =t ,font =FONT_N ,fg_color ="#9370DB",command =lambda v =v :self .e_tmpl .insert ("end",v )).grid (row =i //2 ,column =i %2 ,padx =10 ,pady =5 ,sticky ="ew")
        scroll .columnconfigure (0 ,weight =1 );scroll .columnconfigure (1 ,weight =1 )
        btn_box =ctk .CTkFrame (self ,fg_color ="transparent");btn_box .pack (pady =10 )
        ctk .CTkButton (btn_box ,text ="💾 保存",fg_color =CURRENT_THEME ["accent"],command =self .save ).pack (side ="left",padx =10 )
    def save (self ):t =self .e_tmpl .get ().strip ();self .callback (self .sw_on .get (),t if t else "%(title)s");self .destroy ()

class ChatFilterSelector (ctk .CTkToplevel ):
    def __init__ (self ,parent ,current_filters ,callback ):
        super ().__init__ (parent )
        self .title ("💬 聊天室筛选器")
        self .geometry ("400x500")
        self .callback =callback 
        self .transient (parent )
        self .grab_set ()
        self .configure (fg_color =CURRENT_THEME ["main_bg"])

        ctk .CTkLabel (self ,text ="🔎 请选择要保留的成分",font =FONT_B ,text_color =CURRENT_THEME ["accent"]).pack (pady =15 )

        self .fields ={
        "author":"👤 发言人 (Author)",
        "message":"💬 弹幕内容 (Message)",
        "timestamp":"⏱️ 时间戳 (Timestamp)",
        "money":"💰 投喂金额 (SuperChat)",
        "badges":"🏅 徽章/头衔 (Badges)"
        }

        self .vars ={}
        for k ,v in self .fields .items ():
            val =ctk .BooleanVar (value =(k in current_filters ))
            cb =ctk .CTkCheckBox (self ,text =v ,variable =val ,font =FONT_N ,text_color =CURRENT_THEME ["text"],border_color =CURRENT_THEME ["accent"],fg_color =CURRENT_THEME ["accent"])
            cb .pack (anchor ="w",padx =40 ,pady =10 )
            self .vars [k ]=val 

        btn_f =ctk .CTkFrame (self ,fg_color ="transparent")
        btn_f .pack (pady =20 )
        ctk .CTkButton (btn_f ,text ="✅ 确认",fg_color =CURRENT_THEME ["accent"],command =self .confirm ).pack ()

    def confirm (self ):
        selected =[k for k ,v in self .vars .items ()if v .get ()]
        if not selected :selected =["author","message"]
        self .callback (selected )
        self .destroy ()

class TaskEditWindow (ctk .CTkToplevel ):
    def __init__ (self ,parent ,item_data ,on_save ):
        super ().__init__ (parent );self .title ("✏️ 任务编辑");self .geometry ("600x700");self .item_data =item_data ;self .on_save =on_save ;self .transient (parent );self .grab_set ();self .configure (fg_color =CURRENT_THEME ["main_bg"])
        cfg =item_data ['config'];meta =item_data .get ('meta',{})
        scroll =ctk .CTkScrollableFrame (self ,fg_color ="transparent");scroll .pack (fill ="both",expand =True ,padx =20 ,pady =5 )
        ctk .CTkLabel (scroll ,text ="模式:",font =FONT_B ,text_color =CURRENT_THEME ["text"]).pack (anchor ="w")
        self .seg_mode =ctk .CTkSegmentedButton (scroll ,values =["最佳喵 (Auto)","手动挑选 (Manual)","直播蹲守 (Live)","只要声音 (MP3)","只要小纸条 (字幕)","只抓聊天室 (Chat)"],selected_color =CURRENT_THEME ["accent"],command =self .upd_ui );self .seg_mode .pack (fill ="x",pady =5 );self .seg_mode .set (cfg ['mode'])
        self .fmt_frame =ctk .CTkFrame (scroll ,fg_color =CURRENT_THEME ["panel_bg"])

        self .c_video =ctk .CTkComboBox (self .fmt_frame ,width =400 ,command =self .on_video_change );self .c_video .pack (pady =5 )
        self .c_audio =ctk .CTkComboBox (self .fmt_frame ,width =400 );self .c_audio .pack (pady =5 )

        self .video_infos ={}
        self .populate_formats (meta ,cfg )

        self .chat_frame =ctk .CTkFrame (scroll ,fg_color =CURRENT_THEME ["panel_bg"])
        ctk .CTkLabel (self .chat_frame ,text ="主人喵~ 聊天记录要怎么处理？",font =FONT_S ,text_color =CURRENT_THEME ["text"]).pack (anchor ="w",padx =5 ,pady =2 )

        self .chat_mode_var =ctk .StringVar (value =cfg .get ("chat_mode","full"))
        ctk .CTkRadioButton (self .chat_frame ,text ="全部完整记录 (Raw JSON)",variable =self .chat_mode_var ,value ="full",font =FONT_N ,text_color =CURRENT_THEME ["text"],fg_color =CURRENT_THEME ["accent"],command =self .upd_chat_ui ).pack (anchor ="w",padx =10 ,pady =5 )
        ctk .CTkRadioButton (self .chat_frame ,text ="精简筛选 (Filter JSON)",variable =self .chat_mode_var ,value ="filter",font =FONT_N ,text_color =CURRENT_THEME ["text"],fg_color =CURRENT_THEME ["accent"],command =self .upd_chat_ui ).pack (anchor ="w",padx =10 ,pady =5 )

        self .btn_chat_filter =ctk .CTkButton (self .chat_frame ,text ="⚙️ 选择保留项...",width =150 ,fg_color ="#9370DB",command =self .open_filter_selector )
        self .chat_filters =cfg .get ("chat_filters",["author","message","timestamp"])

        self .sw_embed =ctk .CTkSwitch (scroll ,text ="硬塞字幕",font =FONT_N ,progress_color =CURRENT_THEME ["accent"],text_color =CURRENT_THEME ["text"]);self .sw_embed .pack (pady =10 )
        if cfg .get ('embed'):self .sw_embed .select ()
        self .upd_ui ();ctk .CTkButton (self ,text ="保存",fg_color =CURRENT_THEME ["accent"],command =self .save ).pack (pady =10 )

    def populate_formats (self ,meta ,cfg ):
        if 'formats'not in meta :
            self .c_video .configure (values =["No Video"]);self .c_audio .configure (values =["No Audio"])
            return 

        v_list ,a_list =[],[]
        self .video_infos ={}

        for f in meta ['formats']:
            fid =f .get ('format_id')
            if not fid :continue 


            if f .get ('vcodec')and f .get ('vcodec')!='none':
                h =f .get ('height',0 )or 0 
                br =f .get ('tbr')or f .get ('vbr')or 0 
                fps =f .get ('fps',0 )
                vc =f .get ('vcodec','')
                ac =f .get ('acodec','none')
                ext =f .get ('ext','')

                has_audio =(ac and ac !='none')

                label =f"{h}P | {ext} | {vc} | {int(br)}k"
                if has_audio :label +=" | 🔊"
                label +=f" | ID:{fid}"

                v_list .append ({
                'h':h ,'br':br ,'label':label ,'id':fid ,'has_audio':has_audio 
                })
                self .video_infos [label ]={'has_audio':has_audio ,'id':fid }


            if f .get ('acodec')and f .get ('acodec')!='none'and f .get ('vcodec')=='none':
                abr =f .get ('abr',0 )or 0 
                ac =f .get ('acodec','')
                ext =f .get ('ext','')
                label =f"{int(abr)}k | {ext} | {ac} | ID:{fid}"
                a_list .append ({'abr':abr ,'label':label ,'id':fid })


        v_list .sort (key =lambda x :(x ['h'],x ['br']),reverse =True )
        a_list .sort (key =lambda x :x ['abr'],reverse =True )

        v_labels =[x ['label']for x in v_list ]
        a_labels =[x ['label']for x in a_list ]

        self .c_video .configure (values =v_labels if v_labels else ["No Video"])
        self .c_audio .configure (values =a_labels if a_labels else ["No Audio"])


        curr_vid =cfg .get ('v_id')
        if curr_vid :
            for x in v_labels :
                if x .endswith (f"ID:{curr_vid}"):
                    self .c_video .set (x );break 
        elif v_labels :self .c_video .set (v_labels [0 ])

        curr_aid =cfg .get ('a_id')
        if curr_aid :
            for x in a_labels :
                if x .endswith (f"ID:{curr_aid}"):
                    self .c_audio .set (x );break 
        elif a_labels :self .c_audio .set (a_labels [0 ])

        self .on_video_change (self .c_video .get ())

    def on_video_change (self ,choice ):
        info =self .video_infos .get (choice )
        if info and info ['has_audio']:
            self .c_audio .configure (state ="disabled")

        else :
            self .c_audio .configure (state ="normal")

    def upd_ui (self ,_ =None ):
        m =self .seg_mode .get ()
        if "手动"in m :self .fmt_frame .pack (fill ="x",pady =5 ,after =self .seg_mode )
        else :self .fmt_frame .pack_forget ()
        if "聊天室"in m :
            self .chat_frame .pack (fill ="x",pady =5 ,after =self .seg_mode )
            self .upd_chat_ui ()
        else :self .chat_frame .pack_forget ()

    def get_filter_text (self ):
        if not self .chat_filters :return "⚙️ 选择保留项..."
        display =", ".join ([f .capitalize ()for f in self .chat_filters ])
        if len (display )>20 :display =display [:20 ]+"..."
        return f"⚙️ 选择保留项... ({display})"

    def upd_chat_ui (self ):
        if self .chat_mode_var .get ()=="filter":
            self .btn_chat_filter .configure (text =self .get_filter_text ())
            self .btn_chat_filter .pack (pady =5 ,padx =30 ,anchor ="w")
        else :
            self .btn_chat_filter .pack_forget ()

    def open_filter_selector (self ):
        ChatFilterSelector (self ,self .chat_filters ,self .set_filters )

    def set_filters (self ,filters ):
        self .chat_filters =filters 
        self .upd_chat_ui ()

    def save (self ):
        new =self .item_data ['config'].copy ();new ['mode']=self .seg_mode .get ();new ['embed']=self .sw_embed .get ()
        if "手动"in new ['mode']:
            new ['v_id']=self .c_video .get ().split ("ID:")[-1 ]if "ID:"in self .c_video .get ()else None 
            if self .c_audio .cget ("state")=="normal":
                new ['a_id']=self .c_audio .get ().split ("ID:")[-1 ]if "ID:"in self .c_audio .get ()else None 
            else :
                new ['a_id']=None 
        if "聊天室"in new ['mode']:
            new ['chat_mode']=self .chat_mode_var .get ()
            new ['chat_filters']=self .chat_filters 
        self .on_save (self .item_data ,new );self .destroy ()

class NekoDownloader (ctk .CTk ):
    def __init__ (self ,cached_data =None ):
        # 在初始化前确保没有遗留的 root
        super ().__init__ ()
        
        # 显式设置自己为默认根窗口，防止字体初始化失败
        import tkinter as tk
        tk._default_root = self  # 关键修复：手动修复 Tkinter 的根引用
        
        # 针对 "Too early to use font" 的防御性设置
        # 强制更新 idle 任务，确保窗口句柄完全创建后再进行 UI 渲染
        self.update_idletasks()
        
        # 版本更新
        self.title ("🐾 猫娘视频下载器")
        self.geometry ("1150x900")
        self.configure (fg_color =CURRENT_THEME ["main_bg"])
        self.protocol ("WM_DELETE_WINDOW",self .on_close )
        
        # 线程池用于后台任务
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        
        # 如果有缓存数据，先恢复状态
        if cached_data:
            self.restore_from_cache(cached_data)
        
        self.db =NekoDB ()
        self.mood_manager =NekoMoodManager (self .db )
        
        self.video_infos ={};self.video_opts ={};self.audio_opts ={};
        self.current_meta =None ;self.current_thumb_img =None ;self.last_analyzed_url ="";self.queue_items =[]
        self.cfg =self .load_cfg ();self.max_concurrent =2 
        self.current_sponsor_cats =self .cfg .get ("sponsor_cats",["all"])
        self.sb_cn_map ={"all":"全部","sponsor":"广告","selfpromo":"自推","intro":"片头","outro":"片尾","intermission":"中场","preview":"预告","filler":"废话","music_offtopic":"乱奏"}
        
        self.setup_ui ()
        self.refresh_cookies ()
        self.start_thread (self .startup_maintenance )
        self.start_thread (self .check_mood_loop )
        
        self.last_saved_bytes =0 
        
        # 如果没有缓存数据，需要完整初始化
        if not cached_data:
            self.post_init_setup()
    
    def restore_from_cache(self, cached_data):
        """从缓存恢复状态"""
        try:
            # 恢复配置
            if 'cfg' in cached_data:
                self.cfg = cached_data['cfg']
            
            # 恢复其他状态
            if 'sponsor_cats' in cached_data:
                self.current_sponsor_cats = cached_data['sponsor_cats']
                
            logger.info("从缓存恢复状态成功")
        except Exception as e:
            logger.error(f"从缓存恢复状态失败: {e}")
    
    def get_cache_data(self):
        """获取需要缓存的数据"""
        try:
            return {
                'cfg': self.cfg,
                'sponsor_cats': self.current_sponsor_cats,
                'timestamp': time.time()
            }
        except Exception as e:
            logger.error(f"获取缓存数据失败: {e}")
            return None
    
    def post_init_setup(self):
        """初始化后的额外设置"""
        # 这里可以添加一些不需要立即执行的初始化操作
        pass
    
    def start_thread(self, target, *args, **kwargs):
        """启动后台线程"""
        thread = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
        thread.start()
        return thread
    
    def submit_async_task(self, func, *args, **kwargs):
        """提交异步任务到线程池"""
        return self.thread_pool.submit(func, *args, **kwargs) 

    def load_cfg (self ):
        d ={
        "dir":os .path .join (os .path .expanduser ("~"),"Videos"),"proxy":"","proxy_on":False ,"mode":"最佳喵 (Auto)","embed":False ,"cookie":"🚫 No Cookie","playlist":False ,"sponsor_action":"🙈 Off","sponsor_cats":["all"],
        "tmpl_on":False ,"tmpl_str":"%(title)s","ytdlp_path":"","ffmpeg_path":"","chat_mode":"full","chat_filters":["author","message","timestamp"],
        "time_range_on":False ,"start_h":"00","start_m":"00","start_s":"00","end_h":"00","end_m":"00","end_s":"00"
        }
        if os .path .exists (CFG_FILE ):
            try :
                with open (CFG_FILE ,"r",encoding ="utf-8")as f :return {**d ,**json .load (f )}
            except :pass 
        return d 

    def on_close (self ):
        # 保存缓存
        try:
            cache_data = self.get_cache_data()
            if cache_data:
                cache_manager = CacheManager()
                cache_manager.save_cache(cache_data)
                logger.info("缓存保存成功")
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
        
        pv =f"{self.e_proxy_ip.get().strip()}:{self.e_proxy_port.get().strip()}"if self .e_proxy_ip .get ().strip ()else ""
        d ={
        "dir":self .e_dir .get (),"proxy":pv ,"proxy_on":self .sw_proxy .get (),"mode":self .seg_mode .get (),"embed":self .sw_embed .get (),"cookie":self .c_cookie .get (),
        "playlist":self .sw_list .get (),"sponsor_action":self .c_sponsor_action .get (),"sponsor_cats":self .current_sponsor_cats ,
        "tmpl_on":self .cfg ["tmpl_on"],"tmpl_str":self .cfg ["tmpl_str"],"ytdlp_path":self .cfg .get ("ytdlp_path",""),"ffmpeg_path":self .cfg .get ("ffmpeg_path",""),
        "chat_mode":self .chat_mode_var .get ()if hasattr (self ,'chat_mode_var')else "full",
        "chat_filters":self .chat_filters if hasattr (self ,'chat_filters')else ["author","message","timestamp"],
        "time_range_on":self .switch_time .get ()if hasattr (self ,'switch_time')else False ,
        "start_h":self .e_start_h .get (),"start_m":self .e_start_m .get (),"start_s":self .e_start_s .get (),
        "end_h":self .e_end_h .get (),"end_m":self .e_end_m .get (),"end_s":self .e_end_s .get ()
        }
        with open (CFG_FILE ,"w",encoding ="utf-8")as f :json .dump (d ,f ,indent =4 )
        self .destroy ()

    def run_safe (self ,func ,*args ,**kwargs ):
        # 如果已经在主线程，直接执行
        if threading .current_thread ()is threading .main_thread ():
            try:
                return func (*args ,**kwargs )
            except Exception as e:
                logger.error(f"主线程执行函数错误: {e}")
                return None
        
        # 非主线程情况
        try:
            # 检查窗口是否存在且主循环是否运行
            if not hasattr(self, 'winfo_exists'):
                logger.warning("对象没有winfo_exists方法，直接执行函数")
                return func(*args, **kwargs)
            
            # 尝试检查窗口是否存在
            try:
                if not self.winfo_exists():
                    logger.warning("主窗口不存在，直接执行函数")
                    return func(*args, **kwargs)
            except RuntimeError as e:
                if "main thread is not in main loop" in str(e):
                    logger.warning("主循环未启动，直接执行函数")
                    return func(*args, **kwargs)
                else:
                    raise
            
            # 主循环运行中，使用after方法
            evt =threading .Event ();res =[None ]
            def w ():
                try:
                    res [0 ]=func (*args ,**kwargs )
                except Exception as e:
                    logger.error(f"执行函数错误: {e}")
                finally:
                    evt .set ()
            
            try:
                self .after (0 ,w )
                # 设置超时，避免无限等待
                if not evt.wait(timeout=10):
                    logger.error("执行函数超时")
                    return None
                return res [0 ]
            except Exception as e:
                logger.error(f"使用after执行函数错误: {e}")
                # 失败后直接执行
                return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"run_safe 错误: {e}")
            # 任何错误都直接执行函数
            try:
                return func(*args, **kwargs)
            except Exception as e2:
                logger.error(f"直接执行函数也失败: {e2}")
                return None

    def on_interact (self ):
        self .mood_manager .interact ()
        self .update_mood_display ()

    def check_mood_loop (self ):
        while True :
            time .sleep (30 )
            try:
                # 更新心情逻辑（不需要UI）
                self .mood_manager .update_logic ()
                
                # 安全更新心情显示
                def update_display():
                    try:
                        if hasattr(self, 'update_mood_display') and hasattr(self, 'header_tip'):
                            self .update_mood_display ()
                    except Exception as e:
                        logger.error(f"更新心情显示错误: {e}")
                
                self .run_safe (update_display)
            except Exception as e:
                logger.error(f"心情循环错误: {e}")

    def update_mood_display (self ):
        msg =self .mood_manager .get_greeting ()
        self .header_tip .configure (text =msg )

    def generate_session_id (self ,url ,output_path ):
        content =f"{url}_{output_path}_{datetime.datetime.now().timestamp()}"
        return hashlib .md5 (content .encode ()).hexdigest ()[:16 ]

    def get_expected_filename (self ,cfg ,meta ):
        if cfg ['tmpl_on']:
            template =cfg ['tmpl_str']
            title =meta .get ('title','Unknown')
            filename =template .replace ('%(title)s',title )
        else :
            filename =meta .get ('title','Unknown')
        filename =re .sub (r'[\\/*?:"<>|]',"",filename )
        return os .path .join (cfg ['dir'],filename )

    def find_current_temp_file (self ,cfg ,meta ):
        expected_name =self .get_expected_filename (cfg ,meta )
        possible_temps =[
        expected_name +".part",
        expected_name +".temp",
        expected_name +".ytdl",
        expected_name +".f*.part"
        ]

        import glob 
        for pattern in possible_temps :
            matches =glob .glob (pattern )
            if matches :
                return matches [0 ]
        return None 

    def save_resume_state (self ,session_id ,cfg ,meta ,downloaded_bytes ,total_bytes ):
        temp_file =self .find_current_temp_file (cfg ,meta )
        if temp_file and downloaded_bytes >0 :
            self .db .save_resume_session (
            session_id =session_id ,
            url =cfg ['url'],
            output_path =cfg ['dir'],
            temp_file =temp_file ,
            downloaded_bytes =downloaded_bytes ,
            total_bytes =total_bytes ,
            download_params =cfg ,
            title =meta .get ('title','Unknown')
            )

    def check_resume_status (self ):
        pending_sessions =self .db .get_pending_resume_sessions ()
        count =len (pending_sessions )if pending_sessions else 0 
        if count >0 :
            self .resume_status_label .configure (text =f"📂 {count}个任务可续传",text_color ="orange")
            self .btn_resume_manager .configure (fg_color ="#FF8C42")
        else :
            self .resume_status_label .configure (text ="无待续传任务",text_color ="gray")
            self .btn_resume_manager .configure (fg_color ="#FF6B6B")
        self .after (5000 ,self .check_resume_status )

    def open_resume_manager (self ):
        ResumeManagerWindow (self ,self .db )

    def start_resume_download (self ,session ,download_params ):
        try :
            self .log (f"Resuming: {session[9]}...","working")
            meta ={'title':session [9 ]}
            session_dict ={
            'session_id':session [0 ],
            'url':session [1 ],
            'output_path':session [2 ],
            'temp_file':session [3 ]
            }
            self .download_item_with_resume (download_params ,meta ,session_dict )
        except Exception as e :
            self .log (f"Resume failed: {e}","sad")

    def setup_ui (self ):
        top =ctk .CTkFrame (self ,fg_color ="transparent");top .pack (fill ="x",pady =(15 ,0 ))
        tb =ctk .CTkFrame (top ,fg_color ="transparent");tb .pack ()
        ba =ctk .CTkFrame (tb ,fg_color ="transparent");ba .pack (side ="left",padx =(0 ,10 ))
        ctk .CTkButton (ba ,text ="⚙️",width =40 ,height =30 ,fg_color ="gray",command =lambda :[self .on_interact (),self .open_settings_window ()]).pack (side ="left",padx =2 )
        ctk .CTkButton (ba ,text ="🎨",width =40 ,height =30 ,fg_color =CURRENT_THEME ["accent"],command =lambda :[self .on_interact (),self .open_theme_editor ()]).pack (side ="left",padx =2 )
        ctk .CTkLabel (tb ,text ="🐾 猫娘下载器",font =FONT_T ,text_color =CURRENT_THEME ["accent"]).pack (side ="left",padx =10 )
        ctk .CTkButton (tb ,text ="📊 记忆仓库",width =120 ,height =30 ,fg_color ="#9370DB",command =lambda :[self .on_interact (),self .open_stats_window ()]).pack (side ="left",padx =10 )

        self .l_version =ctk .CTkLabel (top ,text ="Checking...",font =FONT_S ,text_color ="#888");self .l_version .pack (pady =(0 ,5 ))
        self .header_tip =ctk .CTkLabel (self ,text ="主人喵~ 正在把小窝收拾得漂漂亮亮…",font =FONT_N ,text_color ="gray");self .header_tip .pack (pady =(0 ,2 ))

        self .credit_label =ctk .CTkLabel (self ,text ="本软件为个人学习交流用途喵~ 请勿用于商业用途。",font =("微软雅黑",10 ),text_color ="red",cursor ="hand2")
        self .credit_label .pack (pady =(0 ,8 ))
        self .credit_label .bind ("<Button-1>",lambda e :webbrowser .open ("https://space.bilibili.com/387715606"))

        self .paned =tk .PanedWindow (self ,orient =tk .HORIZONTAL ,bg =CURRENT_THEME ["main_bg"],sashwidth =6 ,sashrelief =tk .RAISED )
        self .paned .pack (fill ="both",expand =True ,padx =15 ,pady =(0 ,15 ))

        self .left_panel =ctk .CTkFrame (self .paned ,fg_color =CURRENT_THEME ["secondary"],corner_radius =15 )
        self .paned .add (self .left_panel ,minsize =500 ,stretch ="always")

        inp =ctk .CTkFrame (self .left_panel ,fg_color ="transparent");inp .pack (fill ="x",padx =20 ,pady =(20 ,5 ))
        self .e_url =ctk .CTkEntry (inp ,placeholder_text ="🔗 把链接丢给猫娘喵…",height =45 ,font =FONT_N ,fg_color =CURRENT_THEME ["panel_bg"],text_color =CURRENT_THEME ["text"]);self .e_url .pack (fill ="x",pady =(0 ,10 ))
        self .e_url .bind ("<Return>",lambda e :self .start_thread (self .smart_add_flow ))
        bg =ctk .CTkFrame (inp ,fg_color ="transparent");bg .pack (fill ="x")
        ctk .CTkButton (bg ,text ="🐾 先闻一闻",height =40 ,font =FONT_B ,fg_color ="#D8BFD8",command =lambda :[self .on_interact (),self .start_thread (self .analyze_ui_wrapper )]).pack (side ="left",fill ="x",expand =True ,padx =(0 ,5 ))
        ctk .CTkButton (bg ,text ="📚 批量喂食",height =40 ,font =FONT_B ,fg_color ="#87CEEB",command =lambda :[self .on_interact (),self .open_batch_window ()]).pack (side ="left",fill ="x",expand =True ,padx =(5 ,0 ))

        self .preview_frame =ctk .CTkFrame (self .left_panel ,fg_color =CURRENT_THEME ["panel_bg"],corner_radius =15 )
        self .preview_frame .pack (fill ="x",padx =20 ,pady =5 )
        self .l_thumb =ctk .CTkLabel (self .preview_frame ,text ="[猫猫待机]",width =160 ,height =90 ,fg_color ="#E0E0E0",corner_radius =10 );self .l_thumb .pack (side ="left",padx =15 ,pady =15 )

        self .l_info =ctk .CTkLabel (self .preview_frame ,text ="等待任务...",font =FONT_N ,justify ="left",anchor ="w",text_color =CURRENT_THEME ["text"])
        self .l_info .pack (side ="left",fill ="both",expand =True ,padx =10 )
        self .preview_frame .bind ("<Configure>",lambda e :self .l_info .configure (wraplength =e .width -200 ))

        self .fmt_frame =ctk .CTkFrame (self .left_panel ,fg_color =CURRENT_THEME ["main_bg"],corner_radius =10 )
        ctk .CTkLabel (self .fmt_frame ,text ="✨ 定制流媒体",font =FONT_B ,text_color =CURRENT_THEME ["accent"]).pack (anchor ="w",padx =10 ,pady =5 )
        self .c_video =ctk .CTkComboBox (self .fmt_frame ,values =["请解析"],font =FONT_N ,height =32 ,command =self .on_main_video_select );self .c_video .pack (fill ="x",padx =10 ,pady =5 )
        self .c_audio =ctk .CTkComboBox (self .fmt_frame ,values =["请解析"],font =FONT_N ,height =32 );self .c_audio .pack (fill ="x",padx =10 ,pady =5 )
        # 手动挑选模式的字幕选择框（包含"不下载字幕"选项）
        self .c_subtitle_manual =ctk .CTkComboBox (self .fmt_frame ,values =["不下载字幕"],font =FONT_N ,height =32 )
        # 字幕模式的字幕选择框（不包含"不下载字幕"选项）
        self .c_subtitle_only =ctk .CTkComboBox (self .fmt_frame ,values =["下载所有字幕"],font =FONT_N ,height =32 )

        self .chat_frame =ctk .CTkFrame (self .left_panel ,fg_color =CURRENT_THEME ["main_bg"],corner_radius =10 )
        ctk .CTkLabel (self .chat_frame ,text ="主人喵~ 想抓哪些聊天碎片？",font =FONT_S ,text_color =CURRENT_THEME ["text"]).pack (anchor ="w",padx =10 ,pady =(5 ,0 ))
        self .chat_mode_var =ctk .StringVar (value =self .cfg .get ("chat_mode","full"))
        ctk .CTkRadioButton (self .chat_frame ,text ="全部完整记录 (Raw JSON)",variable =self .chat_mode_var ,value ="full",font =FONT_N ,text_color =CURRENT_THEME ["text"],fg_color =CURRENT_THEME ["accent"],command =self .upd_chat_ui ).pack (anchor ="w",padx =10 ,pady =5 )
        ctk .CTkRadioButton (self .chat_frame ,text ="精简筛选 (Filter JSON)",variable =self .chat_mode_var ,value ="filter",font =FONT_N ,text_color =CURRENT_THEME ["text"],fg_color =CURRENT_THEME ["accent"],command =self .upd_chat_ui ).pack (anchor ="w",padx =10 ,pady =5 )
        self .btn_chat_filter =ctk .CTkButton (self .chat_frame ,text ="⚙️ 选择保留项...",width =150 ,fg_color ="#9370DB",command =self .open_filter_selector )
        self .chat_filters =self .cfg .get ("chat_filters",["author","message","timestamp"])

        cfg =ctk .CTkFrame (self .left_panel ,fg_color ="transparent");cfg .pack (fill ="x",padx =20 ,pady =10 )
        self .seg_mode =ctk .CTkSegmentedButton (cfg ,values =["最佳喵 (Auto)","手动挑选 (Manual)","直播蹲守 (Live)","只要声音 (MP3)","只要小纸条 (字幕)","只抓聊天室 (Chat)"],font =FONT_B ,height =35 ,selected_color =CURRENT_THEME ["accent"],command =self .upd_ui ,text_color =CURRENT_THEME ["text"])
        self .seg_mode .pack (fill ="x",pady =(0 ,10 ));self .seg_mode .set (self .cfg ["mode"])

        sb =ctk .CTkFrame (cfg ,fg_color ="transparent");sb .pack (fill ="x",pady =(0 ,8 ))
        ctk .CTkLabel (sb ,text ="😾 广告处理:",font =FONT_N ,text_color =CURRENT_THEME ["text"]).pack (side ="left")
        self .c_sponsor_action =ctk .CTkComboBox (sb ,values =["🙈 视而不见 (Off)","🔖 做个记号 (Mark)","✂️ 咬掉扔了 (Remove)"],font =FONT_N ,width =170 ,command =self .on_sponsor_action_change ,text_color =CURRENT_THEME ["text"],fg_color =CURRENT_THEME ["panel_bg"]);self .c_sponsor_action .pack (side ="left",padx =10 );self .c_sponsor_action .set (self .cfg ["sponsor_action"])
        self .l_sb_cats =ctk .CTkLabel (sb ,text ="",font =FONT_S ,text_color =CURRENT_THEME ["accent"]);self .l_sb_cats .pack (side ="left",padx =5 );self .refresh_sb_display ()

        rd =ctk .CTkFrame (cfg ,fg_color ="transparent");rd .pack (fill ="x",pady =5 )
        self .e_dir =ctk .CTkEntry (rd ,placeholder_text ="位置...",height =35 ,font =FONT_N ,fg_color =CURRENT_THEME ["panel_bg"],text_color =CURRENT_THEME ["text"]);self .e_dir .insert (0 ,self .cfg ["dir"]);self .e_dir .pack (side ="left",fill ="x",expand =True ,padx =(0 ,5 ))
        ctk .CTkButton (rd ,text ="🏷️",width =60 ,height =35 ,font =FONT_B ,fg_color ="#9370DB",command =lambda :[self .on_interact (),self .open_template_window ()]).pack (side ="left",padx =(0 ,5 ))
        ctk .CTkButton (rd ,text ="📂",width =50 ,height =35 ,font =FONT_B ,fg_color =CURRENT_THEME ["accent"],command =self .browse ).pack (side ="left")

        sws =ctk .CTkFrame (self .left_panel ,fg_color ="transparent");sws .pack (fill ="x",padx =20 ,pady =5 )
        self .sw_list =ctk .CTkSwitch (sws ,text ="一锅端 (列表)",font =FONT_N ,progress_color =CURRENT_THEME ["accent"],text_color =CURRENT_THEME ["text"]);self .sw_list .pack (side ="left",padx =(0 ,15 ))
        self .sw_embed =ctk .CTkSwitch (sws ,text ="硬塞字幕",font =FONT_N ,progress_color =CURRENT_THEME ["accent"],text_color =CURRENT_THEME ["text"]);self .sw_embed .pack (side ="left")
        if self .cfg ["playlist"]:self .sw_list .select ()
        if self .cfg ["embed"]:self .sw_embed .select ()

        self .net =ctk .CTkFrame (self .left_panel ,fg_color ="transparent");self .net .pack (fill ="x",padx =20 ,pady =5 )
        self .sw_proxy =ctk .CTkSwitch (self .net ,text ="魔法通道",font =FONT_N ,progress_color =CURRENT_THEME ["accent"],command =self .upd_ui ,text_color =CURRENT_THEME ["text"]);self .sw_proxy .pack (side ="left")
        pip ,ppt =("","")
        if ":"in self .cfg ["proxy"]:pip ,ppt =self .cfg ["proxy"].split (":")[:2 ]
        else :pip =self .cfg ["proxy"]
        self .e_proxy_ip =ctk .CTkEntry (self .net ,placeholder_text ="127.0.0.1",width =130 ,height =30 ,font =FONT_N ,fg_color =CURRENT_THEME ["panel_bg"],text_color =CURRENT_THEME ["text"]);self .e_proxy_ip .insert (0 ,pip );self .e_proxy_ip .pack (side ="left",padx =(10 ,2 ))
        ctk .CTkLabel (self .net ,text =":",font =FONT_B ,text_color =CURRENT_THEME ["text"]).pack (side ="left")
        self .e_proxy_port =ctk .CTkEntry (self .net ,placeholder_text ="7890",width =70 ,height =30 ,font =FONT_N ,fg_color =CURRENT_THEME ["panel_bg"],text_color =CURRENT_THEME ["text"]);self .e_proxy_port .insert (0 ,ppt );self .e_proxy_port .pack (side ="left",padx =(2 ,10 ))
        ctk .CTkLabel (self .net ,text ="⚡并发:",font =FONT_S ,text_color =CURRENT_THEME ["text"]).pack (side ="left",padx =(15 ,2 ))
        self .c_concurrent =ctk .CTkComboBox (self .net ,values =["1","2","3","4","5"],width =60 ,state ="readonly",command =lambda v :setattr (self ,'max_concurrent',int (v )),fg_color =CURRENT_THEME ["panel_bg"],text_color =CURRENT_THEME ["text"]);self .c_concurrent .set ("2");self .c_concurrent .pack (side ="left")
        self .c_cookie =ctk .CTkComboBox (self .net ,values =["🚫 No Cookie"],width =150 ,height =30 ,font =FONT_N ,fg_color =CURRENT_THEME ["panel_bg"],text_color =CURRENT_THEME ["text"]);self .c_cookie .pack (side ="right")
        if self .cfg ["proxy_on"]:self .sw_proxy .select ()
        
        # 创建浏览器选择器框架
        self .browser_frame =ctk .CTkFrame (self .left_panel ,fg_color ="transparent")
        # 配置网格权重
        self .browser_frame .columnconfigure (0 ,weight =1 )
        self .browser_frame .columnconfigure (1 ,weight =1 )
        
        # 左侧部分：标签与说明
        left_part =ctk .CTkFrame (self .browser_frame ,fg_color ="transparent")
        left_part .grid (row =0 ,column =0 ,sticky ="nsew",padx =(0 ,5 ))
        
        ctk .CTkLabel (
            left_part ,
            text ="🌐 浏览器 Cookie 授权",
            font =FONT_B ,
            text_color =CURRENT_THEME ["text"],
            anchor ="w"
        ).pack (fill ="x")
        
        ctk .CTkLabel (
            left_part ,
            text ="选择已登录视频网站的浏览器以获取会员权限",
            font =FONT_S ,
            text_color ="gray",
            anchor ="w"
        ).pack (fill ="x")
        
        # 右侧部分：选择器与操作
        right_part =ctk .CTkFrame (self .browser_frame ,fg_color ="transparent")
        right_part .grid (row =0 ,column =1 ,sticky ="nsew",padx =(5 ,0 ))
        
        # 浏览器下拉框
        self .c_browser =ctk .CTkComboBox (
            right_part ,
            values =["chrome","firefox","edge","safari"],
            width =120 ,
            font =FONT_N ,
            fg_color =CURRENT_THEME ["panel_bg"],
            text_color =CURRENT_THEME ["text"]
        )
        self .c_browser .pack (side ="left",fill ="x",expand =True ,padx =(0 ,5 ))
        
        # 绑定cookie选择框的变化事件
        self .c_cookie .configure (command =self .update_browser_selector )

        self .time_frame =ctk .CTkFrame (self .left_panel ,fg_color ="transparent");self .time_frame .pack (fill ="x",padx =20 ,pady =5 )
        self .switch_time =ctk .CTkSwitch (self .time_frame ,text ="✂️ 片段下载",font =FONT_N ,progress_color =CURRENT_THEME ["accent"],text_color =CURRENT_THEME ["text"],command =self .upd_ui );self .switch_time .pack (side ="left",padx =(0 ,10 ))
        if self .cfg .get ("time_range_on"):self .switch_time .select ()
        self .cut_box =ctk .CTkFrame (self .time_frame ,fg_color ="transparent")

        def mk_time_entry (parent ,val ):
            e =ctk .CTkEntry (parent ,width =30 ,height =25 ,font =FONT_S ,fg_color =CURRENT_THEME ["panel_bg"],text_color =CURRENT_THEME ["text"])
            e .insert (0 ,val )
            return e 

        self .e_start_h =mk_time_entry (self .cut_box ,self .cfg .get ("start_h","00"));self .e_start_h .pack (side ="left")
        ctk .CTkLabel (self .cut_box ,text =":",text_color =CURRENT_THEME ["text"]).pack (side ="left")
        self .e_start_m =mk_time_entry (self .cut_box ,self .cfg .get ("start_m","00"));self .e_start_m .pack (side ="left")
        ctk .CTkLabel (self .cut_box ,text =":",text_color =CURRENT_THEME ["text"]).pack (side ="left")
        self .e_start_s =mk_time_entry (self .cut_box ,self .cfg .get ("start_s","00"));self .e_start_s .pack (side ="left")

        ctk .CTkLabel (self .cut_box ,text =" 至 ",font =FONT_S ,text_color =CURRENT_THEME ["text"]).pack (side ="left",padx =5 )

        self .e_end_h =mk_time_entry (self .cut_box ,self .cfg .get ("end_h","00"));self .e_end_h .pack (side ="left")
        ctk .CTkLabel (self .cut_box ,text =":",text_color =CURRENT_THEME ["text"]).pack (side ="left")
        self .e_end_m =mk_time_entry (self .cut_box ,self .cfg .get ("end_m","00"));self .e_end_m .pack (side ="left")
        ctk .CTkLabel (self .cut_box ,text =":",text_color =CURRENT_THEME ["text"]).pack (side ="left")
        self .e_end_s =mk_time_entry (self .cut_box ,self .cfg .get ("end_s","00"));self .e_end_s .pack (side ="left")

        resume_frame =ctk .CTkFrame (self .left_panel ,fg_color ="transparent")
        resume_frame .pack (fill ="x",padx =20 ,pady =5 )
        self .btn_resume_manager =ctk .CTkButton (resume_frame ,text ="🔄 续传管理",height =30 ,font =FONT_N ,fg_color ="#FF6B6B",command =lambda :[self .on_interact (),self .open_resume_manager ()])
        self .btn_resume_manager .pack (side ="left",padx =(0 ,10 ))
        self .resume_status_label =ctk .CTkLabel (resume_frame ,text ="无待续传任务",font =FONT_S ,text_color ="gray")
        self .resume_status_label .pack (side ="left")
        self .after (5000 ,self .check_resume_status )

        bb =ctk .CTkFrame (self .left_panel ,fg_color ="transparent");bb .pack (fill ="x",padx =20 ,pady =15 )
        bb .columnconfigure (0 ,weight =1 );bb .columnconfigure (1 ,weight =1 );bb .columnconfigure (2 ,weight =1 )

        self .btn_add =ctk .CTkButton (bb ,text ="📥 放进篮子",height =50 ,font =FONT_B ,fg_color =CURRENT_THEME ["btn_add_bg"],text_color =CURRENT_THEME ["btn_add_fg"],hover_color =CURRENT_THEME ["btn_add_bg"],command =lambda :[self .on_interact (),self .start_thread (self .smart_add_flow )])
        self .btn_add .grid (row =0 ,column =0 ,padx =(0 ,5 ),sticky ="ew")
        self .btn_now =ctk .CTkButton (bb ,text ="⚡ 立即抓取",height =50 ,font =FONT_B ,fg_color =CURRENT_THEME ["btn_now_bg"],text_color =CURRENT_THEME ["btn_now_fg"],hover_color =CURRENT_THEME ["btn_now_bg"],command =lambda :[self .on_interact (),self .start_thread (self .download_now_flow )])
        self .btn_now .grid (row =0 ,column =1 ,padx =5 ,sticky ="ew")
        self .btn_start =ctk .CTkButton (bb ,text ="🚀 叼回窝里",height =50 ,font =FONT_B ,fg_color =CURRENT_THEME ["btn_start_bg"],text_color =CURRENT_THEME ["btn_start_fg"],hover_color =CURRENT_THEME ["btn_start_bg"],command =lambda :[self .on_interact (),self .start_thread (self .process_queue )])
        self .btn_start .grid (row =0 ,column =2 ,padx =(5 ,0 ),sticky ="ew")

        self .l_status =ctk .CTkLabel (self .left_panel ,text ="呼噜呼噜… 待命中喵",font =FONT_S ,text_color ="gray");self .l_status .pack (pady =(0 ,2 ))
        self .prog =ctk .CTkProgressBar (self .left_panel ,progress_color =CURRENT_THEME ["accent"],height =12 );self .prog .pack (fill ="x",padx =20 ,pady =(0 ,10 ));self .prog .set (0 )
        self .log_box =ctk .CTkTextbox (self .left_panel ,height =100 ,fg_color =CURRENT_THEME ["panel_bg"],text_color =CURRENT_THEME ["text"],font =FONT_LOG ,state ="disabled");self .log_box .pack (fill ="both",expand =True ,padx =20 ,pady =(0 ,20 ))

        self .right_panel =ctk .CTkFrame (self .paned ,fg_color =CURRENT_THEME ["secondary"],corner_radius =15 )
        ctk .CTkLabel (self .right_panel ,text ="🛒 篮子里的小老鼠",font =FONT_B ,text_color =CURRENT_THEME ["accent"]).pack (pady =10 )
        self .scroll_q =ctk .CTkScrollableFrame (self .right_panel ,fg_color ="transparent");self .scroll_q .pack (fill ="both",expand =True ,padx =5 ,pady =(0 ,10 ))
        self .upd_ui ()

    def open_theme_editor (self ):
        try:
            self.update() # 刷新主窗口状态
            ThemeEditorWindow (self )
        except Exception as e:
            logger.error(f"无法打开主题编辑器: {e}")
    def on_sponsor_action_change (self ,choice ):
        self .upd_ui ();self .refresh_sb_display ()
        if "Off"not in choice :SponsorSelectWindow (self ,self .current_sponsor_cats ,self .update_sponsor_cats )
    def update_sponsor_cats (self ,cats ):self .current_sponsor_cats =cats ;self .refresh_sb_display ()
    def refresh_sb_display (self ):
        if self .c_sponsor_action .get ().startswith ("🙈"):self .l_sb_cats .configure (text ="")
        else :
            cn =[self .sb_cn_map .get (k ,k )for k in self .current_sponsor_cats ]
            txt ="、".join (cn );self .l_sb_cats .configure (text =f"[{txt[:12]}...]"if len (txt )>15 else f"[{txt}]")
    def open_batch_window (self ):BatchUrlWindow (self ,self .run_batch_add )
    def run_batch_add (self ,urls ):self .log (f"Batch processing {len(urls)} urls...","working");threading .Thread (target =self .batch_process_logic ,args =(urls ,),daemon =True ).start ()

    @safe_run 
    def batch_process_logic (self ,urls ):
        c =0 
        for u in urls :
            u =u .strip ();
            if not u :continue 
            self .log (f"Sniffing: {u}","working")
            # 总是尝试分析，即使失败也会创建基本元数据
            self .perform_analysis (u )
            self .add_to_queue_internal ();c +=1 
            time .sleep (0.5 )
        self .log (f"Batch done! Added {c} tasks.","done")

    def open_stats_window (self ):StatsWindow (self ,self .db )
    def open_template_window (self ):TemplateEditorWindow (self ,self .cfg ["tmpl_on"],self .cfg ["tmpl_str"],self .update_template_cfg )
    def update_template_cfg (self ,e ,s ):self .cfg ["tmpl_on"]=e ;self .cfg ["tmpl_str"]=s ;self .log (f"Naming template updated.","happy")
    def open_settings_window (self ):SettingsWindow (self ,self .update_paths_cfg )
    def update_paths_cfg (self ,y ,f ):self .cfg ['ytdlp_path']=y ;self .cfg ['ffmpeg_path']=f ;self .log ("Paths updated!","happy")

    def startup_maintenance (self ):
        # 先执行不需要UI的操作
        y_ok ,f_ok =False ,False 
        exe =self .cfg .get ('ytdlp_path','')or shutil .which ("yt-dlp")or "yt-dlp"
        if shutil .which ("yt-dlp")or os .path .exists (exe ):y_ok =True 
        if shutil .which ("ffmpeg"):f_ok =True 
        else :
            if self .cfg .get ('ffmpeg_path','')and os .path .exists (self .cfg ['ffmpeg_path']):f_ok =True 

        # 尝试清除缓存
        try:
            subprocess .run ([exe ,"--rm-cache-dir"],capture_output =True ,creationflags =subprocess .CREATE_NO_WINDOW if os .name =='nt'else 0 )
            # 缓存清除成功，稍后记录日志
            cache_cleared = True
        except:
            cache_cleared = False

        # 检查版本
        version_info = None
        try:
            res =subprocess .run ([exe ,"--version"],capture_output =True ,text =True ,creationflags =subprocess .CREATE_NO_WINDOW if os .name =='nt'else 0 )
            version_info = res.stdout.strip()
        except:
            version_info = None

        # 现在执行需要UI的操作
        def update_ui():
            try:
                # 记录初始化日志
                self .log ("Init environment...","working")
                
                # 记录缓存清除日志
                if cache_cleared:
                    self .log ("Cache cleared.","happy")
                
                # 处理缺失核心的情况
                if not y_ok or not f_ok :
                    msg =[]
                    if not y_ok :msg .append ("yt-dlp")
                    if not f_ok :msg .append ("ffmpeg")
                    self .log (f"Missing core: {', '.join(msg)}","sad")
                    if hasattr(self, 'l_version'):
                        self .l_version .configure (text ="Core Missing",text_color ="red")
                    self .after (0 ,lambda :[messagebox .showwarning ("Missing",f"Missing: {', '.join(msg)}"),self .open_settings_window ()])
                    return 
                
                # 更新版本信息
                if hasattr(self, 'l_version'):
                    if version_info:
                        self .l_version .configure (text =f"Core: {version_info}",text_color =CURRENT_THEME ["accent"])
                    else:
                        self .l_version .configure (text ="Unknown Ver",text_color ="gray")
                
                # 更新心情和显示
                self .mood_manager .update_logic ()
                if hasattr(self, 'update_mood_display'):
                    self .update_mood_display ()
            except Exception as e:
                logger.error(f"更新UI错误: {e}")
        
        # 在主线程中执行UI更新
        try:
            self .run_safe (update_ui)
        except Exception as e:
            logger.error(f"执行UI更新错误: {e}")
            # 如果失败，直接打印日志
            print(f"[LOG] Init environment...")
            if cache_cleared:
                print(f"[LOG] Cache cleared.")
            if not y_ok or not f_ok:
                msg =[]
                if not y_ok: msg.append("yt-dlp")
                if not f_ok: msg.append("ffmpeg")
                print(f"[LOG] Missing core: {', '.join(msg)}")

    def upd_ui (self ,_ =None ):
        st ="normal"if self .sw_proxy .get ()else "disabled"
        self .e_proxy_ip .configure (state =st );self .e_proxy_port .configure (state =st )

        if self .switch_time .get ():
            self .cut_box .pack (side ="left")
        else :
            self .cut_box .pack_forget ()

        m =self .seg_mode .get ()
        self .sw_embed .configure (state ="normal"if "最佳"in m or "手动"in m else "disabled")
        if "手动"in m or "字幕"in m :
            self .fmt_frame .pack (after =self .preview_frame ,fill ="x",padx =20 ,pady =10 )
            st ="normal"if self .current_meta else "disabled"
            
            if "字幕"in m :
                # 字幕模式：只显示字幕选择框
                self .c_video .pack_forget ()
                self .c_audio .pack_forget ()
                if hasattr(self, 'c_subtitle_manual'):
                    self .c_subtitle_manual .pack_forget ()
                if hasattr(self, 'c_subtitle_only'):
                    self .c_subtitle_only .pack (fill ="x",padx =10 ,pady =5 )
                    if hasattr(self, 'subtitle_opts'):
                        if self.subtitle_opts:
                            subtitle_labels = [opt[1] for opt in self.subtitle_opts]
                            self.c_subtitle_only.configure(values=subtitle_labels)
                            self.c_subtitle_only.set(subtitle_labels[0])
                        else:
                            self.c_subtitle_only.configure(values=["下载所有字幕"])
                            self.c_subtitle_only.set("下载所有字幕")
            else :
                # 手动模式：显示所有选择框
                if hasattr(self, 'c_video'):
                    self .c_video .pack (fill ="x",padx =10 ,pady =5 )
                if hasattr(self, 'c_audio'):
                    self .c_audio .pack (fill ="x",padx =10 ,pady =5 )
                if hasattr(self, 'c_subtitle_only'):
                    self .c_subtitle_only .pack_forget ()
                if hasattr(self, 'c_subtitle_manual'):
                    self .c_subtitle_manual .pack (fill ="x",padx =10 ,pady =5 )
                    # 手动模式：显示"不下载字幕"和"下载全部字幕"选项
                    if hasattr(self, 'subtitle_opts') and self.subtitle_opts:
                        subtitle_labels = ["不下载字幕", "下载全部字幕"] + [opt[1] for opt in self.subtitle_opts]
                        self.c_subtitle_manual.configure(values=subtitle_labels)
                        self.c_subtitle_manual.set("不下载字幕")
                    else:
                        self.c_subtitle_manual.configure(values=["不下载字幕", "下载全部字幕"])
                        self.c_subtitle_manual.set("不下载字幕")
                self .c_video .configure (state =st )
                self .c_audio .configure (state =st )
        else :self .fmt_frame .pack_forget ()
        if "聊天室"in m :
            self .chat_frame .pack (after =self .preview_frame ,fill ="x",padx =20 ,pady =10 )
            self .upd_chat_ui ()
        else :
            self .chat_frame .pack_forget ()

    def on_main_video_select (self ,choice ):
        info =self .video_infos .get (choice )
        if info and info ['has_audio']:
            self .c_audio .configure (state ="disabled")
            self .l_status .configure (text ="主人喵~ 这个视频自带声音，就不用再挑音轨啦~")
        else :
            self .c_audio .configure (state ="normal")
            self .l_status .configure (text ="待命中喵")

    def get_filter_text (self ):
        if not self .chat_filters :return "⚙️ 选择保留项..."
        display =", ".join ([f .capitalize ()for f in self .chat_filters ])
        if len (display )>20 :display =display [:20 ]+"..."
        return f"⚙️ 选择保留项... ({display})"

    def upd_chat_ui (self ):
        if self .chat_mode_var .get ()=="filter":
            self .btn_chat_filter .configure (text =self .get_filter_text ())
            self .btn_chat_filter .pack (pady =5 ,padx =30 ,anchor ="w")
        else :
            self .btn_chat_filter .pack_forget ()

    def open_filter_selector (self ):
        ChatFilterSelector (self ,self .chat_filters ,self .set_filters )

    def set_filters (self ,filters ):
        self .chat_filters =filters 
        self .upd_chat_ui ()

    def browse (self ):
        p =ctk .filedialog .askdirectory ()
        if p :self .e_dir .delete (0 ,"end");self .e_dir .insert (0 ,p )

    def refresh_cookies (self ):
        fs =["🚫 No Cookie","🔄 使用内置提取器"]+([f for f in os .listdir (COOKIES_DIR )if f .endswith ('.txt')]if os .path .exists (COOKIES_DIR )else [])
        self .c_cookie .configure (values =fs )
        self .c_cookie .set (self .cfg ["cookie"]if self .cfg ["cookie"]in fs else "🚫 No Cookie")
        self .update_browser_selector ()

    def update_browser_selector (self ,*args ):
        # 根据cookie选择状态显示或隐藏浏览器选择器
        if self .c_cookie .get ()=="🔄 使用内置提取器":
            # 放在net框架下方
            self .browser_frame .pack (fill ="x",padx =20 ,pady =5 ,after =self .net )
        else :
            self .browser_frame .pack_forget ()

    def log (self ,msg ,mood ="happy"):
        def _log():
            try:
                # 检查log_box是否存在
                if hasattr(self, 'log_box') and self.log_box:
                    emo ={"happy":["✨","🎵","✅"],"working":["🐾","🔍","💭"],"sad":["😿","🥀","⚠️"],"done":["🎉","💖","😽"]}.get (mood ,[""])
                    self .log_box .configure (state ="normal")
                    self .log_box .insert ("end",f"{msg} {random.choice(emo)}\n")
                    self .log_box .see ("end")
                    self .log_box .configure (state ="disabled")
                else:
                    # 如果log_box不存在，打印到控制台
                    print(f"[LOG] {msg}")
            except Exception as e:
                logger.error(f"日志记录错误: {e}")
        
        # 尝试在主线程中执行，如果失败则直接执行
        try:
            self .run_safe (_log)
        except Exception as e:
            logger.error(f"run_safe执行日志失败: {e}")
            # 直接执行
            _log()

    def start_thread (self ,func ):threading .Thread (target =func ,daemon =True ).start ()

    def get_cmd_base (self ,pon ,pip ,ppt ,ck ):
        exe =self .cfg .get ('ytdlp_path','')or "yt-dlp"
        cmd =[exe ,"--no-warnings","--ignore-errors","--encoding","utf-8"]
        if not shutil .which ("ffmpeg")and self .cfg .get ('ffmpeg_path'):cmd .extend (["--ffmpeg-location",self .cfg ['ffmpeg_path']])
        if pon and pip and ppt :cmd .extend (["--proxy",f"http://{pip}:{ppt}"])
        if "🚫"not in ck :
            if ck =="🔄 使用内置提取器":
                # 使用内置提取器
                browser =self .c_browser .get ()if hasattr (self ,'c_browser')else "chrome"
                cmd .extend (["--cookies-from-browser",browser ])
            else :
                # 使用传统cookie文件
                cp =os .path .join (COOKIES_DIR ,ck )
                if os .path .exists (cp ):cmd .extend (["--cookies",cp ])
        return cmd 

    @safe_run 
    def perform_analysis (self ,url ):
        self .log ("Sniffing metadata...","working")
        def gc ():return {"pon":self .sw_proxy .get (),"pip":self .e_proxy_ip .get (),"ppt":self .e_proxy_port .get (),"ck":self .c_cookie .get ()}
        c =self .run_safe (gc )
        self .run_safe (lambda :[self .l_info .configure (text ="Connecting..."),self .l_thumb .configure (image =None ,text ="...")])
        self .video_opts .clear ();self .audio_opts .clear ();self .video_infos .clear ()
        self .subtitle_opts =[]  # 存储字幕语言选项

        si =subprocess .STARTUPINFO ();si .dwFlags |=subprocess .STARTF_USESHOWWINDOW 
        cmd =self .get_cmd_base (c ["pon"],c ["pip"],c ["ppt"],c ["ck"])

        res =subprocess .run (cmd +["--dump-json",url ],capture_output =True ,text =True ,encoding ='utf-8',errors ='replace',startupinfo =si ,creationflags =subprocess .CREATE_NO_WINDOW if os .name =='nt'else 0 ,env ={**os .environ ,"PYTHONIOENCODING":"utf-8"})
        
        # 如果元数据抓取失败，创建一个基本的元数据对象，而不是抛出异常
        if res .returncode !=0 :
            self .log ("Metadata fetch failed, using basic info for download","sad")
            d = {
                "title": "Unknown Video",
                "uploader": "Unknown Uploader",
                "webpage_url": url,
                "formats": [],
                "thumbnail": None
            }
        else :
            try :
                d =json .loads (res .stdout .split ('\n')[0 ])
            except :
                self .log ("Metadata parse failed, using basic info for download","sad")
                d = {
                    "title": "Unknown Video",
                    "uploader": "Unknown Uploader",
                    "webpage_url": url,
                    "formats": [],
                    "thumbnail": None
                }
        tr =None 
        if 'thumbnail'in d :
            px =None 
            if c ["pon"]:px ={'http':f"http://{c['pip']}:{c['ppt']}",'https':f"http://{c['pip']}:{c['ppt']}"}
            op =urllib .request .build_opener (urllib .request .ProxyHandler (px ))if px else urllib .request .build_opener ()
            op .addheaders =[('User-Agent','Mozilla/5.0')]
            urllib .request .install_opener (op )
            try :tr =urllib .request .urlopen (d ['thumbnail'],timeout =10 ).read ()
            except :pass 

        v_list ,a_list =[],[]
        if 'formats'in d :
            for f in d ['formats']:
                fid =f .get ('format_id')
                if not fid :continue 
                if f .get ('vcodec')and f .get ('vcodec')!='none':
                    h =f .get ('height',0 )or 0 
                    br =f .get ('tbr')or f .get ('vbr')or 0 
                    fps =f .get ('fps',0 )
                    vc =f .get ('vcodec','')
                    ac =f .get ('acodec','none')
                    ext =f .get ('ext','')
                    has_audio =(ac and ac !='none')
                    label =f"{h}P | {ext} | {vc} | {int(br)}k"
                    if has_audio :label +=" | 🔊"
                    label +=f" | ID:{fid}"
                    v_list .append ({'h':h ,'br':br ,'label':label ,'id':fid ,'has_audio':has_audio })
                    self .video_infos [label ]={'has_audio':has_audio ,'id':fid }

                if f .get ('acodec')and f .get ('acodec')!='none'and f .get ('vcodec')=='none':
                    abr =f .get ('abr',0 )or 0 
                    ac =f .get ('acodec','')
                    ext =f .get ('ext','')
                    label =f"{int(abr)}k | {ext} | {ac} | ID:{fid}"
                    a_list .append ({'abr':abr ,'label':label ,'id':fid })

        # 解析字幕语言
        self .log ("Checking subtitles...","working")
        try:
            # 使用 --list-subs 命令获取字幕信息
            subs_cmd = cmd + ["--list-subs", url]
            subs_res = subprocess.run(subs_cmd, capture_output=True, text=True, 
                                   encoding='utf-8', errors='replace', 
                                   startupinfo=si, 
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0, 
                                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            
            if subs_res.returncode == 0:
                subs_output = subs_res.stdout
                # 解析字幕信息
                lines = subs_output.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('['):
                        # 格式示例: "zh-Hans" (Chinese (Simplified)) -- [VTT] (automatic)
                        parts = line.split(' -- ')
                        if len(parts) >= 2:
                            lang_info = parts[0].strip()
                            sub_info = parts[1].strip()
                            # 提取语言代码和名称
                            lang_match = re.search(r'"([^"]+)"\s+\(([^\)]+)\)', lang_info)
                            if lang_match:
                                lang_code = lang_match.group(1)
                                lang_name = lang_match.group(2)
                                # 检查是否是自动生成的
                                is_auto = 'automatic' in sub_info.lower()
                                label = f"{lang_name} ({lang_code})"
                                if is_auto:
                                    label += " [自动]"
                                else:
                                    label += " [手动]"
                                self.subtitle_opts.append((lang_code, label, is_auto))
                
                if self.subtitle_opts:
                    self.log(f"Found {len(self.subtitle_opts)} subtitle languages","happy")
                else:
                    self.log("No subtitles found","sad")
        except Exception as e:
            logger.error(f"Error parsing subtitles: {e}")
            self.log("Failed to check subtitles","sad")

        v_list .sort (key =lambda x :(x ['h'],x ['br']),reverse =True )
        a_list .sort (key =lambda x :x ['abr'],reverse =True )
        v_labels =[x ['label']for x in v_list ]
        a_labels =[x ['label']for x in a_list ]

        def upd ():
            self .current_meta =d ;self .last_analyzed_url =url 
            if tr :
                self .current_thumb_img =ctk .CTkImage (Image .open (io .BytesIO (tr )),size =(160 ,90 ))
                self .l_thumb .configure (image =self .current_thumb_img ,text ="")
                self .l_thumb .image =self .current_thumb_img  # 双重保险，防止图片被垃圾回收
            else :
                self .current_thumb_img =None 
                self .l_thumb .configure (image =None ,text ="No Image")
                self .l_thumb .image =None  # 清除引用

            self .video_opts ={x ['label']:x ['id']for x in v_list }
            self .audio_opts ={x ['label']:x ['id']for x in a_list }

            self .c_video .configure (values =v_labels if v_labels else ["No Video"])
            self .c_audio .configure (values =a_labels if a_labels else ["No Audio"])

            if v_labels :self .c_video .set (v_labels [0 ])
            if a_labels :self .c_audio .set (a_labels [0 ])
            self .on_main_video_select (self .c_video .get ())

            # 更新字幕选择框
            if hasattr(self, 'c_subtitle'):
                m = self.seg_mode.get() if hasattr(self, 'seg_mode') else ""
                if self.subtitle_opts:
                    # 所有模式都添加"不下载字幕"选项
                    subtitle_labels = ["不下载字幕"] + [opt[1] for opt in self.subtitle_opts]
                    self.c_subtitle.configure(values=subtitle_labels)
                    self.c_subtitle.set("不下载字幕")
                else:
                    self.c_subtitle.configure(values=["不下载字幕"])
                    self.c_subtitle.set("不下载字幕")

            self .l_info .configure (text =f"Title: {d.get('title','?')}\nUP: {d.get('uploader','?')}")
            if 'entries'in d or d .get ('_type')=='playlist':self .sw_list .select ()
            self .upd_ui ();self .log (f"Analyzed: {d.get('title','?')[:15]}...","happy")
        self .run_safe (upd )
        return True 

    def analyze_ui_wrapper (self ):
        u =self .run_safe (lambda :self .e_url .get ().strip ())
        if u :self .perform_analysis (u )

    def smart_add_flow (self ):
        u =self .run_safe (lambda :self .e_url .get ().strip ())
        if not u :return 
        if (u !=self .last_analyzed_url )or (self .current_meta is None ):
            # 总是尝试分析，即使失败也会创建基本元数据
            self .perform_analysis (u )
            if "手动"in self .run_safe (self .seg_mode .get ):
                self .log ("Ready for manual selection...","happy");return 
        self .add_to_queue_internal ()

    def add_to_queue_internal (self ):
        def _add ():
            if not self .current_meta :return 
            cfg ,desc =self .build_current_config ()
            if len (self .queue_items )==0 :self .paned .add (self .right_panel ,minsize =320 ,stretch ="always")

            item =ctk .CTkFrame (self .scroll_q ,fg_color =CURRENT_THEME ["panel_bg"],corner_radius =10 );item .pack (fill ="x",pady =5 )
            img =ctk .CTkImage (self .current_thumb_img ._light_image ,size =(80 ,45 ))if self .current_thumb_img else None 
            ctk .CTkLabel (item ,text ="",image =img ,width =80 ).pack (side ="left",padx =5 ,pady =5 )
            tf =ctk .CTkFrame (item ,fg_color ="transparent");tf .pack (side ="left",fill ="both",expand =True ,padx =5 )
            ctk .CTkLabel (tf ,text =self .current_meta .get ('title','?'),font =FONT_Q_TITLE ,anchor ="w",text_color =CURRENT_THEME ["text"]).pack (fill ="x",expand =True )
            dl =ctk .CTkLabel (tf ,text =desc ,font =FONT_Q_DESC ,text_color ="gray",anchor ="w");dl .pack (fill ="x",expand =True )
            lbl =ctk .CTkLabel (item ,text ="Queued",font =("微软雅黑",10 ),text_color ="gray");lbl .pack (side ="right",padx =10 )

            pkt ={"config":cfg ,"label":lbl ,"desc_label":dl ,"status":"waiting","meta":self .current_meta ,"widget":item }
            self .queue_items .append (pkt )

            def pop (e ):
                m =tk .Menu (self ,tearoff =0 )
                m .add_command (label ="✏️ Edit",command =lambda :self .edit_queue_item (pkt ))
                m .add_command (label ="🗑️ Delete",command =lambda :self .delete_queue_item (pkt ))
                m .tk_popup (e .x_root ,e .y_root )
            def rb (w ):w .bind ("<Button-3>",pop );[rb (c )for c in w .winfo_children ()]
            rb (item )
            self .log (f"Added: {self.current_meta.get('title','?')[:15]}...","done")
        self .run_safe (_add )

    def delete_queue_item (self ,i ):
        if i in self .queue_items :self .queue_items .remove (i );i ['widget'].destroy ();self .log ("Deleted.","sad")

    def edit_queue_item (self ,i ):
        def save (o ,n ):
            o ['config']=n ;desc =[]
            o ['desc_label'].configure (text ="Edited")
            self .log ("Task updated.","happy")
        TaskEditWindow (self ,i ,save )

    def download_now_flow (self ):
        u =self .run_safe (lambda :self .e_url .get ().strip ())
        if not u :return 
        if (u !=self .last_analyzed_url )or (self .current_meta is None ):
            # 总是尝试分析，即使失败也会创建基本元数据
            self .perform_analysis (u )
            if "手动"in self .run_safe (self .seg_mode .get ):self .log ("Select format first...","happy");return 
        cfg ,_ =self .run_safe (self .build_current_config )
        self .log ("Direct downloading...","working")
        self .run_safe (lambda :[self .btn_now .configure (state ="disabled"),self .btn_add .configure (state ="disabled")])

        session_id =self .generate_session_id (cfg ['url'],cfg ['dir'])
        temp_file =self .find_current_temp_file (cfg ,self .current_meta )

        session_dict =None 
        if temp_file :
            session_dict ={
            'session_id':session_id ,
            'url':cfg ['url'],
            'output_path':cfg ['dir'],
            'temp_file':temp_file 
            }
            self .log ("Detected partial file, attempting resume...","working")

        suc =self .download_item_with_resume (cfg ,self .current_meta ,session_dict )

        self .run_safe (lambda :[self .btn_now .configure (state ="normal"),self .btn_add .configure (state ="normal")])
        if suc :
            show_windows_toast ("Neko","Done!");self .log ("Done!","done")
            self .mood_manager .report_success ()
        else :
            self .log ("Failed.","sad")
            self .mood_manager .report_fail ()
        self .run_safe (lambda :self .l_status .configure (text ="待命中喵"))
        self .update_mood_display ()

    def build_current_config (self ):
        m =self .seg_mode .get ()
        desc =[m ]
        if "手动"in m :desc .append (f"{self.c_video.get().split('|')[0]}")
        if self .sw_embed .get ():desc .append ("+Sub")
        if self .switch_time .get ():desc .append (f"Cut({self.e_start_h.get()}:{self.e_start_m.get()}:{self.e_start_s.get()})")


        aid =self .audio_opts .get (self .c_audio .get ())
        if "手动"in m and self .c_audio .cget ("state")=="disabled":
            aid =None 

        # 确保current_meta存在，如果不存在则创建一个基本的元数据对象
        if not hasattr(self, 'current_meta') or self.current_meta is None:
            self.current_meta = {
                "title": "Unknown Video",
                "uploader": "Unknown Uploader",
                "webpage_url": self.e_url.get() if hasattr(self, 'e_url') else "",
                "formats": [],
                "thumbnail": None
            }

        # 获取选中的字幕语言
        selected_subtitle = ""
        is_subtitle_mode = "字幕" in m
        if is_subtitle_mode:
            # 字幕模式：使用 c_subtitle_only
            selected_subtitle = self.c_subtitle_only.get() if hasattr(self, 'c_subtitle_only') else "下载所有字幕"
        else:
            # 手动模式：使用 c_subtitle_manual
            selected_subtitle = self.c_subtitle_manual.get() if hasattr(self, 'c_subtitle_manual') else "不下载字幕"
        
        subtitle_lang = None
        if not is_subtitle_mode:
            if selected_subtitle == "不下载字幕":
                subtitle_lang = None
            elif selected_subtitle == "下载全部字幕":
                # 下载全部字幕：不指定语言代码，让 yt-dlp 下载所有字幕
                subtitle_lang = "all"
            else:
                if hasattr(self, 'subtitle_opts') and self.subtitle_opts:
                    for lang_code, label, is_auto in self.subtitle_opts:
                        if label == selected_subtitle:
                            subtitle_lang = lang_code
                            break
        else:
            if hasattr(self, 'subtitle_opts') and self.subtitle_opts:
                for lang_code, label, is_auto in self.subtitle_opts:
                    if label == selected_subtitle:
                        subtitle_lang = lang_code
                        break

        # 获取浏览器选择器的值
        browser =self .c_browser .get ()if hasattr (self ,'c_browser')else "chrome"
        
        return {
        "url":self .current_meta .get ("webpage_url",self .e_url .get ()),
        "dir":self .e_dir .get (),"mode":m ,"proxy_on":self .sw_proxy .get (),
        "proxy_ip":self .e_proxy_ip .get (),"proxy_port":self .e_proxy_port .get (),
        "cookie":self .c_cookie .get (),"browser":browser ,"playlist":self .sw_list .get (),"embed":self .sw_embed .get (),
        "sb_act":self .c_sponsor_action .get (),"sb_cats":self .current_sponsor_cats ,
        "v_id":self .video_opts .get (self .c_video .get ()),"a_id":aid ,
        "tmpl_on":self .cfg ["tmpl_on"],"tmpl_str":self .cfg ["tmpl_str"],
        "ytdlp_path":self .cfg .get ('ytdlp_path',''),"ffmpeg_path":self .cfg .get ('ffmpeg_path',''),
        "chat_mode":self .chat_mode_var .get ()if hasattr (self ,'chat_mode_var')else "full",
        "chat_filters":self .chat_filters if hasattr (self ,'chat_filters')else ["author","message","timestamp"],
        "time_range_on":self .switch_time .get (),
        "start_h":self .e_start_h .get (),"start_m":self .e_start_m .get (),"start_s":self .e_start_s .get (),
        "end_h":self .e_end_h .get (),"end_m":self .e_end_m .get (),"end_s":self .e_end_s .get (),
        "subtitle_lang":subtitle_lang
        }," ".join (desc )

    def process_queue (self ):
        q =[i for i in self .queue_items if i ['status']=='waiting']
        if not q :self .log ("篮子空空的喵…","sad");return 
        self .run_safe (lambda :[self .btn_add .configure (state ="disabled"),self .btn_start .configure (state ="disabled")])
        self .log (f"Processing {len(q)} items...","working")
        sem =threading .Semaphore (self .max_concurrent );ths =[]
        for i ,it in enumerate (q ):
            t =threading .Thread (target =self ._dw ,args =(it ,sem ),daemon =True );t .start ();ths .append (t )
        for t in ths :t .join ()
        self .run_safe (lambda :[self .btn_add .configure (state ="normal"),self .btn_start .configure (state ="normal"),self .l_status .configure (text ="Finished")])
        self .log ("全部叼回窝里啦喵！","done");show_windows_toast ("Neko","Queue finished!")
        self .mood_manager .interact ()
        self .mood_manager .update_logic ()
        self .update_mood_display ()

    @safe_run 
    def _dw (self ,it ,sem ):
        with sem :
            self .run_safe (lambda :it ['label'].configure (text ="Running",text_color ="orange"))
            it ['status']='running'

            cfg =it ['config']
            session_id =self .generate_session_id (cfg ['url'],cfg ['dir'])
            temp_file =self .find_current_temp_file (cfg ,it ['meta'])
            session_dict =None 
            if temp_file :
                session_dict ={
                'session_id':session_id ,
                'url':cfg ['url'],
                'output_path':cfg ['dir'],
                'temp_file':temp_file 
                }

            ok =self .download_item_with_resume (cfg ,it ['meta'],session_dict )

            c ,t =("green","Done")if ok else ("red","Error")
            self .run_safe (lambda :it ['label'].configure (text =t ,text_color =c ))
            it ['status']='done'if ok else 'error'
            if ok :self .mood_manager .download_success_today +=1 

    @safe_run 
    def download_item_with_resume (self ,cfg ,meta ,resume_session =None ):
        session_id =resume_session ['session_id']if resume_session else self .generate_session_id (cfg ['url'],cfg ['dir'])
        self .db .save_resume_session (
        session_id =session_id ,
        url =cfg ['url'],
        output_path =cfg ['dir'],
        temp_file =self .get_expected_filename (cfg ,meta )+".part",
        downloaded_bytes =0 ,
        total_bytes =0 ,
        download_params =cfg ,
        title =meta .get ('title','Unknown')
        )

        output_template =cfg ['tmpl_str']if cfg ['tmpl_on']else "%(title)s.%(ext)s"

        # 获取浏览器选择器的值
        if not hasattr (self ,'c_browser'):
            # 如果浏览器选择器还未创建，创建它
            self .update_browser_selector ()
        
        # 确保浏览器选择器的值被正确设置
        if 'browser' in cfg:
            browser = cfg['browser']
            if hasattr (self ,'c_browser'):
                self .c_browser .set (browser )
        
        cmd =self .get_cmd_base (cfg ["proxy_on"],cfg ["proxy_ip"],cfg ["proxy_port"],cfg ["cookie"])
        cmd .extend ([
        "--continue",
        "--no-part",
        "-N","8",
        "-P",cfg ["dir"],
        "-o",f"{output_template}",
        "--windows-filenames","--no-mtime","--embed-thumbnail","--embed-metadata","--newline"
        ])

        sb =cfg .get ("sb_act","")
        if "Mark"in sb :cmd .extend (["--sponsorblock-mark","all","--embed-chapters"])
        elif "Remove"in sb :cmd .extend (["--sponsorblock-remove","all"])

        m =cfg ["mode"]
        if "字幕"in m :
            cmd .extend (["--skip-download","--write-subs","--write-auto-subs"])
            # 添加字幕语言选择
            subtitle_lang = cfg.get("subtitle_lang")
            if subtitle_lang and subtitle_lang != "all":
                cmd.extend(["--sub-langs", subtitle_lang])
        elif "声音"in m :cmd .extend (["-f","bestaudio/best","--extract-audio","--audio-format","mp3"])
        elif "直播"in m :cmd .extend (["--wait-for-video","15","--live-from-start"])
        elif "聊天室"in m :
            cmd .extend (["--write-sub","--sub-langs","live_chat","--skip-download"])
        elif "手动"in m :
            v ,a =cfg .get ("v_id"),cfg .get ("a_id")
            if v and a :cmd .extend (["-f",f"{v}+{a}"])
            elif v :cmd .extend (["-f",f"{v}+bestaudio"])
            else :cmd .extend (["-f","bestvideo+bestaudio/best"])
        else :cmd .extend (["-f","bestvideo+bestaudio/best"])

        if cfg .get ("embed"):
            subtitle_lang = cfg.get("subtitle_lang")
            if subtitle_lang:
                cmd .extend (["--write-subs","--write-auto-subs","--embed-subs"])
                if subtitle_lang != "all":
                    cmd.extend(["--sub-langs", subtitle_lang])

        if cfg .get ("time_range_on"):
            start_str =f"{cfg.get('start_h', '00')}:{cfg.get('start_m', '00')}:{cfg.get('start_s', '00')}"
            end_str =f"{cfg.get('end_h', '00')}:{cfg.get('end_m', '00')}:{cfg.get('end_s', '00')}"
            cmd .extend (["--download-sections",f"*{start_str}-{end_str}"])

        cmd .append ("--yes-playlist"if cfg ["playlist"]else "--no-playlist")
        cmd .append (cfg ["url"])

        return self .execute_download_with_progress (cmd ,cfg ,meta ,session_id )

    def process_chat_filtering (self ,json_file ,filters ):
        try :
            filtered_file =json_file .replace (".live_chat.json",".filtered.json")
            if filtered_file ==json_file :filtered_file +=".json"

            output_data =[]
            with open (json_file ,'r',encoding ='utf-8')as f :
                for line in f :
                    try :
                        data =json .loads (line )
                        if 'replayChatItemAction'not in data :continue 
                        actions =data ['replayChatItemAction']['actions']
                        for action in actions :
                            if 'addChatItemAction'not in action :continue 
                            item =action ['addChatItemAction']['item']

                            renderer =None 
                            msg_type ="normal"
                            if 'liveChatTextMessageRenderer'in item :
                                renderer =item ['liveChatTextMessageRenderer']
                            elif 'liveChatPaidMessageRenderer'in item :
                                renderer =item ['liveChatPaidMessageRenderer']
                                msg_type ="paid"

                            if not renderer :continue 

                            entry ={}
                            if "author"in filters :
                                entry ['author']=renderer .get ('authorName',{}).get ('simpleText','Unknown')

                            if "message"in filters :
                                runs =renderer .get ('message',{}).get ('runs',[])
                                entry ['message']="".join ([r .get ('text','')for r in runs ])

                            if "timestamp"in filters :
                                entry ['timestamp']=renderer .get ('timestampUsec','0')

                            if "money"in filters and msg_type =="paid":
                                entry ['money']=renderer .get ('purchaseAmountText',{}).get ('simpleText','')

                            if "badges"in filters :
                                badges =renderer .get ('authorBadges',[])
                                entry ['badges']=[b .get ('liveChatAuthorBadgeRenderer',{}).get ('tooltip','')for b in badges ]

                            output_data .append (entry )
                    except :continue 

            if output_data :
                with open (filtered_file ,'w',encoding ='utf-8')as f :
                    json .dump (output_data ,f ,indent =2 ,ensure_ascii =False )
                return True 
        except Exception as e :
            print (f"Chat filter error: {e}")
            return False 
        return False 

    def execute_download_with_progress (self ,cmd ,cfg ,meta ,session_id ):
        p =subprocess .Popen (cmd ,stdout =subprocess .PIPE ,stderr =subprocess .STDOUT ,text =True ,encoding ='utf-8',errors ='replace',startupinfo =subprocess .STARTUPINFO (),creationflags =subprocess .CREATE_NO_WINDOW if os .name =='nt'else 0 ,env ={**os .environ ,"PYTHONIOENCODING":"utf-8"})

        rp ,rs ,rsp ,ret =re .compile (r"(\d+\.?\d*)%"),re .compile (r"of\s+(\S+)"),re .compile (r"at\s+(\S+)"),re .compile (r"ETA\s+(\S+)")
        st =time .time ()
        last_save_time =0 
        final_file_path =None 

        re_merge =re .compile (r'\[Merger\] Merging formats into "(.*?)"')
        re_dest =re .compile (r'\[download\] Destination: (.*)')
        re_exist =re .compile (r'\[download\] (.*?) has already been downloaded')

        for l in p .stdout :
            if "Merger"in l :
                if m :=re_merge .search (l ):final_file_path =m .group (1 )
            elif "Destination:"in l :
                if m :=re_dest .search (l ):final_file_path =m .group (1 )
            elif "has already been downloaded"in l :
                if m :=re_exist .search (l ):final_file_path =m .group (1 )

            if "[download]"in l and "%"in l :
                if mp :=rp .search (l ):
                    pct =float (mp .group (1 ))
                    self .run_safe (lambda :self .prog .set (pct /100 ))
                    txt =f"{pct}%"

                    if ms :=rs .search (l ):
                        size_str =ms .group (1 )
                        txt +=f" | {size_str}"

                    if msp :=rsp .search (l ):txt +=f" | {msp.group(1)}"
                    if me :=ret .search (l ):txt +=f" | {me.group(1)}"

                    self .run_safe (lambda :self .l_status .configure (text =txt ))

                    if time .time ()-last_save_time >2 :
                        temp_file =self .find_current_temp_file (cfg ,meta )
                        if temp_file and os .path .exists (temp_file ):
                            current_size =os .path .getsize (temp_file )
                            self .save_resume_state (session_id ,cfg ,meta ,current_size ,0 )
                            last_save_time =time .time ()

            elif not any (x in l for x in ["[download]","Deleting"]):self .log (l .strip ())

        p .wait ()
        self .run_safe (lambda :self .prog .set (1 if p .returncode ==0 else 0 ))

        if p .returncode ==0 :
            if "聊天室"in cfg .get ("mode","")and cfg .get ("chat_mode")=="filter":
                base_name =self .get_expected_filename (cfg ,meta )
                json_candidates =glob .glob (f"{base_name}*.live_chat.json")
                if json_candidates :
                    json_file =json_candidates [0 ]
                    self .log ("Filtering chat data...","working")
                    if self .process_chat_filtering (json_file ,cfg .get ("chat_filters",[])):
                        try :os .remove (json_file )
                        except :pass 

            if meta :
                fs =0 
                if final_file_path :
                    if not os .path .isabs (final_file_path ):
                        final_file_path =os .path .join (cfg ['dir'],final_file_path )
                    if os .path .exists (final_file_path ):
                        try :fs =os .path .getsize (final_file_path )
                        except :pass 

                if fs ==0 :
                    fs =meta .get ('filesize',0 )or meta .get ('filesize_approx',0 )

                self .db .add_record (meta ,fs ,time .time ()-st )
            self .db .complete_resume_session (session_id )
            return True 
        else :
            return False 

# 多线程UI加载器
class UILoader:
    def __init__(self, cache_manager):
        self.cache_manager = cache_manager
        self.loading_screen = None
        self.main_app = None
        self.load_thread = None
        self.loading_completed = False
        self.error_message = None
        
    def start_loading(self):
        # 创建临时root窗口作为LoadingScreen的父窗口
        temp_root = ctk.CTk()
        temp_root.withdraw()  # 隐藏临时窗口
        
        self.loading_screen = LoadingScreen(temp_root)
        
        # 启动加载线程
        threading.Thread(target=self._prepare_app, daemon=True).start()
        
        # 启动进度轮询
        self.loading_screen.process_updates()
        # 启动状态检查逻辑
        self.check_loading_status()
        
        # 进入加载屏的主循环
        self.loading_screen.mainloop()
        
        # 销毁临时root窗口
        try:
            temp_root.destroy()
        except:
            pass
        
        # --- 关键修改：确保加载屏完全消失后再判断是否启动主程序 ---
        if self.error_message:
            self.show_error_and_exit(self.error_message)
            return

        # 手动清理一次 Tkinter 的全局状态
        import tkinter as tk
        tk._default_root = None  
        
        try:
            # 实例化主程序
            self.main_app = NekoDownloader(cached_data=self.cached_data_ref)
            self.main_app.mainloop()
        except Exception as e:
            self.show_error_and_exit(f"主程序启动崩溃: {e}")
        
    def check_loading_status(self):
        """每100毫秒检查一次加载是否完成"""
        if self.loading_completed:
            self.loading_screen.close() # 这会触发 mainloop 停止
        else:
            if self.loading_screen.winfo_exists():
                self.loading_screen.after(100, self.check_loading_status)
        
    def _prepare_app(self):
        """准备应用数据"""
        try:
            # 检查并更新 ytdlp
            self.update_progress_safe(0.2, "检查 ytdlp 版本...")
            if not self.check_and_update_ytdlp():
                self.error_message = "ytdlp 更新失败"
                self.loading_completed = True
                return
            
            self.update_progress_safe(0.7, "加载缓存数据...")
            self.cached_data_ref = self.cache_manager.load_cache()
            
            self.update_progress_safe(0.9, "完成初始化...")
            # 模拟加载进度（确保 UI 有时间渲染）
            time.sleep(0.2)
            self.loading_completed = True
        except Exception as e:
            self.error_message = str(e)
            self.loading_completed = True
    
    def check_and_update_ytdlp(self):
        """检查并更新 ytdlp 到最新版本"""
        try:
            import subprocess
            import json
            import urllib.request
            import os
            import shutil
            
            # 获取当前 ytdlp 版本
            current_version = None
            ytdlp_path = shutil.which("yt-dlp") or "yt-dlp"
            
            try:
                result = subprocess.run([ytdlp_path, "--version"], capture_output=True, text=True, 
                                      creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                if result.returncode == 0:
                    current_version = result.stdout.strip()
                    logger.info(f"当前 ytdlp 版本: {current_version}")
                else:
                    logger.warning("无法获取当前 ytdlp 版本")
            except Exception as e:
                logger.error(f"检查 ytdlp 版本失败: {e}")
                return True  # 失败时继续启动
            
            # 获取最新版本信息
            self.update_progress_safe(0.3, "获取最新版本信息...")
            try:
                url = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
                with urllib.request.urlopen(url, timeout=10) as response:
                    data = json.loads(response.read().decode())
                    latest_version = data.get("tag_name", "").lstrip("v")
                    logger.info(f"最新 ytdlp 版本: {latest_version}")
            except Exception as e:
                logger.error(f"获取最新版本信息失败: {e}")
                return True  # 失败时继续启动
            
            # 比较版本
            if current_version and latest_version and current_version != latest_version:
                logger.info(f"需要更新 ytdlp: {current_version} -> {latest_version}")
                self.update_progress_safe(0.4, f"更新 ytdlp 到 v{latest_version}...")
                
                # 执行更新
                try:
                    update_cmd = [ytdlp_path, "--update"]
                    result = subprocess.run(update_cmd, capture_output=True, text=True, 
                                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    if result.returncode == 0:
                        logger.info("ytdlp 更新成功")
                        self.update_progress_safe(0.6, "ytdlp 更新成功")
                    else:
                        logger.error(f"ytdlp 更新失败: {result.stderr}")
                        # 尝试手动下载（如果更新失败）
                        if os.name == 'nt':
                            self.update_progress_safe(0.5, "尝试手动下载...")
                            try:
                                # 下载最新版本
                                download_url = f"https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
                                with urllib.request.urlopen(download_url, timeout=30) as response:
                                    with open("yt-dlp.exe", "wb") as f:
                                        f.write(response.read())
                                # 替换旧版本
                                if shutil.which("yt-dlp"):
                                    os.replace("yt-dlp.exe", shutil.which("yt-dlp"))
                                logger.info("ytdlp 手动更新成功")
                                self.update_progress_safe(0.6, "ytdlp 手动更新成功")
                            except Exception as e:
                                logger.error(f"手动下载失败: {e}")
                                return False
                except Exception as e:
                    logger.error(f"执行更新失败: {e}")
                    return False
            else:
                logger.info("ytdlp 已是最新版本")
                self.update_progress_safe(0.6, "ytdlp 已是最新版本")
            
            return True
        except Exception as e:
            logger.error(f"检查并更新 ytdlp 时发生错误: {e}")
            return True  # 失败时继续启动
    
    def load_ui_components(self):
        """后台加载逻辑"""
        self._prepare_app()
    
    def update_progress_safe(self, value, status=""):
        """安全更新进度"""
        if self.loading_screen:
            try:
                # 使用后端的 queue 传递
                self.loading_screen.update_progress(value, status)
            except:
                pass
    
    def create_main_app(self, cached_data=None):
        """在主线程中创建主应用"""
        def _create():
            try:
                # 确保在主线程中创建
                if threading.current_thread() is threading.main_thread():
                    self.main_app = NekoDownloader(cached_data=cached_data)
                    # 保存缓存
                    if hasattr(self.main_app, 'get_cache_data'):
                        cache_data = self.main_app.get_cache_data()
                        self.cache_manager.save_cache(cache_data)
                else:
                    logger.error("创建主应用必须在主线程中执行")
                    # 如果不在主线程，直接执行
                    self.main_app = NekoDownloader(cached_data=cached_data)
                    if hasattr(self.main_app, 'get_cache_data'):
                        cache_data = self.main_app.get_cache_data()
                        self.cache_manager.save_cache(cache_data)
            except Exception as e:
                logger.error(f"创建主应用错误: {e}")
                self.error_message = str(e)
                self.loading_completed = True
        
        if self.loading_screen and self.loading_screen.window:
            try:
                if self.loading_screen.window.winfo_exists():
                    # 使用安全的after方法
                    self.loading_screen.safe_after(0, _create)
            except Exception as e:
                logger.error(f"在主线程中创建主应用错误: {e}")
                # 如果失败，直接在当前线程创建
                _create()
    
    def show_main_app(self):
        """显示主应用"""
        if self.loading_screen:
            try:
                self.loading_screen.close()
            except Exception as e:
                logger.error(f"关闭加载屏错误: {e}")
        
        # 主应用的mainloop将在start_loading的末尾调用
    
    def show_error_and_exit(self, error_msg):
        """显示错误并退出"""
        if self.loading_screen:
            try:
                self.loading_screen.close()
            except Exception as e:
                logger.error(f"关闭加载屏错误: {e}")
        
        try:
            error_window = ctk.CTk()
            error_window.title("初始化错误")
            error_window.geometry("400x200")
            
            error_label = ctk.CTkLabel(
                error_window,
                text=f"初始化失败:\n{error_msg}",
                font=("微软雅黑", 12),
                text_color="red"
            )
            error_label.pack(expand=True, pady=20)
            
            ok_button = ctk.CTkButton(
                error_window,
                text="确定",
                command=error_window.destroy,
                fg_color="#FF69B4",
                hover_color="#FF1493"
            )
            ok_button.pack(pady=10)
            
            error_window.mainloop()
        except Exception as e:
            logger.error(f"显示错误窗口错误: {e}")

def main():
    """主函数 - 支持作为模块运行"""
    try:
        # 创建缓存管理器
        cache_manager = CacheManager()
        
        # 检查是否有代码更新
        if not cache_manager.is_cache_valid():
            logger.info("检测到代码更新，清除旧缓存")
            cache_manager.clear_cache()
        
        # 创建UI加载器并启动
        ui_loader = UILoader(cache_manager)
        ui_loader.start_loading()
        
    except Exception as e:
        logger.error(f"程序启动失败: {e}")
        # 显示错误对话框
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("启动失败", f"程序启动失败:\n{str(e)}")
        root.destroy()
        sys.exit(1)

if __name__ =="__main__":
    main()
