"""Port Check - kiểm tra mạng có chặn cổng POS/terminal PAX không + quét xem cổng nào đang mở.
Chạy:  python port_check.py     (cần: python -m pip install customtkinter)
"""
import sys, socket, time, json, threading, queue
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import customtkinter as ctk

RULES = Path(sys.argv[0]).resolve().parent / "portcheck_rules.json"
TERM = "{terminal}"
DEFAULT = [[1, "POS ⇄ PAX (LAN)", TERM, "10009"], [1, "PAX ⇄ TSYS", "portquiz.net", "5003"],
           [1, "PAX ⇄ FD", "portquiz.net", "443"], [1, "VX520 ⇄ Vantiv", "portquiz.net", "445"]]
STATUS = {"OPEN": ("MỞ - kết nối được", "#3ddc97", 0),
          "REFUSED": ("THÔNG - máy đích từ chối (đường đi không bị chặn)", "#7bd88f", 0),
          "TIMEOUT": ("CÓ THỂ BỊ CHẶN - không phản hồi (timeout)", "#ff6b6b", 1),
          "DNS": ("LỖI DNS - không phân giải được host", "#ffb454", 1),
          "UNREACH": ("KHÔNG TỚI ĐƯỢC", "#ff6b6b", 1)}
HINTS = {22: "SSH", 23: "Telnet", 53: "DNS", 80: "HTTP", 443: "HTTPS (PAX ⇄ FD)", 445: "SMB (VX520 ⇄ Vantiv)",
         3389: "Remote Desktop", 5003: "PAX ⇄ TSYS", 5555: "ADB (Android)", 8080: "HTTP phụ", 8443: "HTTPS phụ",
         9100: "Máy in", 10009: "POS ⇄ PAX (POSLink)"}
M0, M1, M2 = "Cổng POS/PAX thông dụng", "Toàn bộ 1–1024", "Tùy chọn (vd 80,443,5000-5010)"

def probe(host, port, timeout):
    t = time.perf_counter(); ms = lambda: round((time.perf_counter() - t) * 1000)
    try: socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror: return "DNS", ms(), ""
    try:
        with socket.create_connection((host, port), timeout=timeout): return "OPEN", ms(), ""
    except ConnectionRefusedError: return "REFUSED", ms(), ""
    except (TimeoutError, socket.timeout): return "TIMEOUT", ms(), ""
    except OSError as e: return "UNREACH", ms(), str(e)

def is_open(host, port, timeout):
    try:
        with socket.create_connection((host, port), timeout=timeout): return True
    except OSError: return False

def parse_ports(s):
    out = set()
    for part in s.replace(" ", "").split(","):
        if not part: continue
        a, _, b = part.partition("-"); lo = int(a); hi = int(b) if b else lo
        if not 1 <= lo <= hi <= 65535: raise ValueError(part)
        out.update(range(lo, hi + 1))
    if not out: raise ValueError("chưa nhập cổng")
    if len(out) > 10000: raise ValueError("tối đa 10000 cổng mỗi lần quét")
    return sorted(out)

