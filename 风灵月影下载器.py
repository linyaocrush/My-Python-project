"""
FLiNG Trainer 猫娘下载器 - Aurora Mint Glassmorphism（CustomTkinter）
--------------------------------------------------------------------
修复：
- CustomTkinter 的 place() 不能传 width/height：改用 grid 布局，并把 width/height 放到构造/configure。
- GlassCard 阴影层 place 不再传 width/height（改用 configure 后 place）。

新增设置项：
- 是否自动解压（默认开）
- 是否解压后删除压缩包（默认关）

依赖：
  pip install customtkinter requests beautifulsoup4

可选解压依赖：
- 7z：pip install py7zr
- rar：pip install rarfile （并确保系统有 unrar/bsdtar）

"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import sqlite3
import threading
import time
import webbrowser
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, Future

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import customtkinter as ctk
import requests
from bs4 import BeautifulSoup


APP_NAME = "风灵月影下载器（Aurora Mint 猫娘版）"
BASE_URL = "https://flingtrainer.com/"
SEARCH_URL = "https://flingtrainer.com/?s={query}"

# --- Aurora Mint Palette ---
MINT = "#B4F8C8"
FOG_SILVER = "#E5E7EB"
LAVENDER_MIST = "#F3E8FF"
ROSE_MIST = "#FFF0F5"
INK = "#0B1220"
CARD_BG = "#F8FAFC"
CARD_BORDER = "#FFFFFF"
DANGER = "#EF4444"


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', "_", name).strip()
    return name or f"download_{int(time.time())}"


def human_bytes(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024.0:
            return f"{num:.1f} {unit}" if unit != "B" else f"{num} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"


# ----------------------------
# Config & Storage
# ----------------------------

@dataclass
class AppConfig:
    proxy_enabled: bool = False
    proxy_url: str = ""
    download_threads: int = 3
    download_dir: str = ""

    auto_extract_enabled: bool = True
    delete_archive_after_extract: bool = False

    def normalized(self) -> "AppConfig":
        cfg = AppConfig(**asdict(self))
        if not cfg.download_dir:
            cfg.download_dir = str(Path.home() / "Downloads" / "FLiNG")
        cfg.download_threads = max(1, min(int(cfg.download_threads), 16))
        cfg.auto_extract_enabled = bool(cfg.auto_extract_enabled)
        cfg.delete_archive_after_extract = bool(cfg.delete_archive_after_extract)
        return cfg


class ConfigManager:
    def __init__(self, data_dir: Path):
        self.data_dir = ensure_dir(data_dir)
        self.path = self.data_dir / "config.json"

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig().normalized()
        try:
            obj = json.loads(self.path.read_text("utf-8"))
            return AppConfig(**obj).normalized()
        except Exception:
            return AppConfig().normalized()

    def save(self, cfg: AppConfig) -> None:
        cfg = cfg.normalized()
        self.path.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), "utf-8")


class DB:
    def __init__(self, data_dir: Path):
        self.data_dir = ensure_dir(data_dir)
        self.db_path = self.data_dir / "app.db"
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL UNIQUE,
                    url TEXT NOT NULL,
                    added_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    file TEXT NOT NULL,
                    saved_path TEXT NOT NULL,
                    downloaded_at TEXT NOT NULL
                );
                """
            )
            conn.commit()

    # Favorites
    def list_favorites(self) -> List[Tuple[int, str, str, str]]:
        with self._conn() as conn:
            cur = conn.execute("SELECT id, title, url, added_at FROM favorites ORDER BY id DESC;")
            return list(cur.fetchall())

    def is_favorite(self, url: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("SELECT 1 FROM favorites WHERE url=? LIMIT 1;", (url,))
            return cur.fetchone() is not None

    def add_favorite(self, title: str, url: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO favorites(title, url, added_at) VALUES(?,?,?);",
                (title, url, now_str()),
            )
            conn.commit()

    def remove_favorite(self, url: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM favorites WHERE url=?;", (url,))
            conn.commit()

    # History
    def add_history(self, url: str, title: str, file: str, saved_path: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO history(url, title, file, saved_path, downloaded_at) VALUES(?,?,?,?,?);",
                (url, title, file, saved_path, now_str()),
            )
            conn.commit()

    def list_history(self, limit: int = 200) -> List[Tuple[int, str, str, str, str, str]]:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT id, url, title, file, saved_path, downloaded_at FROM history ORDER BY id DESC LIMIT ?;",
                (limit,),
            )
            return list(cur.fetchall())

    def clear_history(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM history;")
            conn.commit()


# ----------------------------
# Web Client
# ----------------------------

@dataclass
class SearchResult:
    title: str
    url: str


@dataclass
class DownloadItem:
    file: str
    url: str
    date_added: str
    file_size: str
    downloads: str


class FlingClient:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg.normalized()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            }
        )
        self.apply_config(self.cfg)

    def apply_config(self, cfg: AppConfig) -> None:
        self.cfg = cfg.normalized()
        if self.cfg.proxy_enabled and self.cfg.proxy_url.strip():
            proxy = self.cfg.proxy_url.strip()
            self.session.proxies = {"http": proxy, "https": proxy}
        else:
            self.session.proxies = {}

    def _get(self, url: str) -> str:
        r = self.session.get(url, timeout=25)
        r.raise_for_status()
        r.encoding = r.encoding or "utf-8"
        return r.text

    def latest_home_title(self) -> str:
        html = self._get(BASE_URL)
        soup = BeautifulSoup(html, "html.parser")
        a = soup.select_one("h2.post-title a")
        return a.get_text(strip=True) if a else ""

    def search(self, query: str) -> List[SearchResult]:
        q = query.strip()
        if not q:
            return []
        url = SEARCH_URL.format(query=requests.utils.quote(q))
        html = self._get(url)
        soup = BeautifulSoup(html, "html.parser")

        results: List[SearchResult] = []
        for a in soup.select("h2.post-title a, article h2 a[rel=bookmark]"):
            title = (a.get_text(strip=True) or "").strip()
            href = (a.get("href") or "").strip()
            if not title or not href:
                continue
            if "/trainer/" not in href:
                continue
            results.append(SearchResult(title=title, url=href))

        uniq: Dict[str, SearchResult] = {}
        for r in results:
            uniq[r.url] = r
        return list(uniq.values())

    def parse_downloads(self, trainer_url: str) -> Tuple[str, List[DownloadItem]]:
        html = self._get(trainer_url)
        soup = BeautifulSoup(html, "html.parser")

        title = soup.select_one("h1.post-title")
        title_text = title.get_text(strip=True) if title else "Trainer"

        downloads: List[DownloadItem] = []
        table = soup.select_one(".download-attachments table.da-attachments-table")
        if not table:
            return title_text, downloads

        for tr in table.select("tbody tr"):
            a = tr.select_one("a.attachment-link")
            if not a:
                continue

            file_name = a.get_text(strip=True) or "download"
            href = (a.get("href") or "").strip()
            href = requests.compat.urljoin(trainer_url, href)

            td_date = tr.select_one("td.attachment-date")
            td_size = tr.select_one("td.attachment-size")
            td_dls = tr.select_one("td.attachment-downloads")
            date_added = td_date.get_text(strip=True) if td_date else ""
            file_size = td_size.get_text(strip=True) if td_size else ""
            dls = td_dls.get_text(strip=True) if td_dls else ""

            tds = tr.find_all("td")
            if (not date_added or not file_size or not dls) and len(tds) >= 4:
                date_added = date_added or tds[1].get_text(strip=True)
                file_size = file_size or tds[2].get_text(strip=True)
                dls = dls or tds[3].get_text(strip=True)

            downloads.append(
                DownloadItem(
                    file=file_name,
                    url=href,
                    date_added=date_added,
                    file_size=file_size,
                    downloads=dls,
                )
            )
        return title_text, downloads

    def download_file(
        self,
        url: str,
        dest_dir: Path,
        preferred_name: str,
        progress_cb: Callable[[int, Optional[int], float], None],
        cancel_event: threading.Event,
    ) -> Path:
        ensure_dir(dest_dir)

        with self.session.get(url, stream=True, allow_redirects=True, timeout=40) as r:
            r.raise_for_status()

            filename = preferred_name.strip()
            cd = r.headers.get("content-disposition", "")
            m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, re.IGNORECASE)
            if m:
                filename = m.group(1)

            if not filename:
                filename = Path(requests.utils.urlparse(r.url).path).name or "download.bin"

            filename = sanitize_filename(filename)
            tmp_path = dest_dir / f"{filename}.part"
            final_path = dest_dir / filename

            total = r.headers.get("content-length")
            total_int: Optional[int] = int(total) if total and total.isdigit() else None

            downloaded = 0
            t0 = time.time()
            last_t = t0
            last_bytes = 0

            with open(tmp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 512):
                    if cancel_event.is_set():
                        raise RuntimeError("用户取消了下载喵~")
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    if now - last_t >= 0.2:
                        speed = (downloaded - last_bytes) / max(now - last_t, 1e-6)
                        progress_cb(downloaded, total_int, speed)
                        last_t = now
                        last_bytes = downloaded

            speed = downloaded / max(time.time() - t0, 1e-6)
            progress_cb(downloaded, total_int, speed)

            if final_path.exists():
                stem = final_path.stem
                suf = final_path.suffix
                final_path = dest_dir / f"{stem}_{int(time.time())}{suf}"
            tmp_path.replace(final_path)
            return final_path


