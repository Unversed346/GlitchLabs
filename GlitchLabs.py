from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QFrame,
    QSpinBox, QLineEdit, QComboBox, QGroupBox, QListWidget, QListWidgetItem
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtCore import Qt, QUrl
import sys, random, os

def parse_pattern(text: str, mode: str) -> bytes:
    """Parse user input into bytes. Raises ValueError with a clear message."""
    if mode == "Hex":
        cleaned = text.replace(" ", "").replace("0x", "").replace(",", "")
        if not cleaned:
            raise ValueError("Hex input is empty")
        if len(cleaned) % 2 != 0:
            raise ValueError(f"Odd number of hex digits: '{cleaned}'")
        try:
            return bytes.fromhex(cleaned)
        except ValueError:
            raise ValueError(f"Invalid hex characters in: '{cleaned}'")
    else:  # Text mode — handle \xNN escapes manually
        result = bytearray()
        i = 0
        while i < len(text):
            if text[i:i+2] == "\\x" and i + 4 <= len(text):
                hex_part = text[i+2:i+4]
                try:
                    result.append(int(hex_part, 16))
                    i += 4
                    continue
                except ValueError:
                    pass
            result.append(ord(text[i]) & 0xFF)
            i += 1
        return bytes(result)

class GlitchLab(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Glitch Lab")
        self.setGeometry(100, 100, 960, 700)
        self.file_path = None
        self.iterations = []          # list of bytes snapshots
        self.current_index = -1
        self._loop = False
        self._pending_iterations = [] # list of (label, callable) not yet run

        # Background
        self.bg_label = QLabel(self)
        self.bg_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.bg_pixmap = QPixmap("background.png")
        self.bg_label.lower()
        self._tile_background()

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(4)

        # ── Toolbar: file ops ──────────────────────────────
        tb_file = QHBoxLayout()
        self.open_btn    = QPushButton("Open File")
        self.save_btn    = QPushButton("Save Copy")
        self.reset_btn   = QPushButton("Reset")
        self.undo_btn    = QPushButton("◀ Undo")
        self.redo_btn    = QPushButton("Redo ▶")
        self.preview_btn = QPushButton("▶ Preview")
        self.stop_btn    = QPushButton("⏹ Stop")
        self.loop_btn    = QPushButton("Loop: OFF")
        for b in [self.open_btn, self.save_btn, self.reset_btn,
                  self.undo_btn, self.redo_btn,
                  self.preview_btn, self.stop_btn, self.loop_btn]:
            b.setFixedHeight(28)
            tb_file.addWidget(b)
        tb_file.addStretch()
        root.addLayout(tb_file)

        sep1 = QFrame(); sep1.setFrameShape(QFrame.HLine); root.addWidget(sep1)

        # ── Builder section ───────────────────────────────
        builder_row = QHBoxLayout()
        builder_row.setSpacing(6)

        # Random Bytes
        rng_box = QGroupBox("Random Bytes")
        rng_lay = QHBoxLayout(rng_box)
        rng_lay.setContentsMargins(4, 2, 4, 2)
        self.byte_count = QSpinBox()
        self.byte_count.setRange(1, 1_000_000)
        self.byte_count.setValue(500)
        self.byte_count.setFixedWidth(90)
        self.add_corrupt_btn = QPushButton("+ Add")
        rng_lay.addWidget(QLabel("Bytes:"))
        rng_lay.addWidget(self.byte_count)
        rng_lay.addWidget(self.add_corrupt_btn)
        builder_row.addWidget(rng_box)

        # Find & Replace
        fr_box = QGroupBox("Find & Replace")
        fr_lay = QHBoxLayout(fr_box)
        fr_lay.setContentsMargins(4, 2, 4, 2)
        self.find_edit = QLineEdit(); self.find_edit.setPlaceholderText("Find")
        self.replace_edit = QLineEdit(); self.replace_edit.setPlaceholderText("Replace (blank = delete)")
        self.find_edit.setFixedWidth(140)
        self.replace_edit.setFixedWidth(140)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Text", "Hex"])
        self.mode_combo.setFixedWidth(70)
        self.add_replace_btn = QPushButton("+ Add")
        fr_lay.addWidget(QLabel("Find:"))
        fr_lay.addWidget(self.find_edit)
        fr_lay.addWidget(QLabel("→"))
        fr_lay.addWidget(self.replace_edit)
        fr_lay.addWidget(self.mode_combo)
        fr_lay.addWidget(self.add_replace_btn)
        builder_row.addWidget(fr_box)

        # Advanced Corruptions
        adv_box = QGroupBox("Advanced Corruptions")
        adv_lay = QHBoxLayout(adv_box)
        adv_lay.setContentsMargins(4, 2, 4, 2)
        self.shift_btn = QPushButton("Shift Bytes")
        self.interleave_btn = QPushButton("Interleave Chunks")
        self.pattern_btn = QPushButton("Pattern Injection")
        self.del_block_btn = QPushButton("Random Block Deletion")
        self.noise_btn = QPushButton("Noise Amplification")
        for b in [self.shift_btn, self.interleave_btn, self.pattern_btn,
                  self.del_block_btn, self.noise_btn]:
            b.setFixedHeight(26)
            adv_lay.addWidget(b)
        builder_row.addWidget(adv_box)

        builder_row.addStretch()
        root.addLayout(builder_row)

        # ── Pending iterations queue ───────────────────────
        queue_row = QHBoxLayout()
        queue_left = QVBoxLayout()
        queue_left.addWidget(QLabel("Pending Iterations:"))
        self.queue_list = QListWidget()
        self.queue_list.setFixedHeight(90)
        self.queue_list.setSelectionMode(QListWidget.SingleSelection)
        queue_left.addWidget(self.queue_list)
        queue_row.addLayout(queue_left, stretch=1)
        queue_btns = QVBoxLayout()
        queue_btns.setSpacing(3)
        self.run_one_btn  = QPushButton("Run Selected")
        self.run_all_btn  = QPushButton("Run All")
        self.remove_btn   = QPushButton("Remove Selected")
        self.clear_queue_btn = QPushButton("Clear Queue")
        for b in [self.run_one_btn, self.run_all_btn,
                  self.remove_btn, self.clear_queue_btn]:
            queue_btns.addWidget(b)
        queue_btns.addStretch()
        queue_row.addLayout(queue_btns)
        root.addLayout(queue_row)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine); root.addWidget(sep2)

        # ── Video / Audio Preview ─────────────────────────
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000;")
        self.player.setVideoOutput(self.video_widget)
        root.addWidget(self.video_widget, stretch=1)

        # Status
        self.status = QLabel("No file loaded.")
        root.addWidget(self.status)

        # ── Connections ───────────────────────────────────
        self.open_btn.clicked.connect(self.open_file)
        self.save_btn.clicked.connect(self.save_file)
        self.reset_btn.clicked.connect(self.reset)
        self.undo_btn.clicked.connect(self.undo)
        self.redo_btn.clicked.connect(self.redo)
        self.preview_btn.clicked.connect(self.preview)
        self.stop_btn.clicked.connect(self.stop_preview)
        self.loop_btn.clicked.connect(self.toggle_loop)
        self.add_corrupt_btn.clicked.connect(self.add_corrupt_iteration)
        self.add_replace_btn.clicked.connect(self.add_replace_iteration)

        # Advanced corruptions
        self.shift_btn.clicked.connect(self.add_shift_iteration)
        self.interleave_btn.clicked.connect(self.add_interleave_iteration)
        self.pattern_btn.clicked.connect(self.add_pattern_iteration)
        self.del_block_btn.clicked.connect(self.add_blockdel_iteration)
        self.noise_btn.clicked.connect(self.add_noise_iteration)

        self.run_one_btn.clicked.connect(self.run_selected)
        self.run_all_btn.clicked.connect(self.run_all)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_queue_btn.clicked.connect(self.clear_queue)

        self._update_buttons()

    # ── Background ─────────────────────────────────────────
    def _tile_background(self):
        w, h = max(self.width(), 1), max(self.height(), 1)
        self.bg_label.setGeometry(0, 0, w, h)
        if self.bg_pixmap.isNull():
            return
        tiled = QPixmap(w, h)
        p = QPainter(tiled)
        for x in range(0, w, self.bg_pixmap.width()):
            for y in range(0, h, self.bg_pixmap.height()):
                p.drawPixmap(x, y, self.bg_pixmap)
        p.end()
        self.bg_label.setPixmap(tiled)

    def resizeEvent(self, event):
        self._tile_background()
        super().resizeEvent(event)

    # ── Button state ─────────────────────────────────────────
    def _update_buttons(self):
        has = bool(self.iterations)
        for b in [self.save_btn, self.reset_btn, self.preview_btn, self.stop_btn]:
            b.setEnabled(has)
        self.undo_btn.setEnabled(self.current_index > 0)
        self.redo_btn.setEnabled(self.current_index < len(self.iterations) - 1)
        has_queue = self.queue_list.count() > 0
        self.run_all_btn.setEnabled(has and has_queue)
        self.run_one_btn.setEnabled(has and has_queue)
        self.remove_btn.setEnabled(has_queue)
        self.clear_queue_btn.setEnabled(has_queue)

    # ── Queue helper ───────────────────────────────────────
    def _queue_add(self, label, op):
        self._pending_iterations.append(op)
        item = QListWidgetItem(f"{self.queue_list.count()+1}. {label}")
        self.queue_list.addItem(item)
        self.status.setText(f"Queued: {label}")
        self._update_buttons()

    # ── File ops ───────────────────────────────────────────
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if path:
            self.file_path = path
            with open(path, "rb") as f:
                self.iterations = [f.read()]
            self.current_index = 0
            self.status.setText(f"Loaded: {os.path.basename(path)}  ({len(self.iterations[0])} bytes)")
            self._update_buttons()

    def save_file(self):
        if not self.iterations or not self.file_path:
            return
        ext = os.path.splitext(self.file_path)[1]
        path, _ = QFileDialog.getSaveFileName(self, "Save File", "", f"*{ext}")
        if path:
            with open(path, "wb") as f:
                f.write(self.iterations[self.current_index])
            self.status.setText(f"Saved → {os.path.basename(path)}")

    def reset(self):
        if self.iterations:
            self.current_index = 0
            self.status.setText("Reset to original.")
            self._update_buttons()

    def undo(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.status.setText(f"Undo → iteration {self.current_index}")
            self._update_buttons()

    def redo(self):
        if self.current_index < len(self.iterations) - 1:
            self.current_index += 1
            self.status.setText(f"Redo → iteration {self.current_index}")
            self._update_buttons()

    def preview(self):
        if self.current_index < 0 or not self.file_path:
            return
        ext = os.path.splitext(self.file_path)[1]
        temp = os.path.join(os.path.dirname(self.file_path), "_glitch_preview" + ext)
        with open(temp, "wb") as f:
            f.write(self.iterations[self.current_index])
        self.player.setSource(QUrl.fromLocalFile(temp))
        self.player.play()

    def stop_preview(self):
        self.player.stop()
        self.status.setText("Playback stopped.")

    def toggle_loop(self):
        self._loop = not self._loop
        self.player.setLoops(-1 if self._loop else 1)
        self.loop_btn.setText(f"Loop: {'ON' if self._loop else 'OFF'}")

    # ── Standard corruptions ──────────────────────────────
    def add_corrupt_iteration(self):
        count = self.byte_count.value()
        label = f"Random Corrupt ({count} bytes)"
        def op(data):
            arr = bytearray(data)
            n = min(count, len(arr))
            for idx in random.sample(range(len(arr)), n):
                arr[idx] = random.randint(0, 255)
            return bytes(arr)
        self._queue_add(label, op)

    def add_replace_iteration(self):
        find_txt    = self.find_edit.text()
        replace_txt = self.replace_edit.text()
        mode        = self.mode_combo.currentText()
        if not find_txt:
            self.status.setText("Find field is empty.")
            return
        try:
            find_bytes    = parse_pattern(find_txt, mode)
            replace_bytes = parse_pattern(replace_txt, mode) if replace_txt else b""
        except ValueError as e:
            self.status.setText(f"Error: {e}")
            return
        label = f"Replace [{mode}] {find_txt!r} → {replace_txt!r}"
        def op(data, fb=find_bytes, rb=replace_bytes):
            return data.replace(fb, rb)
        self._queue_add(label, op)
        self.find_edit.clear()
        self.replace_edit.clear()

    # ── Advanced corruptions ─────────────────────────────
    def add_shift_iteration(self):
        label = "Shift Bytes"
        def op(data):
            arr = bytearray(data)
            if len(arr) > 1:
                start = random.randint(0, len(arr)-1)
                end = random.randint(start+1, len(arr))
                chunk = arr[start:end]
                arr[start:end] = chunk[-1:] + chunk[:-1]
            return bytes(arr)
        self._queue_add(label, op)

    def add_interleave_iteration(self):
        label = "Interleave Chunks"
        def op(data):
            arr = bytearray(data)
            if len(arr) > 2:
                mid = len(arr)//2
                arr[:mid], arr[mid:] = arr[mid:], arr[:mid]
            return bytes(arr)
        self._queue_add(label, op)

    def add_pattern_iteration(self):
        label = "Pattern Injection"
        pattern = bytes([0xAA, 0x55])
        def op(data):
            arr = bytearray(data)
            for i in range(0, len(arr), len(pattern)):
                for j, b in enumerate(pattern):
                    if i+j < len(arr):
                        arr[i+j] = b
            return bytes(arr)
        self._queue_add(label, op)

    def add_blockdel_iteration(self):
        label = "Random Block Deletion"
        def op(data):
            arr = bytearray(data)
            if len(arr) > 5:
                start = random.randint(0, len(arr)-5)
                del arr[start:start+5]
            return bytes(arr)
        self._queue_add(label, op)

    def add_noise_iteration(self):
        label = "Noise Amplification"
        def op(data):
            arr = bytearray(data)
            for _ in range(min(100, len(arr))):
                idx = random.randint(0, len(arr)-1)
                arr[idx] = (arr[idx] + random.randint(50, 255)) % 256
            return bytes(arr)
        self._queue_add(label, op)

    # ── Queue ops ───────────────────────────────────────
    def run_selected(self):
        row = self.queue_list.currentRow()
        if row < 0 or not self.iterations:
            return
        data = self.iterations[self.current_index]
        new_data = self._pending_iterations[row](data)
        self._push(new_data)
        self.queue_list.takeItem(row)
        self._pending_iterations.pop(row)
        self._renumber_queue()
        self._update_buttons()

    def run_all(self):
        if not self.iterations:
            return
        count = self.queue_list.count()
        for i in range(count):
            data = self.iterations[self.current_index]
            new_data = self._pending_iterations[0](data)
            self._push(new_data)
            self._pending_iterations.pop(0)
            self.queue_list.takeItem(0)
        self._renumber_queue()
        self.status.setText(f"Ran {count} iteration(s) → iteration {self.current_index}")
        self._update_buttons()

    def remove_selected(self):
        row = self.queue_list.currentRow()
        if row < 0:
            return
        self.queue_list.takeItem(row)
        self._pending_iterations.pop(row)
        self._renumber_queue()
        self._update_buttons()

    def clear_queue(self):
        self.queue_list.clear()
        self._pending_iterations.clear()
        self._update_buttons()

    def _renumber_queue(self):
        for i in range(self.queue_list.count()):
            item = self.queue_list.item(i)
            text = item.text()
            item.setText(f"{i+1}. {text.split('. ', 1)[-1]}")

    # ── Helper to push new iteration ─────────────────────
    def _push(self, data: bytes):
        self.iterations = self.iterations[:self.current_index + 1]
        self.iterations.append(data)
        self.current_index += 1
        self._update_buttons()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GlitchLab()
    window.show()
    sys.exit(app.exec())