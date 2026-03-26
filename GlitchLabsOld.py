import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import random
import tempfile
import os
import pygame
from PIL import Image, ImageTk

pygame.mixer.init()

class GlitchLabUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Glitch Lab")
        self.root.configure(bg="#1e1e1e")
        self.file_data = None
        self.iterations = []
        self.current_index = -1
        self.file_path = None
        self.bg_photo = None

        # Canvas for background and preview
        self.canvas = tk.Canvas(root, width=800, height=600, bg="#1e1e1e")
        self.canvas.grid(row=0, column=0, columnspan=3, rowspan=6, sticky="nsew")

        # Preview label over canvas
        self.preview_label = tk.Label(self.canvas, bg="#1e1e1e")
        self.preview_label.place(x=0, y=0)

        # Configure grid weights
        for i in range(3):
            root.columnconfigure(i, weight=1)
        for i in range(6):
            root.rowconfigure(i, weight=1)

        # Buttons in grid (smaller so they don’t stretch)
        self.add_button("Open File", self.open_file, 0, 0, width=15)
        self.add_button("Random Corrupt", self.random_corrupt, 0, 1, width=15)
        self.add_button("Pattern Replace", self.pattern_replace, 0, 2, width=15)
        self.add_button("Next Iteration", self.next_iteration, 1, 0, width=15)
        self.add_button("Previous Iteration", self.prev_iteration, 1, 1, width=15)
        self.add_button("Preview", self.preview, 1, 2, width=15)
        self.add_button("Stop Preview", self.stop_preview, 2, 0, width=15)
        self.add_button("Save Current", self.save_current, 2, 1, width=15)

        # Load repeating background
        self.load_background("background.png", tile_width=100, tile_height=100)

    def add_button(self, text, command, row, col, width=10):
        btn = tk.Button(self.root, text=text, bg="#333", fg="#fff", command=command, width=width)
        btn.grid(row=row, column=col, padx=5, pady=5)

    # ---------------- Background ----------------
    # ---------------- Background ----------------
    def load_background(self, filename, tile_width=100, tile_height=100):
        if not os.path.exists(filename):
            return
        img = Image.open(filename)
        img = img.resize((tile_width, tile_height), Image.Resampling.LANCZOS)
        self.bg_photo = ImageTk.PhotoImage(img)

        def draw_tiles(event=None):
            self.canvas.delete("bg_tile")
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            for x in range(0, canvas_width, tile_width):
                for y in range(0, canvas_height, tile_height):
                    self.canvas.create_image(x, y, image=self.bg_photo, anchor="nw", tags="bg_tile")

    # Bind redraw to canvas size changes
        self.canvas.bind("<Configure>", draw_tiles)

        self.root.after(100, draw_tiles)

    # ---------------- File operations ----------------
    def open_file(self):
        path = filedialog.askopenfilename(title="Select a file")
        if path:
            self.file_path = path
            with open(path, "rb") as f:
                self.file_data = f.read()
            self.iterations = [self.file_data]
            self.current_index = 0
            messagebox.showinfo("Loaded", f"File loaded: {os.path.basename(path)}")

    def random_corrupt(self, intensity=None):
        if self.file_data is None:
            messagebox.showwarning("No file", "Load a file first!")
            return
        if intensity is None:
            intensity = simpledialog.askinteger("Intensity", "Bytes to corrupt?", minvalue=1, maxvalue=1000)
            if intensity is None:
                return
        data = bytearray(self.iterations[self.current_index])
        for _ in range(intensity):
            idx = random.randint(0, len(data)-1)
            data[idx] = random.randint(0, 255)
        self._add_iteration(bytes(data))

    def pattern_replace(self):
        if self.file_data is None:
            messagebox.showwarning("No file", "Load a file first!")
            return
        orig = simpledialog.askstring("Pattern Replace", "Original char (single char):")
        if not orig:
            return
        repl = simpledialog.askstring("Pattern Replace", "Replacement char (single char):")
        if repl is None:
            return
        orig_byte = ord(orig)
        repl_byte = ord(repl)
        data = bytearray(self.iterations[self.current_index])
        for i in range(len(data)):
            if data[i] == orig_byte:
                data[i] = repl_byte
        self._add_iteration(bytes(data))

    def _add_iteration(self, new_data):
        self.iterations = self.iterations[:self.current_index+1] + [new_data]
        self.current_index += 1
        messagebox.showinfo("Iteration", f"Iteration {self.current_index} created")

    def next_iteration(self):
        if self.current_index < len(self.iterations) - 1:
            self.current_index += 1
            messagebox.showinfo("Iteration", f"Moved to iteration {self.current_index}")
        else:
            messagebox.showwarning("End", "No next iteration!")

    def prev_iteration(self):
        if self.current_index > 0:
            self.current_index -= 1
            messagebox.showinfo("Iteration", f"Moved back to iteration {self.current_index}")
        else:
            messagebox.showwarning("Start", "Already at the first iteration!")

    # ---------------- Preview ----------------
    def preview(self):
        if self.current_index < 0:
            messagebox.showwarning("No file", "Nothing to preview!")
            return
        temp_path = tempfile.mktemp(suffix=os.path.splitext(self.file_path)[1])
        with open(temp_path, "wb") as f:
            f.write(self.iterations[self.current_index])
        try:
            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.play()
        except pygame.error:
            messagebox.showwarning("Preview Error", "Cannot preview this file type.")

    def stop_preview(self):
        pygame.mixer.music.stop()

    # ---------------- Save ----------------
    def save_current(self):
        if self.current_index < 0:
            return
        path = filedialog.asksaveasfilename(title="Save corrupted file")
        if path:
            with open(path, "wb") as f:
                f.write(self.iterations[self.current_index])
            messagebox.showinfo("Saved", f"Iteration {self.current_index} saved!")

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("800x600")
    app = GlitchLabUI(root)
    root.mainloop()