# ----------------------------
# UI Helpers
# ----------------------------

class CatToast:
    @staticmethod
    def info(title: str, msg: str) -> None:
        messagebox.showinfo(title=f"{title} ฅ^•ﻌ•^ฅ", message=msg)

    @staticmethod
    def warn(title: str, msg: str) -> None:
        messagebox.showwarning(title=f"{title} ฅ(•́ﻌ•̀)ฅ", message=msg)

    @staticmethod
    def err(title: str, msg: str) -> None:
        messagebox.showerror(title=f"{title} ฅ(>﹏<)ฅ", message=msg)


class GlassCard(ctk.CTkFrame):
    """浅色雾面 + 边框 + 伪阴影（hover）"""
    def __init__(self, master, corner_radius: int = 24, **kwargs):
        super().__init__(
            master,
            corner_radius=corner_radius,
            fg_color=CARD_BG,
            border_width=1,
            border_color=CARD_BORDER,
            **kwargs
        )
        self._corner_radius = corner_radius
        self._shadow = ctk.CTkFrame(master, corner_radius=corner_radius, fg_color="#D1D5DB")
        self._shadow.lower(self)
        self._shadow.place_forget()
        self._hovered = False

        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")
        self.bind("<Configure>", self._on_configure, add="+")

    def _on_configure(self, _evt=None):
        try:
            x = self.winfo_x()
            y = self.winfo_y()
            w = self.winfo_width()
            h = self.winfo_height()
            if w > 1 and h > 1:
                offset = 0 if not self._hovered else 3
                # IMPORTANT: do NOT pass width/height into place() for customtkinter
                self._shadow.configure(width=w, height=h)
                self._shadow.place(x=x + offset, y=y + offset)
        except Exception:
            pass

    def _on_enter(self, _evt=None):
        self._hovered = True
        self.configure(border_color=FOG_SILVER)
        self._on_configure()

    def _on_leave(self, _evt=None):
        self._hovered = False
        self.configure(border_color=CARD_BORDER)
        self._on_configure()


