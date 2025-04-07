import tkinter
from tkinter import ttk
import psutil
import threading
import queue
import GPUtil


data_queue = queue.Queue()#Creates a queue to pass data between threads

#Initialize GUI
root = tkinter.Tk()
root.title("Hardware Monitor")#title of window
root.geometry("300x150")#initial window size
root.resizable(True, True)#allow window to be resized
root.minsize(300, 150)#minimum window size
root.maxsize(800, 600)#maximum window size

main_frame = ttk.Frame(root)#creates a container frame inside the root window
main_frame.grid(row=0, column=0, sticky="nsew")#places the frame in row 0, column 0, sticky="nsew" meaning it will expand in all directions

root.grid_rowconfigure(0, weight=1)#allows row 0 of the root grid window's to expand
root.grid_columnconfigure(0, weight=1)#allows column 0 of the root window's grid to expand

for i in range(3):#loop runs 3 times, because we have 3 items:cpu, ram, and gpu
    main_frame.grid_rowconfigure(i, weight=1)#allows each row to expand, looping through all rows
main_frame.grid_columnconfigure(0, weight=1)#allows column 0 of the main_frame's grid that allows column 0 to expand, since there is only 1 column

cpu_label = ttk.Label(main_frame, text="CPU: 0%", font=("Consolas", 14))#creates a cpu label, places it in the main_frame grid, gives it initial text and font/size
cpu_label.grid(row=0, column=0, pady=10, sticky="nsew")#shows where on the grid this sticker will be placed, pady is the number of pixels between the stickers and everything around them

ram_label = ttk.Label(main_frame, text="RAM: 0%", font=("Consolas", 14))#creates a ram label, places it in the main_frame grid, gives it initial text and font/size
ram_label.grid(row=1, column=0, pady=10, sticky="nsew")#shows where on the grid this sticker will be placed, pady is the number of pixels between the stickers and everything around them

GPU_label = ttk.Label(main_frame, text="GPU: 0%", font=("Consolas", 14))#creates a gpu label, places it in the main_frame grid, gives it initial text and font/size
GPU_label.grid(row=2, column=0, pady=10, sticky="nsew")#shows where on the grid this sticker will be placed, pady is the number of pixels between the stickers and everything around them

def measure_metrics():#defines the measure_metrics method which updates the percentages every second
    while True:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        gpu = GPUtil.getGPUs()[0].load * 100 if GPUtil.getGPUs() else 0.0

        data_queue.put({"type": "cpu", "value": cpu})#loads cpu into the queue
        data_queue.put({"type": "ram", "value": ram})#loads ram into the queue
        data_queue.put({"type": "gpu", "value": gpu})#loads gpu into the queue

def update_gui():#defines the update_gui method which checks the type we put in the queue above and updates the gui accordingly
    """Checks the queue and updates the GUI (runs in the main thread)."""
    try:
        data = data_queue.get_nowait()
        if data["type"] == "cpu":
            cpu_label.config(text=f"CPU: {data['value']}%")

        elif data["type"] == "ram":
            ram_label.config(text=f"RAM: {data['value']}%")

        elif data["type"] == "gpu":
            GPU_label.config(text=f"GPU: {data['value']}%")
    except queue.Empty:
        pass
    root.after(100, update_gui)

thread = threading.Thread(target=measure_metrics, daemon = True)#puts measure_metrics into its own thread for performance, daemon closes automatically
thread.start()#starts the thread

update_gui()#calls update_gui method

root.mainloop()#calls the root.mainloop method