class App(ctk.CTk):
    def __init__(self):
        super().__init__(); ctk.set_appearance_mode("dark"); ctk.set_default_color_theme("blue")
        self.title("Port Check - POS / PAX"); self.geometry("1000x640"); self.q = queue.Queue(); self.rows = []; self.scan_state = None
        top = ctk.CTkFrame(self, fg_color="transparent"); top.pack(fill="x", padx=14, pady=(12, 0))
        ctk.CTkLabel(top, text="IP terminal").pack(side="left")
        self.ip = ctk.CTkEntry(top, width=150, placeholder_text="192.168.1.100"); self.ip.pack(side="left", padx=8)
        ctk.CTkLabel(top, text="Timeout (giây)").pack(side="left", padx=(16, 0))
        self.to = ctk.CTkEntry(top, width=60); self.to.insert(0, "3"); self.to.pack(side="left", padx=8)
        tabs = ctk.CTkTabview(self); tabs.pack(fill="both", expand=True, padx=10, pady=8)
        self.build_check(tabs.add("Kiểm tra cổng bị chặn")); self.build_scan(tabs.add("Quét cổng đang mở"))
        self.after(100, self.pump)

    def pump(self):
        while not self.q.empty(): cb, r = self.q.get(); cb(r)
        self.after(100, self.pump)
    def tval(self, default=3.0):
        try: return float(self.to.get())
        except ValueError: return default

    # ---------- Tab 1: kiểm tra cổng có bị chặn ----------
    def build_check(self, tab):
        ctk.CTkLabel(tab, wraplength=920, justify="left", text_color="#8a93a3", text=
            "“{terminal}” = IP terminal ở trên (cổng trong LAN). “portquiz.net” là máy chủ mở mọi cổng, dùng để biết mạng có chặn cổng đó ra ngoài "
            "không; muốn kiểm tra đích thật, thay bằng host/IP của TSYS, FD, Vantiv. Kết quả phản ánh mạng của máy đang chạy tool.").pack(anchor="w", padx=8, pady=4)
        self.box = ctk.CTkScrollableFrame(tab); self.box.pack(fill="both", expand=True, padx=6, pady=4)
        try: rules = json.loads(RULES.read_text(encoding="utf-8"))
        except Exception: rules = DEFAULT
        for r in rules: self.add_rule(*r)
        self.sum = ctk.CTkLabel(tab, text="", font=("Segoe UI", 13, "bold")); self.sum.pack(anchor="w", padx=8)
        bar = ctk.CTkFrame(tab, fg_color="transparent"); bar.pack(fill="x", pady=8)
        self.run_btn = ctk.CTkButton(bar, text="Chạy kiểm tra", command=self.run); self.run_btn.pack(side="left", padx=4)
        ctk.CTkButton(bar, text="Thêm dòng", fg_color="#444", command=lambda: self.add_rule(1, "Mới", "portquiz.net", "443")).pack(side="left", padx=4)
        ctk.CTkButton(bar, text="Xóa dòng cuối", fg_color="#444", command=self.del_rule).pack(side="left", padx=4)
        ctk.CTkButton(bar, text="Sao chép báo cáo", fg_color="#444", command=self.copy).pack(side="left", padx=4)
    def add_rule(self, on, name, host, port):
        f = ctk.CTkFrame(self.box, fg_color="transparent"); f.pack(fill="x", pady=2)
        chk = ctk.CTkCheckBox(f, text="", width=24); chk.pack(side="left")
        if on: chk.select()
        e = [ctk.CTkEntry(f, width=w) for w in (190, 190, 70)]
        for w, v in zip(e, (name, host, port)): w.insert(0, v); w.pack(side="left", padx=3)
        res = ctk.CTkLabel(f, text="", anchor="w"); res.pack(side="left", padx=8); self.rows.append((f, chk, e, res))
    def del_rule(self):
        if self.rows: self.rows.pop()[0].destroy()
    def run(self):
        rules = [[c.get(), e[0].get(), e[1].get().strip(), e[2].get().strip()] for _, c, e, _ in self.rows]
        RULES.write_text(json.dumps(rules, ensure_ascii=False), encoding="utf-8")
        ip, to = self.ip.get().strip(), self.tval()
        for *_, res in self.rows: res.configure(text="...", text_color="#aaa")
        def one(i):
            on, _, host, port = rules[i]
            if not on: return i, None
            if host == TERM:
                if not ip: return i, ("NOIP", 0, "")
                host = ip
            try: return i, probe(host, int(port), to)
            except ValueError: return i, ("UNREACH", 0, "port không hợp lệ")
        def done(res):
            self.run_btn.configure(state="normal"); n = bad = 0
            for i, r in res:
                lab = self.rows[i][3]
                if r is None: lab.configure(text="bỏ qua", text_color="#888"); continue
                if r[0] == "NOIP": lab.configure(text="Chưa nhập IP terminal", text_color="#ffb454"); continue
                t, c, b = STATUS[r[0]]; n += 1; bad += b
                lab.configure(text=f"{t}  ({r[1]} ms) {r[2]}", text_color=c)
            self.sum.configure(text=f"Đã kiểm tra {n} cổng — " + (f"{bad} cổng nghi bị chặn." if bad else "không thấy cổng nào bị chặn."),
                               text_color="#ff6b6b" if bad else "#3ddc97")
        self.run_btn.configure(state="disabled")
        def bg():
            try:
                with ThreadPoolExecutor(8) as ex: r = list(ex.map(one, range(len(rules))))
            except Exception as e: r = []; print(e)
            self.q.put((done, r))
        threading.Thread(target=bg, daemon=True).start()
    def copy(self):
        self.clipboard_clear()
        self.clipboard_append("\n".join(f"{e[0].get()} | {e[1].get()}:{e[2].get()} | {r.cget('text')}" for _, _, e, r in self.rows))

    # ---------- Tab 2: quét cổng đang mở ----------
    def build_scan(self, tab):
        ctk.CTkLabel(tab, wraplength=920, justify="left", text_color="#8a93a3", text=
            "Quét xem host đó đang mở cổng nào. Để trống Host = dùng IP terminal ở trên (xem terminal đang mở cổng nào trong LAN). "
            "Nhập “portquiz.net” để biết mạng của bạn cho phép đi ra những cổng nào. Chỉ quét thiết bị/mạng của bạn hoặc máy chủ test.").pack(anchor="w", padx=8, pady=4)
        row = ctk.CTkFrame(tab, fg_color="transparent"); row.pack(fill="x", padx=6, pady=6)
        ctk.CTkLabel(row, text="Host").pack(side="left")
        self.s_host = ctk.CTkEntry(row, width=190, placeholder_text="(IP terminal)"); self.s_host.pack(side="left", padx=8)
        self.s_mode = ctk.CTkComboBox(row, values=[M0, M1, M2], width=260, command=lambda _: None); self.s_mode.set(M0); self.s_mode.pack(side="left", padx=4)
        self.s_ports = ctk.CTkEntry(row, width=200, placeholder_text="80,443,5000-5010"); self.s_ports.pack(side="left", padx=4)
        ctk.CTkLabel(row, text="Timeout").pack(side="left", padx=(10, 0))
        self.s_to = ctk.CTkEntry(row, width=50); self.s_to.insert(0, "1"); self.s_to.pack(side="left", padx=6)
        self.s_btn = ctk.CTkButton(row, text="Quét", width=90, command=self.scan); self.s_btn.pack(side="left", padx=8)
        self.s_prog = ctk.CTkLabel(tab, text=""); self.s_prog.pack(anchor="w", padx=8)
        self.s_out = ctk.CTkTextbox(tab, font=("Consolas", 13)); self.s_out.pack(fill="both", expand=True, padx=6, pady=6)
    def s_show(self, text):
        self.s_out.delete("1.0", "end"); self.s_out.insert("end", text)
    def scan(self):
        host = self.s_host.get().strip() or self.ip.get().strip()
        if not host: return self.s_show("Hãy nhập Host hoặc IP terminal ở trên cùng.")
        mode = self.s_mode.get()
        try:
            ports = sorted(HINTS) if mode == M0 else list(range(1, 1025)) if mode == M1 else parse_ports(self.s_ports.get())
            to = float(self.s_to.get() or 1)
        except ValueError as e: return self.s_show(f"Danh sách cổng hoặc timeout không hợp lệ: {e}")
        try: socket.getaddrinfo(host, None)
        except socket.gaierror: return self.s_show(f"Không phân giải được host “{host}”.")
        st = self.scan_state = {"done": 0, "total": len(ports), "open": [], "fin": False, "t0": time.time()}
        self.s_btn.configure(state="disabled"); self.s_show(f"Đang quét {host} ({len(ports)} cổng)...")
        def work():
            with ThreadPoolExecutor(200) as ex:
                futs = {ex.submit(is_open, host, p, to): p for p in ports}
                for f in as_completed(futs):
                    st["done"] += 1
                    if f.result(): st["open"].append(futs[f])
            st["fin"] = True
        threading.Thread(target=work, daemon=True).start()
        def poll():
            self.s_prog.configure(text=f"Đã quét {st['done']}/{st['total']} cổng — tìm thấy {len(st['open'])} cổng mở")
            if not st["fin"]: return self.after(200, poll)
            self.s_btn.configure(state="normal"); op = sorted(st["open"])
            lines = [f"Host: {host}   |   Quét {st['total']} cổng trong {time.time() - st['t0']:.1f} giây", ""]
            lines += [f"  ✔ {p:<6} {HINTS.get(p, '')}" for p in op] or ["  Không có cổng nào mở trong danh sách đã quét."]
            self.s_show("\n".join(lines))
        poll()

if __name__ == "__main__":
    App().mainloop()