class RippleButton(ctk.CTkFrame):
    """轻量涟漪按钮（Canvas 扩散圆）"""
    def __init__(self, master, text: str, command: Callable, width: int = 120, height: int = 36):
        super().__init__(master, corner_radius=18, fg_color=MINT, width=width, height=height)
        self.command = command
        self._btn_w = width
        self._btn_h = height
        self.pack_propagate(False)

        self.canvas = tk.Canvas(self, width=width, height=height, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.configure(bg=MINT)

        self.canvas.create_text(width // 2, height // 2, text=text, fill=INK, font=("Segoe UI", 11, "bold"))

        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<Enter>", lambda e: self._hover(True))
        self.canvas.bind("<Leave>", lambda e: self._hover(False))

        self._ripples: List[int] = []

    def _hover(self, on: bool):
        bg = "#A6F3BE" if on else MINT
        self.canvas.configure(bg=bg)
        self.configure(fg_color=bg)

    def _btn_hover(self, on: bool):
        # backward-compatible alias
        return self._hover(on)

    def _click(self, evt):
        x, y = evt.x, evt.y
        rid = self.canvas.create_oval(x, y, x, y, outline="", fill="#D1FAE5")
        self._ripples.append(rid)

        steps = 16
        max_r = max(self._btn_w, self._btn_h) * 1.1

        def animate(i=0):
            if i >= steps or rid not in self._ripples:
                try:
                    self.canvas.delete(rid)
                except Exception:
                    pass
                if rid in self._ripples:
                    self._ripples.remove(rid)
                return
            r = (i / steps) * max_r
            self.canvas.coords(rid, x - r, y - r, x + r, y + r)
            if i > steps * 0.6:
                self.canvas.itemconfig(rid, fill="#ECFEFF")
            self.after(16, lambda: animate(i + 1))

        animate()
        self.after(60, self.command)


class AuroraBackground(tk.Canvas):
    """动态极光背景：渐变带 + 相位偏移"""
    def __init__(self, master, **kwargs):
        super().__init__(master, highlightthickness=0, bd=0, **kwargs)
        self._phase = 0.0
        self._running = True
        self.bind("<Configure>", lambda e: self._draw())

    def stop(self):
        self._running = False

    @staticmethod
    def _lerp(a: int, b: int, t: float) -> int:
        return int(a + (b - a) * t)

    @staticmethod
    def _hex_to_rgb(h: str):
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    @staticmethod
    def _rgb_to_hex(rgb):
        return "#{:02x}{:02x}{:02x}".format(*rgb)

    def _blend(self, c1: str, c2: str, t: float) -> str:
        r1, g1, b1 = self._hex_to_rgb(c1)
        r2, g2, b2 = self._hex_to_rgb(c2)
        return self._rgb_to_hex((self._lerp(r1, r2, t), self._lerp(g1, g2, t), self._lerp(b1, b2, t)))

    def _draw(self):
        self.delete("all")
        w = max(self.winfo_width(), 2)
        h = max(self.winfo_height(), 2)

        stops = [MINT, LAVENDER_MIST, ROSE_MIST, FOG_SILVER, MINT]
        bands = 70

        for i in range(bands):
            t = i / (bands - 1)
            tt = (t + self._phase) % 1.0
            seg = int(tt * (len(stops) - 1))
            seg_t = (tt * (len(stops) - 1)) - seg
            c = self._blend(stops[seg], stops[seg + 1], seg_t)
            y0 = int(i * h / bands)
            y1 = int((i + 1) * h / bands) + 1
            self.create_rectangle(0, y0, w, y1, outline="", fill=c)

    def start(self):
        def tick():
            if not self._running:
                return
            self._phase = (self._phase + 0.0015) % 1.0
            self._draw()
            self.after(90, tick)

        tick()


# ----------------------------
# Download Window
# ----------------------------

class DownloadWindow(ctk.CTkToplevel):
    def __init__(self, master: tk.Misc, item: DownloadItem,
                 on_success: Callable[[Path], None]):
        super().__init__(master)
        self.title(f"下载中喵~  {item.file}")
        self.geometry("560x210")
        self.resizable(False, False)

        self.item = item
        self.cancel_event = threading.Event()
        self.q: "queue.Queue[Tuple[int, Optional[int], float]]" = queue.Queue()
        self.on_success = on_success

        card = GlassCard(self, corner_radius=24)
        card.pack(fill="both", expand=True, padx=14, pady=14)

        self.label = ctk.CTkLabel(card, text=f"正在抓取：{item.file}\n别急喵~我会努力的！", text_color=INK)
        self.label.pack(padx=14, pady=(14, 8), anchor="w")

        self.progress = ctk.CTkProgressBar(card, progress_color=MINT)
        self.progress.pack(fill="x", padx=14, pady=8)
        self.progress.set(0)

        self.status = ctk.CTkLabel(card, text="0 B / ?   速度：0 B/s", text_color=INK)
        self.status.pack(padx=14, pady=(0, 8), anchor="w")

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.pack(fill="x", padx=14, pady=(2, 12))

        self.btn_cancel = RippleButton(btns, text="取消喵", command=self._cancel, width=110, height=36)
        self.btn_cancel.pack(side="right")

        self.future: Optional[Future] = None
        self.after(120, self._poll)

        self._sweep_on = True
        self.after(180, self._sweep)

    def _sweep(self):
        if not self.winfo_exists():
            return
        self.progress.configure(progress_color=("#A6F3BE" if self._sweep_on else MINT))
        self._sweep_on = not self._sweep_on
        self.after(900, self._sweep)

    def begin_download(self, start_fn: Callable[[Callable], Future]) -> None:
        def progress_cb(downloaded: int, total: Optional[int], speed: float):
            self.q.put((downloaded, total, speed))

        self.future = start_fn(progress_cb)

        def done_cb(fut: Future):
            try:
                path = fut.result()
                self.after(0, lambda: self._done_ok(path))
            except Exception as e:
                self.after(0, lambda: self._done_err(str(e)))

        self.future.add_done_callback(done_cb)

    def _poll(self) -> None:
        try:
            while True:
                downloaded, total, speed = self.q.get_nowait()
                if total and total > 0:
                    self.progress.set(min(downloaded / total, 1.0))
                    self.status.configure(
                        text=f"{human_bytes(downloaded)} / {human_bytes(total)}   速度：{human_bytes(int(speed))}/s"
                    )
                else:
                    self.progress.set(0.0)
                    self.status.configure(text=f"{human_bytes(downloaded)} / ?   速度：{human_bytes(int(speed))}/s")
        except queue.Empty:
            pass

        if self.winfo_exists():
            self.after(120, self._poll)

    def _cancel(self) -> None:
        self.cancel_event.set()
        self.status.configure(text="正在取消…喵")

    def _done_ok(self, path: Path) -> None:
        self.progress.set(1.0)
        self.status.configure(text=f"完成啦喵！已保存到：{path}")
        CatToast.info("下载完成", f"搞定！文件在这里喵：\n{path}")
        try:
            self.on_success(path)
        finally:
            self.destroy()

    def _done_err(self, err: str) -> None:
        self.status.configure(text=f"失败喵：{err}")
        CatToast.err("下载失败", err)
        self.destroy()


# ----------------------------
# Pages
# ----------------------------

class HomePage(ctk.CTkFrame):
    def __init__(self, master: tk.Misc, app: "App"):
        super().__init__(master, fg_color="transparent")
        self.app = app

        title = ctk.CTkLabel(self, text="主页喵~ 请输入游戏名来搜修改器！",
                             font=ctk.CTkFont(size=18, weight="bold"), text_color=INK)
        title.pack(padx=18, pady=(18, 10), anchor="w")

        card = GlassCard(self)
        card.pack(fill="x", padx=18, pady=(0, 12))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=14)

        self.entry = ctk.CTkEntry(row, placeholder_text="比如：SILENT HILL f",
                                  fg_color="#FFFFFF", text_color=INK, border_color=FOG_SILVER)
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry.bind("<Return>", lambda e: self.do_search())

        self.btn = RippleButton(row, text="搜一下喵！", command=self.do_search, width=130, height=36)
        self.btn.pack(side="left")

        tip = ctk.CTkLabel(self, text="提示：结果来自 flingtrainer.com（网络慢的话就多等等喵~）", text_color=INK)
        tip.pack(padx=18, pady=(0, 10), anchor="w")

        self.results_frame = ctk.CTkScrollableFrame(self, label_text="搜索结果（点进去喵）",
                                                    fg_color="transparent", label_text_color=INK)
        self.results_frame.pack(fill="both", expand=True, padx=18, pady=(0, 18))

    def clear_results(self) -> None:
        for w in self.results_frame.winfo_children():
            w.destroy()

    def do_search(self) -> None:
        q = self.entry.get().strip()
        if not q:
            CatToast.warn("空空的", "你还没输入关键词喵~")
            return

        self.app.set_status("搜索中喵…")
        self.clear_results()

        def task():
            return self.app.client.search(q)

        def done(fut: Future):
            try:
                results = fut.result()
            except Exception as e:
                CatToast.err("搜索失败", str(e))
                self.app.set_status("搜索失败喵…")
                return

            if not results:
                CatToast.info("没有找到", f"呜呜…没搜到「{q}」，换个词试试喵？")
                self.app.set_status("没搜到结果喵…")
                return

            self.app.set_status(f"找到 {len(results)} 条结果喵~")

            for r in results:
                card = GlassCard(self.results_frame)
                card.pack(fill="x", padx=10, pady=8)

                left = ctk.CTkFrame(card, fg_color="transparent")
                left.pack(side="left", fill="x", expand=True, padx=12, pady=12)

                ctk.CTkLabel(left, text=r.title, anchor="w", text_color=INK).pack(anchor="w")

                RippleButton(card, text="打开喵", command=lambda url=r.url: self.app.open_trainer(url),
                             width=92, height=34).pack(side="right", padx=12, pady=12)

        fut = self.app.fetch_executor.submit(task)
        fut.add_done_callback(lambda f: self.app.safe_ui(lambda: done(f)))


class FavoritesPage(ctk.CTkFrame):
    def __init__(self, master: tk.Misc, app: "App"):
        super().__init__(master, fg_color="transparent")
        self.app = app

        ctk.CTkLabel(self, text="收藏喵~（你喜欢的修改器都在这）",
                     font=ctk.CTkFont(size=18, weight="bold"), text_color=INK)\
            .pack(padx=18, pady=(18, 10), anchor="w")

        self.frame = ctk.CTkScrollableFrame(self, label_text="收藏列表",
                                            fg_color="transparent", label_text_color=INK)
        self.frame.pack(fill="both", expand=True, padx=18, pady=18)
        self.refresh()

    def refresh(self) -> None:
        for w in self.frame.winfo_children():
            w.destroy()

        favs = self.app.db.list_favorites()
        if not favs:
            ctk.CTkLabel(self.frame, text="这里空空如也…快去收藏一个喵！", text_color=INK)\
                .pack(padx=12, pady=12, anchor="w")
            return

        for _id, title, url, added_at in favs:
            card = GlassCard(self.frame)
            card.pack(fill="x", padx=10, pady=8)

            left = ctk.CTkFrame(card, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True, padx=12, pady=12)

            ctk.CTkLabel(left, text=title, anchor="w", text_color=INK).pack(anchor="w")
            ctk.CTkLabel(left, text=f"收藏时间：{added_at}", anchor="w", text_color=INK,
                         font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(4, 0))

            RippleButton(card, text="打开喵", command=lambda u=url: self.app.open_trainer(u),
                         width=92, height=34).pack(side="right", padx=12, pady=12)

            ctk.CTkButton(card, text="移除", width=70, fg_color=FOG_SILVER, text_color=INK,
                          hover_color="#D1D5DB", command=lambda u=url: self._remove(u))\
                .pack(side="right", padx=(0, 8), pady=12)

    def _remove(self, url: str) -> None:
        self.app.db.remove_favorite(url)
        self.refresh()
        CatToast.info("移除完成", "已从收藏里拿走啦喵~")


class HistoryPage(ctk.CTkFrame):
    def __init__(self, master: tk.Misc, app: "App"):
        super().__init__(master, fg_color="transparent")
        self.app = app

        ctk.CTkLabel(self, text="历史记录喵~（你下载过的都在这）",
                     font=ctk.CTkFont(size=18, weight="bold"), text_color=INK)\
            .pack(padx=18, pady=(18, 10), anchor="w")

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(0, 8))
        ctk.CTkButton(top, text="清空历史", fg_color=FOG_SILVER, text_color=INK,
                      hover_color="#D1D5DB", command=self.clear).pack(side="right")

        self.frame = ctk.CTkScrollableFrame(self, label_text="最近下载",
                                            fg_color="transparent", label_text_color=INK)
        self.frame.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self.refresh()

    def refresh(self) -> None:
        for w in self.frame.winfo_children():
            w.destroy()

        rows = self.app.db.list_history()
        if not rows:
            ctk.CTkLabel(self.frame, text="还没有下载记录喵~", text_color=INK)\
                .pack(padx=12, pady=12, anchor="w")
            return

        for _id, url, title, file, saved_path, downloaded_at in rows:
            card = GlassCard(self.frame)
            card.pack(fill="x", padx=10, pady=8)

            left = ctk.CTkFrame(card, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True, padx=12, pady=12)

            ctk.CTkLabel(left, text=title, text_color=INK, anchor="w").pack(anchor="w")
            ctk.CTkLabel(left, text=f"文件：{file}", text_color=INK, anchor="w",
                         font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(4, 0))
            ctk.CTkLabel(left, text=f"时间：{downloaded_at}", text_color=INK, anchor="w",
                         font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(2, 0))

            RippleButton(card, text="打开 Trainer", command=lambda u=url: self.app.open_trainer(u),
                         width=110, height=34).pack(side="right", padx=12, pady=12)

            ctk.CTkButton(card, text="打开文件夹", width=110, fg_color=FOG_SILVER, text_color=INK,
                          hover_color="#D1D5DB", command=lambda p=saved_path: self._open_folder(p))\
                .pack(side="right", padx=(0, 8), pady=12)

    def _open_folder(self, saved_path: str) -> None:
        p = Path(saved_path)
        folder = p.parent if p.exists() else Path(saved_path).parent
        try:
            os.startfile(folder)  # Windows
        except Exception:
            webbrowser.open(folder.as_uri())

    def clear(self):
        if messagebox.askyesno("清空历史 ฅ(•́ﻌ•̀)ฅ", "确定要清空所有历史记录吗喵？"):
            self.app.db.clear_history()
            self.refresh()
            CatToast.info("清空完成", "历史都清掉啦喵~")


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master: tk.Misc, app: "App"):
        super().__init__(master, fg_color="transparent")
        self.app = app

        ctk.CTkLabel(self, text="设置喵~（调一调更顺手）",
                     font=ctk.CTkFont(size=18, weight="bold"), text_color=INK)\
            .pack(padx=18, pady=(18, 10), anchor="w")

        card = GlassCard(self)
        card.pack(fill="x", padx=18, pady=10)

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=14)

        # proxy
        self.var_proxy = tk.BooleanVar(value=self.app.cfg.proxy_enabled)
        ctk.CTkSwitch(body, text="启用系统代理（HTTP/HTTPS）", variable=self.var_proxy,
                      progress_color=MINT, button_color=MINT, button_hover_color="#A6F3BE",
                      text_color=INK).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 6), columnspan=2)

        ctk.CTkLabel(body, text="代理地址：", text_color=INK).grid(row=1, column=0, sticky="w", padx=10, pady=6)
        self.entry_proxy = ctk.CTkEntry(body, placeholder_text="例如：http://127.0.0.1:7890",
                                        fg_color="#FFFFFF", text_color=INK, border_color=FOG_SILVER)
        self.entry_proxy.grid(row=1, column=1, sticky="ew", padx=10, pady=6)
        self.entry_proxy.insert(0, self.app.cfg.proxy_url or "")

        # threads
        ctk.CTkLabel(body, text="下载线程数：", text_color=INK).grid(row=2, column=0, sticky="w", padx=10, pady=6)
        self.entry_threads = ctk.CTkEntry(body, placeholder_text="1 - 16",
                                          fg_color="#FFFFFF", text_color=INK, border_color=FOG_SILVER)
        self.entry_threads.grid(row=2, column=1, sticky="ew", padx=10, pady=6)
        self.entry_threads.insert(0, str(self.app.cfg.download_threads))

        # download dir
        ctk.CTkLabel(body, text="下载目录：", text_color=INK).grid(row=3, column=0, sticky="w", padx=10, pady=6)
        self.entry_dir = ctk.CTkEntry(body, fg_color="#FFFFFF", text_color=INK, border_color=FOG_SILVER)
        self.entry_dir.grid(row=3, column=1, sticky="ew", padx=10, pady=6)
        self.entry_dir.insert(0, self.app.cfg.download_dir)

        ctk.CTkButton(body, text="选择…", width=90, fg_color=FOG_SILVER, text_color=INK,
                      hover_color="#D1D5DB", command=self.pick_dir)\
            .grid(row=3, column=2, sticky="e", padx=10, pady=6)

        # auto extract switches
        self.var_auto_extract = tk.BooleanVar(value=self.app.cfg.auto_extract_enabled)
        ctk.CTkSwitch(body, text="下载后自动解压", variable=self.var_auto_extract,
                      progress_color=MINT, button_color=MINT, button_hover_color="#A6F3BE",
                      text_color=INK).grid(row=4, column=0, sticky="w", padx=10, pady=(14, 6), columnspan=2)

        self.var_delete_archive = tk.BooleanVar(value=self.app.cfg.delete_archive_after_extract)
        ctk.CTkSwitch(body, text="解压成功后删除压缩包", variable=self.var_delete_archive,
                      progress_color=MINT, button_color=MINT, button_hover_color="#A6F3BE",
                      text_color=INK).grid(row=5, column=0, sticky="w", padx=10, pady=(2, 6), columnspan=2)

        body.grid_columnconfigure(1, weight=1)

        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.pack(fill="x", padx=14, pady=(0, 14))
        RippleButton(footer, text="保存设置喵！", command=self.save, width=140, height=38)\
            .pack(side="right")

    def pick_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.entry_dir.delete(0, tk.END)
            self.entry_dir.insert(0, path)

    def save(self) -> None:
        try:
            threads = int(self.entry_threads.get().strip() or "3")
        except ValueError:
            CatToast.warn("不太对喵", "下载线程数得是整数喵~")
            return

        cfg = AppConfig(
            proxy_enabled=bool(self.var_proxy.get()),
            proxy_url=self.entry_proxy.get().strip(),
            download_threads=threads,
            download_dir=self.entry_dir.get().strip(),
            auto_extract_enabled=bool(self.var_auto_extract.get()),
            delete_archive_after_extract=bool(self.var_delete_archive.get()),
        ).normalized()

        self.app.apply_new_config(cfg)
        CatToast.info("保存成功", "设置已保存啦喵~")


