"""
3-Phase PWM Controller GUI
Arduino UNO R4 WiFi — RA4M1 GPT Serial Controller

Requirements:
    pip install pyserial

Run:
    python pwm_gui.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import threading
import json
import math
import time

# ─────────────────────────────────────────────────────────────
#  Serial worker (non-blocking, runs in background thread)
# ─────────────────────────────────────────────────────────────
class SerialWorker:
    def __init__(self, on_message):
        self.ser = None
        self.on_message = on_message
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

    def connect(self, port, baud=115200):
        self.disconnect()
        self.ser = serial.Serial(port, baud, timeout=0.1)
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def disconnect(self):
        self._running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None

    def send(self, cmd: str):
        with self._lock:
            if self.ser and self.ser.is_open:
                self.ser.write((cmd + '\n').encode())

    def _read_loop(self):
        while self._running:
            try:
                line = self.ser.readline().decode(errors='replace').strip()
                if line:
                    self.on_message(line)
            except Exception:
                pass

    @property
    def connected(self):
        return self.ser is not None and self.ser.is_open


# ─────────────────────────────────────────────────────────────
#  Phase diagram canvas
# ─────────────────────────────────────────────────────────────
class PhaseDiagram(tk.Canvas):
    """Three phasors drawn on a circle."""
    COLORS = ['#e74c3c', '#2ecc71', '#3498db']
    LABELS = ['A (0°)', 'B', 'C']

    def __init__(self, master, **kw):
        super().__init__(master, width=220, height=220,
                         bg='#1a1a2e', highlightthickness=0, **kw)
        self._phases = [0.0, 120.0, 240.0]
        self.after(50, self._draw)

    def set_phases(self, phase_b, phase_c):
        self._phases = [0.0, phase_b, phase_c]
        self._draw()

    def _draw(self):
        self.delete('all')
        cx, cy, r = 110, 110, 85
        # Circle
        self.create_oval(cx-r, cy-r, cx+r, cy+r,
                         outline='#444466', width=1)
        # Tick marks every 30°
        for deg in range(0, 360, 30):
            rad = math.radians(-deg + 90)
            x1 = cx + (r-4)*math.cos(rad)
            y1 = cy - (r-4)*math.sin(rad)
            x2 = cx + r*math.cos(rad)
            y2 = cy - r*math.sin(rad)
            self.create_line(x1, y1, x2, y2, fill='#444466')

        # Phasors
        for i, (deg, col, lbl) in enumerate(
                zip(self._phases, self.COLORS, self.LABELS)):
            rad = math.radians(-deg + 90)
            ex = cx + r * math.cos(rad)
            ey = cy - r * math.sin(rad)
            self.create_line(cx, cy, ex, ey, fill=col, width=3,
                             arrow=tk.LAST, arrowshape=(10, 12, 4))
            lx = cx + (r + 14) * math.cos(rad)
            ly = cy - (r + 14) * math.sin(rad)
            label_text = lbl if i == 0 else f"{lbl[0]} ({deg:.0f}°)"
            self.create_text(lx, ly, text=label_text,
                             fill=col, font=('Consolas', 8, 'bold'))

        # Centre dot
        self.create_oval(cx-4, cy-4, cx+4, cy+4,
                         fill='#ffffff', outline='')


# ─────────────────────────────────────────────────────────────
#  PWM waveform canvas
# ─────────────────────────────────────────────────────────────
class WaveformView(tk.Canvas):
    COLORS = ['#e74c3c', '#2ecc71', '#3498db']
    LABELS = ['A', 'B', 'C']

    def __init__(self, master, **kw):
        super().__init__(master, width=480, height=180,
                         bg='#0d0d1a', highlightthickness=0, **kw)
        self._duty = 50.0
        self._phases = [0.0, 120.0, 240.0]
        self.after(50, self._draw)

    def update(self, duty, phase_b, phase_c):
        self._duty = duty
        self._phases = [0.0, phase_b, phase_c]
        self._draw()

    def _draw(self):
        self.delete('all')
        W, H = 480, 180
        margin_l, margin_r = 32, 12
        pw = W - margin_l - margin_r   # plot width = 2 full cycles
        row_h = 48
        row_gap = 8
        n_cycles = 2

        # Grid lines
        for x in [margin_l, margin_l + pw//2, margin_l + pw]:
            self.create_line(x, 0, x, H, fill='#2a2a4a', dash=(4, 4))

        for i, (phase_deg, col, lbl) in enumerate(
                zip(self._phases, self.COLORS, self.LABELS)):
            y_top    = row_gap + i * (row_h + row_gap)
            y_bot    = y_top + row_h
            y_mid    = (y_top + y_bot) // 2
            h_sig    = row_h - 10

            # Background lane
            self.create_rectangle(margin_l, y_top, W - margin_r, y_bot,
                                   fill='#0a0a18', outline='#1a1a3a')
            # Label
            self.create_text(margin_l - 4, y_mid, text=lbl,
                             fill=col, font=('Consolas', 9, 'bold'), anchor='e')

            # Draw waveform for n_cycles
            duty_frac  = self._duty / 100.0
            phase_frac = phase_deg / 360.0

            pts = []
            steps = 600
            for s in range(steps + 1):
                t = s / steps * n_cycles          # time in cycles
                t_in_cycle = (t - phase_frac) % 1.0
                high = t_in_cycle < duty_frac
                x = margin_l + int(s / steps * pw)
                y = y_top + 5 + (0 if high else h_sig)
                pts.append((x, y))

            # Render as segments with vertical transitions
            prev_x, prev_y = pts[0]
            for x, y in pts[1:]:
                if y != prev_y:
                    self.create_line(prev_x, prev_y, x, prev_y, fill=col, width=2)
                    self.create_line(x, prev_y, x, y, fill=col, width=2)
                elif x == pts[-1][0]:
                    self.create_line(prev_x, prev_y, x, y, fill=col, width=2)
                prev_x, prev_y = x, y

        # X-axis label
        self.create_text(margin_l + pw//4, H - 4,
                         text='0.5 cycle', fill='#555577', font=('Consolas', 7))
        self.create_text(margin_l + 3*pw//4, H - 4,
                         text='1.5 cycles', fill='#555577', font=('Consolas', 7))


# ─────────────────────────────────────────────────────────────
#  Main application window
# ─────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('3-Phase PWM Controller  ▸  Arduino UNO R4 WiFi')
        self.resizable(False, False)
        self.configure(bg='#1a1a2e')

        self.worker = SerialWorker(self._on_serial_msg)

        # Current state (mirrors Arduino)
        self.s_freq    = tk.DoubleVar(value=20000.0)
        self.s_duty    = tk.DoubleVar(value=50.0)
        self.s_phase_b = tk.DoubleVar(value=120.0)
        self.s_phase_c = tk.DoubleVar(value=240.0)
        self.s_running = tk.BooleanVar(value=False)

        self._build_ui()
        self._refresh_ports()

        # Trace changes for live waveform preview
        for v in (self.s_duty, self.s_phase_b, self.s_phase_c):
            v.trace_add('write', lambda *_: self._update_visuals())

    # ── UI construction ───────────────────────────────────────
    def _build_ui(self):
        PAD = dict(padx=8, pady=4)
        STYLE = {'bg': '#1a1a2e', 'fg': '#c8c8e8',
                 'font': ('Consolas', 10)}
        ENTRY_STYLE = {'bg': '#12122a', 'fg': '#e8e8ff',
                       'insertbackground': 'white',
                       'relief': 'flat', 'font': ('Consolas', 10),
                       'width': 10}
        BTN_STYLE = {'relief': 'flat', 'cursor': 'hand2',
                     'font': ('Consolas', 10, 'bold'), 'padx': 10}

        # ── Top: connection bar ───────────────────────────────
        conn_frame = tk.Frame(self, bg='#12122a', pady=6)
        conn_frame.grid(row=0, column=0, columnspan=2, sticky='ew', padx=0)

        tk.Label(conn_frame, text='Port:', **STYLE).pack(side='left', padx=(12,2))
        self.port_cb = ttk.Combobox(conn_frame, width=16,
                                     font=('Consolas', 10), state='readonly')
        self.port_cb.pack(side='left', padx=4)

        tk.Button(conn_frame, text='⟳ Refresh', command=self._refresh_ports,
                  bg='#2a2a4a', fg='#aaaacc', **BTN_STYLE).pack(side='left', padx=4)

        self.conn_btn = tk.Button(conn_frame, text='Connect',
                                   command=self._toggle_connect,
                                   bg='#27ae60', fg='white', **BTN_STYLE)
        self.conn_btn.pack(side='left', padx=8)

        self.status_lbl = tk.Label(conn_frame, text='● Disconnected',
                                    bg='#12122a', fg='#e74c3c',
                                    font=('Consolas', 10))
        self.status_lbl.pack(side='left', padx=12)

        # ── Left column: controls ─────────────────────────────
        ctrl = tk.Frame(self, bg='#1a1a2e', padx=12, pady=10)
        ctrl.grid(row=1, column=0, sticky='ns')

        def section(parent, label):
            f = tk.LabelFrame(parent, text=label, bg='#1a1a2e',
                              fg='#8888bb', font=('Consolas', 9),
                              relief='groove', padx=8, pady=6)
            f.pack(fill='x', pady=(0, 8))
            return f

        def row(parent, label, var, from_, to, resolution, unit='',
                fmt='{:.1f}'):
            r = tk.Frame(parent, bg='#1a1a2e')
            r.pack(fill='x', pady=2)
            tk.Label(r, text=label, width=10, anchor='w', **STYLE).pack(side='left')
            sl = tk.Scale(r, variable=var, from_=from_, to=to,
                          resolution=resolution, orient='horizontal',
                          length=200, bg='#12122a', fg='#c8c8e8',
                          troughcolor='#2a2a4a', highlightthickness=0,
                          activebackground='#3498db', showvalue=False,
                          command=lambda v: entry_var.set(fmt.format(float(v))))
            sl.pack(side='left', padx=4)
            entry_var = tk.StringVar(value=fmt.format(var.get()))
            e = tk.Entry(r, textvariable=entry_var, **ENTRY_STYLE)
            e.pack(side='left', padx=2)
            tk.Label(r, text=unit, **STYLE).pack(side='left')

            def on_entry(*_):
                try:
                    val = float(entry_var.get())
                    val = max(from_, min(to, val))
                    var.set(val)
                    sl.set(val)
                except ValueError:
                    pass
            entry_var.trace_add('write', on_entry)
            var.trace_add('write', lambda *_: entry_var.set(
                fmt.format(var.get())))
            return sl

        # Frequency
        f_freq = section(ctrl, ' Frequency ')
        row(f_freq, 'Freq', self.s_freq, 100, 200000, 100,
            'Hz', '{:.0f}')

        # Duty cycle
        f_duty = section(ctrl, ' Duty Cycle ')
        row(f_duty, 'Duty', self.s_duty, 0.1, 99.9, 0.1, '%')

        # Phase
        f_phase = section(ctrl, ' Phase Offsets ')
        row(f_phase, 'Phase B', self.s_phase_b, 0, 359, 1, '°', '{:.0f}')
        row(f_phase, 'Phase C', self.s_phase_c, 0, 359, 1, '°', '{:.0f}')

        # Quick presets
        f_pre = section(ctrl, ' Quick Presets ')
        preset_row = tk.Frame(f_pre, bg='#1a1a2e')
        preset_row.pack(fill='x')
        presets = [
            ('3-Phase 120°', 20000, 50, 120, 240),
            ('3-Phase 90°',  20000, 50,  90, 180),
            ('In-phase',     20000, 50,   0,   0),
            ('Half-bridge',  20000, 50, 180, 180),
        ]
        for i, (name, f, d, pb, pc) in enumerate(presets):
            tk.Button(preset_row, text=name,
                      command=lambda f=f,d=d,pb=pb,pc=pc: self._apply_preset(f,d,pb,pc),
                      bg='#2c2c4e', fg='#aaaaee', **BTN_STYLE
                      ).grid(row=i//2, column=i%2, padx=2, pady=2, sticky='ew')

        # Send / Stop
        btn_frame = tk.Frame(ctrl, bg='#1a1a2e', pady=4)
        btn_frame.pack(fill='x')
        self.send_btn = tk.Button(btn_frame, text='▶  SEND',
                                   command=self._send_all,
                                   bg='#2980b9', fg='white',
                                   state='disabled', **BTN_STYLE)
        self.send_btn.pack(side='left', expand=True, fill='x', padx=(0,4))
        self.stop_btn = tk.Button(btn_frame, text='■  STOP',
                                   command=self._send_stop,
                                   bg='#c0392b', fg='white',
                                   state='disabled', **BTN_STYLE)
        self.stop_btn.pack(side='left', expand=True, fill='x')

        # ── Right column: visuals ─────────────────────────────
        vis = tk.Frame(self, bg='#1a1a2e', padx=8, pady=10)
        vis.grid(row=1, column=1, sticky='ns')

        tk.Label(vis, text='Phase Diagram', bg='#1a1a2e', fg='#c8c8e8',
                 font=('Consolas', 9)).pack(anchor='w')
        self.phase_diag = PhaseDiagram(vis)
        self.phase_diag.pack(pady=(2, 10))

        tk.Label(vis, text='Waveform Preview (2 cycles)', bg='#1a1a2e', fg='#c8c8e8',
                 font=('Consolas', 9)).pack(anchor='w')
        self.wave_view = WaveformView(vis)
        self.wave_view.pack()

        # ── Log ───────────────────────────────────────────────
        log_frame = tk.Frame(self, bg='#0a0a18', padx=8, pady=4)
        log_frame.grid(row=2, column=0, columnspan=2, sticky='ew')
        tk.Label(log_frame, text='Serial Log', bg='#0a0a18',
                 fg='#555577', font=('Consolas', 8)).pack(anchor='w')
        self.log = tk.Text(log_frame, height=5, bg='#0a0a18',
                            fg='#44cc88', font=('Consolas', 8),
                            state='disabled', relief='flat', wrap='word')
        self.log.pack(fill='x')

        self._update_visuals()

    # ── Helpers ───────────────────────────────────────────────
    def _update_visuals(self):
        pb = self.s_phase_b.get()
        pc = self.s_phase_c.get()
        d  = self.s_duty.get()
        self.phase_diag.set_phases(pb, pc)
        self.wave_view.update(d, pb, pc)

    def _log(self, msg, color='#44cc88'):
        self.log.config(state='normal')
        self.log.insert('end', msg + '\n')
        self.log.see('end')
        self.log.config(state='disabled')

    def _on_serial_msg(self, msg):
        self.after(0, self._log, f'← {msg}')
        # Parse status JSON
        if msg.startswith('{'):
            try:
                d = json.loads(msg)
                self.after(0, self._apply_status, d)
            except Exception:
                pass

    def _apply_status(self, d):
        if 'freq'    in d: self.s_freq.set(d['freq'])
        if 'duty'    in d: self.s_duty.set(d['duty'])
        if 'phase_b' in d: self.s_phase_b.set(d['phase_b'])
        if 'phase_c' in d: self.s_phase_c.set(d['phase_c'])
        if 'running' in d: self.s_running.set(d['running'])

    def _apply_preset(self, freq, duty, pb, pc):
        self.s_freq.set(freq)
        self.s_duty.set(duty)
        self.s_phase_b.set(pb)
        self.s_phase_c.set(pc)
        if self.worker.connected:
            self._send_all()

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_cb['values'] = ports
        if ports:
            self.port_cb.set(ports[0])

    def _toggle_connect(self):
        if self.worker.connected:
            self.worker.disconnect()
            self.conn_btn.config(text='Connect', bg='#27ae60')
            self.status_lbl.config(text='● Disconnected', fg='#e74c3c')
            self.send_btn.config(state='disabled')
            self.stop_btn.config(state='disabled')
        else:
            port = self.port_cb.get()
            if not port:
                messagebox.showerror('Error', 'No port selected')
                return
            try:
                self.worker.connect(port)
                self.conn_btn.config(text='Disconnect', bg='#c0392b')
                self.status_lbl.config(text=f'● Connected ({port})', fg='#2ecc71')
                self.send_btn.config(state='normal')
                self.stop_btn.config(state='normal')
                self._log(f'Connected to {port}')
                # Request status after a short delay
                self.after(500, lambda: self.worker.send('GET STATUS'))
            except Exception as e:
                messagebox.showerror('Connection Error', str(e))

    def _send_all(self):
        if not self.worker.connected:
            return
        cmds = [
            f"SET FREQ {self.s_freq.get():.0f}",
            f"SET DUTY {self.s_duty.get():.1f}",
            f"SET PHASE_B {self.s_phase_b.get():.1f}",
            f"SET PHASE_C {self.s_phase_c.get():.1f}",
            "START",
        ]
        for cmd in cmds:
            self.worker.send(cmd)
            self._log(f'→ {cmd}', '#4488ff')
            time.sleep(0.04)   # small gap so Arduino can process

    def _send_stop(self):
        if not self.worker.connected:
            return
        self.worker.send('STOP')
        self._log('→ STOP', '#ff6644')

    def on_close(self):
        self.worker.disconnect()
        self.destroy()


# ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app = App()
    app.protocol('WM_DELETE_WINDOW', app.on_close)
    app.mainloop()