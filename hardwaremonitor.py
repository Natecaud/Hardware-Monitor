import sys
import os
import subprocess
import platform

#Patch subprocess.Popen on Windows to hide console windows (for both psutil and GPUtil)
if platform.system() == "Windows":
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    #Save the original subprocess.Popen so we can use it without recursion
    original_popen = subprocess.Popen

    #Override subprocess.Popen globally
    subprocess.Popen = lambda *args, **kwargs: original_popen(
        *args,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW,
        **kwargs
    )
else:
    startupinfo = None

#Now import other modules after patching subprocess.Popen
import tkinter
from tkinter import ttk
import psutil
import threading
import queue
import GPUtil

#Suppress console output in the executable if frozen
if getattr(sys, 'frozen', False):
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

#Silence GPUtil debug output
GPUtil.__GPUtil__DEBUG = False
GPUtil.__GPUtil__SILENT = True

#Create a thread-safe queue for metric data
data_queue = queue.Queue()

def measure_metrics():
    #Measure hardware metrics and put the results in a thread-safe queue
    while True:
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        gpu_usage = 0.0
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu_usage = gpus[0].load * 100
        except Exception:
            pass #Ignore errors from GPU measurement
        data_queue.put({"type": "cpu", "value": cpu})
        data_queue.put({"type": "ram", "value": ram})
        data_queue.put({"type": "gpu", "value": gpu_usage})

def update_gui(root, cpu_label, ram_label, GPU_label):
    #Update the GUI with the latest metrics from the queue
    try:
        #Process all queued items in one go
        while True:
            data = data_queue.get_nowait()
            if data["type"] == "cpu":
                cpu_label.config(text=f"CPU: {data['value']}%")
            elif data["type"] == "ram":
                ram_label.config(text=f"RAM: {data['value']}%")
            elif data["type"] == "gpu":
                GPU_label.config(text=f"GPU: {data['value']}%")
    except queue.Empty:
        pass
    #Continue polling every 200 milliseconds
    root.after(200, update_gui, root, cpu_label, ram_label, GPU_label)

#Standard entry-point guard
if __name__ == '__main__':
    #GUI Setup
    root = tkinter.Tk()
    root.title("Hardware Monitor")
    root.geometry("300x150")
    root.resizable(True, True)
    root.minsize(300, 150)
    root.maxsize(800, 600)

    main_frame = ttk.Frame(root)
    main_frame.grid(row=0, column=0, sticky="nsew")
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    for i in range(3):
        main_frame.grid_rowconfigure(i, weight=1)
    main_frame.grid_columnconfigure(0, weight=1)

    cpu_label = ttk.Label(main_frame, text="CPU: 0%", font=("Consolas", 14))
    cpu_label.grid(row=0, column=0, pady=10, sticky="nsew")

    ram_label = ttk.Label(main_frame, text="RAM: 0%", font=("Consolas", 14))
    ram_label.grid(row=1, column=0, pady=10, sticky="nsew")

    GPU_label = ttk.Label(main_frame, text="GPU: 0%", font=("Consolas", 14))
    GPU_label.grid(row=2, column=0, pady=10, sticky="nsew")

    #Start the metrics measurement thread (daemon thread will close automatically with the program)
    thread = threading.Thread(target=measure_metrics, daemon=True)
    thread.start()

    update_gui(root, cpu_label, ram_label, GPU_label)
    root.mainloop()