class TrainerPage(ctk.CTkFrame):
    def __init__(self, master: tk.Misc, app: "App"):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.current_url: Optional[str] = None
        self.current_title: str = ""
        self.items: List[DownloadItem] = []

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(18, 8))

        ctk.CTkButton(top, text="← 返回喵", width=110, fg_color=FOG_SILVER, text_color=INK,
                      hover_color="#D1D5DB", command=self.app.show_home).pack(side="left")

        self.lbl_title = ctk.CTkLabel(top, text="Trainer", font=ctk.CTkFont(size=18, weight="bold"),
                                      text_color=INK)
        self.lbl_title.pack(side="left", padx=12)

        self.btn_fav = ctk.CTkButton(top, text="☆ 收藏", width=90, fg_color=MINT, text_color=INK,
                                     hover_color="#A6F3BE", command=self.toggle_fav)
        self.btn_fav.pack(side="right", padx=(8, 0))

        ctk.CTkButton(top, text="在浏览器打开", width=120, fg_color=FOG_SILVER, text_color=INK,
                      hover_color="#D1D5DB", command=self.open_in_browser).pack(side="right")

        card = GlassCard(self)
        card.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        cols = ("file", "date", "size", "downloads")
        self.tree = ttk.Treeview(card, columns=cols, show="headings", height=12)
        self.tree.heading("file", text="File")
        self.tree.heading("date", text="Date added")
        self.tree.heading("size", text="File size")
        self.tree.heading("downloads", text="Downloads")

        self.tree.column("file", width=380, anchor="w")
        self.tree.column("date", width=140, anchor="center")
        self.tree.column("size", width=110, anchor="center")
        self.tree.column("downloads", width=110, anchor="center")

        vsb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=14)
        vsb.pack(side="right", fill="y", pady=14, padx=(0, 14))

        self.tree.bind("<Double-1>", self._on_double_click)

        ctk.CTkLabel(self, text="双击 File 开始下载喵~（并发下载数在设置里调）", text_color=INK)\
            .pack(padx=18, pady=(0, 18), anchor="w")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#FFFFFF", fieldbackground="#FFFFFF",
                        foreground="#111827", rowheight=30, bordercolor=FOG_SILVER, borderwidth=0)
        style.configure("Treeview.Heading", background=FOG_SILVER, foreground="#111827", relief="flat")
        style.map("Treeview", background=[("selected", "#D1FAE5")])

    def open(self, trainer_url: str) -> None:
        self.current_url = trainer_url
        self.current_title = ""
        self.items = []
        self.lbl_title.configure(text="加载中喵…")
        self._refresh_fav_button()
        self._clear_table()

        def task():
            return self.app.client.parse_downloads(trainer_url)

        def done(fut: Future):
            try:
                title, items = fut.result()
            except Exception as e:
                CatToast.err("打开失败", str(e))
                self.lbl_title.configure(text="打开失败喵…")
                return

            self.current_title = title
            self.items = items
            self.lbl_title.configure(text=title)

            self._refresh_fav_button()
            self._fill_table(items)

            if not items:
                CatToast.info("没有下载项", "这个页面的 Download 区域里没有可下载的文件喵~")

        fut = self.app.fetch_executor.submit(task)
        fut.add_done_callback(lambda f: self.app.safe_ui(lambda: done(f)))

    def _clear_table(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)

    def _fill_table(self, items: List[DownloadItem]) -> None:
        self._clear_table()
        for idx, it in enumerate(items):
            self.tree.insert("", "end", iid=str(idx),
                             values=(it.file, it.date_added, it.file_size, it.downloads))

    def _refresh_fav_button(self) -> None:
        if self.current_url and self.app.db.is_favorite(self.current_url):
            self.btn_fav.configure(text="★ 已收藏")
        else:
            self.btn_fav.configure(text="☆ 收藏")

    def toggle_fav(self) -> None:
        if not self.current_url:
            return
        if self.app.db.is_favorite(self.current_url):
            self.app.db.remove_favorite(self.current_url)
            CatToast.info("取消收藏", "唔…那我先放回去啦喵~")
        else:
            self.app.db.add_favorite(self.current_title or "Trainer", self.current_url)
            CatToast.info("收藏成功", "已收藏！以后我帮你看着喵~")
        self._refresh_fav_button()
        self.app.pages["favorites"].refresh()

    def open_in_browser(self) -> None:
        if self.current_url:
            webbrowser.open(self.current_url)

    def _on_double_click(self, _evt: tk.Event) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        try:
            it = self.items[int(iid)]
        except Exception:
            return
        self.app.start_download(it, trainer_url=self.current_url or "", trainer_title=self.current_title or "Trainer")


# ----------------------------
# App
# ----------------------------

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.base_dir = Path(__file__).resolve().parent
        self.data_dir = ensure_dir(self.base_dir / "data")
        self.last_title_path = self.data_dir / "last_title.txt"

        self.cfg_mgr = ConfigManager(self.data_dir)
        self.cfg = self.cfg_mgr.load()

        self.db = DB(self.data_dir)
        self.client = FlingClient(self.cfg)

        self.fetch_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="fetch")
        self.download_executor = ThreadPoolExecutor(max_workers=self.cfg.download_threads, thread_name_prefix="dl")

        self.title(APP_NAME)
        self.geometry("1100x720")
        self.minsize(940, 600)

        ctk.set_appearance_mode("Light")

        # background
        self.bg = AuroraBackground(self)
        self.bg.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.bg.start()

        # overlay
        self.overlay = ctk.CTkFrame(self, fg_color="transparent")
        self.overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.overlay.grid_rowconfigure(0, weight=1)
        self.overlay.grid_rowconfigure(1, weight=0)
        self.overlay.grid_columnconfigure(0, weight=0)
        self.overlay.grid_columnconfigure(1, weight=1)

        # sidebar + content (grid, fixed width)
        self.sidebar = GlassCard(self.overlay, width=210)
        self.sidebar.grid(row=0, column=0, sticky="nsw", padx=(18, 12), pady=(18, 12))

        self.content = ctk.CTkFrame(self.overlay, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=(0, 18), pady=(18, 12))

        # status bar
        self.status_var = tk.StringVar(value="喵~准备就绪！")
        status_card = GlassCard(self.overlay, corner_radius=18)
        status_card.configure(height=34)
        status_card.grid(row=1, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 18))
        status_card.grid_propagate(False)

        self.status = ctk.CTkLabel(status_card, textvariable=self.status_var, anchor="w", text_color=INK)
        self.status.pack(fill="both", padx=10)

        # build sidebar buttons
        self._build_sidebar()

        # pages
        self.pages: Dict[str, ctk.CTkFrame] = {
            "home": HomePage(self.content, self),
            "favorites": FavoritesPage(self.content, self),
            "history": HistoryPage(self.content, self),
            "settings": SettingsPage(self.content, self),
            "trainer": TrainerPage(self.content, self),
        }
        for p in self.pages.values():
            p.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.show_home()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # update check
        self.safe_ui(self._check_updates_async)

    def _build_sidebar(self) -> None:
        self.lbl_update = ctk.CTkLabel(self.sidebar, text="", text_color=DANGER, cursor="hand2")
        self.lbl_update.pack(padx=14, pady=(14, 0), anchor="w")
        self.lbl_update.bind("<Button-1>", lambda e: self._ack_open_official())

        ctk.CTkLabel(self.sidebar, text="🐾 Aurora Mint", font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=INK).pack(padx=14, pady=(10, 6), anchor="w")

        ctk.CTkLabel(self.sidebar, text="风灵月影下载器\n（非官方）", justify="left", text_color=INK)\
            .pack(padx=14, pady=(0, 14), anchor="w")

        ctk.CTkButton(self.sidebar, text="主页", command=self.show_home,
                      fg_color=MINT, text_color=INK, hover_color="#A6F3BE")\
            .pack(fill="x", padx=14, pady=6)

        ctk.CTkButton(self.sidebar, text="收藏", command=self.show_favorites,
                      fg_color=FOG_SILVER, text_color=INK, hover_color="#D1D5DB")\
            .pack(fill="x", padx=14, pady=6)

        ctk.CTkButton(self.sidebar, text="历史", command=self.show_history,
                      fg_color=FOG_SILVER, text_color=INK, hover_color="#D1D5DB")\
            .pack(fill="x", padx=14, pady=6)

        ctk.CTkButton(self.sidebar, text="设置", command=self.show_settings,
                      fg_color=FOG_SILVER, text_color=INK, hover_color="#D1D5DB")\
            .pack(fill="x", padx=14, pady=6)

        ctk.CTkLabel(self.sidebar, text="小提示：\n双击下载项就开下喵~",
                     font=ctk.CTkFont(size=12), justify="left", text_color=INK)\
            .pack(padx=14, pady=(18, 0), anchor="w")

    def safe_ui(self, fn: Callable[[], None]) -> None:
        self.after(0, fn)

    def set_status(self, text: str) -> None:
        if hasattr(self, "status_var"):
            self.status_var.set(text)

    def _show(self, key: str) -> None:
        self.pages[key].lift()

    def show_home(self) -> None:
        self._show("home")
        self.set_status("回到主页喵~")

    def show_favorites(self) -> None:
        self.pages["favorites"].refresh()
        self._show("favorites")
        self.set_status("打开收藏喵~")

    def show_history(self) -> None:
        self.pages["history"].refresh()
        self._show("history")
        self.set_status("打开历史记录喵~")

    def show_settings(self) -> None:
        self.pages["settings"].destroy()
        self.pages["settings"] = SettingsPage(self.content, self)
        self.pages["settings"].place(relx=0, rely=0, relwidth=1, relheight=1)
        self._show("settings")
        self.set_status("打开设置喵~")

    def open_trainer(self, url: str) -> None:
        self._show("trainer")
        self.set_status("加载 Trainer 页面中喵…")
        self.pages["trainer"].open(url)

    def apply_new_config(self, cfg: AppConfig) -> None:
        self.cfg = cfg.normalized()
        self.cfg_mgr.save(self.cfg)
        self.client.apply_config(self.cfg)

        try:
            self.download_executor.shutdown(wait=False, cancel_futures=False)
        except Exception:
            pass
        self.download_executor = ThreadPoolExecutor(max_workers=self.cfg.download_threads, thread_name_prefix="dl")
        self.set_status("设置已更新喵~")

    # ---- update check ----
    def _read_last_title(self) -> str:
        try:
            return self.last_title_path.read_text("utf-8").strip()
        except Exception:
            return ""

    def _write_last_title(self, t: str) -> None:
        try:
            self.last_title_path.write_text(t.strip(), "utf-8")
        except Exception:
            pass

    def _check_updates_async(self) -> None:
        def task():
            latest = self.client.latest_home_title()
            local = self._read_last_title()
            return latest, local

        def done(fut: Future):
            try:
                latest, local = fut.result()
            except Exception:
                return
            if not latest:
                return
            if not local:
                self._write_last_title(latest)
                return
            if latest != local:
                self.lbl_update.configure(text="有新 Trainer 喵！点我去看 →")
            else:
                self.lbl_update.configure(text="")

        fut = self.fetch_executor.submit(task)
        fut.add_done_callback(lambda f: self.safe_ui(lambda: done(f)))

    def _ack_open_official(self):
        try:
            latest = self.client.latest_home_title()
        except Exception:
            latest = ""
        webbrowser.open(BASE_URL)
        if latest:
            self._write_last_title(latest)
        self.lbl_update.configure(text="")
        self.set_status("已打开官网喵~（并标记为已读）")

    # ---- download ----
    def start_download(self, item: DownloadItem, trainer_url: str, trainer_title: str) -> None:
        dest_dir = Path(self.cfg.download_dir)
        ensure_dir(dest_dir)
        self.set_status(f"开始下载：{item.file} 喵~")

        def on_success(path: Path):
            # history
            try:
                self.db.add_history(trainer_url, trainer_title, item.file, str(path))
            except Exception:
                pass

            # auto extract (optional)
            if self.cfg.auto_extract_enabled:
                self._auto_extract_if_needed(path)

            self.set_status("下载完成喵~")

        win = DownloadWindow(self, item=item, on_success=on_success)

        def start_fn(progress_cb: Callable[[int, Optional[int], float], None]) -> Future:
            cancel_event = win.cancel_event

            def run():
                return self.client.download_file(
                    url=item.url,
                    dest_dir=dest_dir,
                    preferred_name=item.file,
                    progress_cb=progress_cb,
                    cancel_event=cancel_event,
                )

            return self.download_executor.submit(run)

        win.begin_download(start_fn)
        win.grab_set()

    def _auto_extract_if_needed(self, path: Path) -> None:
        ext = path.suffix.lower()
        if ext not in [".zip", ".7z", ".rar"]:
            return

        extract_dir = path.with_suffix("")
        ensure_dir(extract_dir)

        def maybe_delete():
            if self.cfg.delete_archive_after_extract:
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass

        try:
            if ext == ".zip":
                shutil.unpack_archive(str(path), str(extract_dir))
                maybe_delete()
                CatToast.info("自动解压完成", f"已解压到：\n{extract_dir}")
                return

            if ext == ".7z":
                try:
                    import py7zr  # type: ignore
                except Exception:
                    CatToast.warn("需要组件喵", "要解压 7z 请先安装：pip install py7zr")
                    return
                with py7zr.SevenZipFile(path, mode="r") as z:
                    z.extractall(path=extract_dir)
                maybe_delete()
                CatToast.info("自动解压完成", f"已解压到：\n{extract_dir}")
                return

            if ext == ".rar":
                try:
                    import rarfile  # type: ignore
                except Exception:
                    CatToast.warn("需要组件喵", "要解压 rar 请先安装：pip install rarfile\n并确保系统有 unrar/bsdtar")
                    return
                with rarfile.RarFile(path) as rf:
                    rf.extractall(extract_dir)
                maybe_delete()
                CatToast.info("自动解压完成", f"已解压到：\n{extract_dir}")
                return

        except Exception as e:
            CatToast.err("解压失败", f"下载成功但解压失败喵：\n{e}")

    def on_close(self) -> None:
        try:
            self.bg.stop()
        except Exception:
            pass
        try:
            self.fetch_executor.shutdown(wait=False, cancel_futures=False)
        except Exception:
            pass
        try:
            self.download_executor.shutdown(wait=False, cancel_futures=False)
        except Exception:
            pass
        self.destroy()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
