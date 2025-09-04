import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import serial
import serial.tools.list_ports
import threading
import time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib
import csv
import os
from datetime import datetime

# Configure matplotlib to support English display
matplotlib.rcParams["font.family"] = ["Arial", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False  # Fix minus sign display issue


class SmartRopeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Smart Jump Rope Data Visualization Tool")
        self.geometry("800x600")
        self.configure(bg="#f0f0f0")

        # Data storage
        self.serial_data = []  # Stores data received from serial port
        self.data_by_mode = {0: [], 1: [], 2: []}  # Data categorized by exercise mode
        self.current_plot_mode = 0  # Currently selected exercise mode
        self.current_y_axis = "exerciseDuration"  # Currently selected Y-axis data

        # Create main container
        self.container = tk.Frame(self)
        self.container.pack(fill="both", expand=True)

        # Create three pages
        self.frames = {}
        for F in (MainPage, SerialPage, ChartPage):
            frame = F(self.container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # Show main page initially
        self.show_frame(MainPage)

    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()


class MainPage(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent, bg="#f0f0f0")
        self.controller = controller

        # Create title
        title_label = tk.Label(self, text="Smart Jump Rope Data Visualization Tool",
                               font=("Arial", 24, "bold"), bg="#f0f0f0")
        title_label.pack(pady=50)

        # Create introduction text
        intro_text = """
        Welcome to the Smart Jump Rope Data Visualization Tool!

        This tool helps you:
        1. Connect to your smart jump rope device via serial port
        2. Monitor real-time exercise data
        3. Analyze performance across different exercise modes
        4. Generate intuitive charts to visualize trends

        Click the buttons below to get started:
        """
        intro_label = tk.Label(self, text=intro_text, font=("Arial", 12),
                               bg="#f0f0f0", justify=tk.LEFT)
        intro_label.pack(pady=20)

        # Create button frame
        button_frame = tk.Frame(self, bg="#f0f0f0")
        button_frame.pack(pady=30)

        # Serial connection page button
        serial_button = tk.Button(button_frame, text="Serial Connection",
                                  font=("Arial", 14), width=15, height=2,
                                  command=lambda: controller.show_frame(SerialPage),
                                  bg="#4CAF50", fg="white")
        serial_button.pack(side=tk.LEFT, padx=20)

        # Chart analysis page button
        chart_button = tk.Button(button_frame, text="Chart Analysis",
                                 font=("Arial", 14), width=15, height=2,
                                 command=lambda: controller.show_frame(ChartPage),
                                 bg="#2196F3", fg="white")
        chart_button.pack(side=tk.LEFT, padx=20)

        # Footer information
        footer_label = tk.Label(self, text="© 2025 Smart Jump Rope Analysis System",
                                font=("Arial", 10), bg="#f0f0f0")
        footer_label.pack(side=tk.BOTTOM, pady=10)


class SerialPage(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent, bg="#f0f0f0")
        self.controller = controller
        self.serial_port = None
        self.serial_thread = None
        self.stop_thread = threading.Event()

        # Create navigation bar
        nav_frame = tk.Frame(self, bg="#e0e0e0", height=40)
        nav_frame.pack(fill="x")

        home_button = tk.Button(nav_frame, text="Home", command=lambda: controller.show_frame(MainPage),
                                bg="#e0e0e0", bd=0, font=("Arial", 10))
        home_button.pack(side=tk.LEFT, padx=10, pady=5)

        chart_button = tk.Button(nav_frame, text="Chart Analysis", command=lambda: controller.show_frame(ChartPage),
                                 bg="#e0e0e0", bd=0, font=("Arial", 10))
        chart_button.pack(side=tk.LEFT, padx=10, pady=5)

        # Create serial settings frame
        settings_frame = tk.LabelFrame(self, text="Serial Settings", font=("Arial", 12), bg="#f0f0f0")
        settings_frame.pack(fill="x", padx=20, pady=10)

        # Port selection
        tk.Label(settings_frame, text="Port:", font=("Arial", 10), bg="#f0f0f0").grid(row=0, column=0, padx=10, pady=10)
        self.port_var = tk.StringVar()
        self.port_combobox = ttk.Combobox(settings_frame, textvariable=self.port_var, width=15)
        self.port_combobox.grid(row=0, column=1, padx=10, pady=10)
        self.refresh_ports()

        refresh_button = tk.Button(settings_frame, text="Refresh Ports", command=self.refresh_ports,
                                   bg="#f0f0f0", font=("Arial", 10))
        refresh_button.grid(row=0, column=2, padx=10, pady=10)

        # Baudrate selection
        tk.Label(settings_frame, text="Baudrate:", font=("Arial", 10), bg="#f0f0f0").grid(row=0, column=3, padx=10,
                                                                                          pady=10)
        self.baudrate_var = tk.StringVar(value="115200")
        self.baudrate_combobox = ttk.Combobox(settings_frame, textvariable=self.baudrate_var,
                                              values=["9600", "115200", "230400"], width=10)
        self.baudrate_combobox.grid(row=0, column=4, padx=10, pady=10)

        # Connect/disconnect button
        self.connect_button = tk.Button(settings_frame, text="Connect", command=self.toggle_connection,
                                        bg="#4CAF50", fg="white", font=("Arial", 10))
        self.connect_button.grid(row=0, column=5, padx=20, pady=10)

        # Create data display area
        data_frame = tk.LabelFrame(self, text="Received Data", font=("Arial", 12), bg="#f0f0f0")
        data_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Create scrolled text area
        self.data_text = scrolledtext.ScrolledText(data_frame, wrap=tk.WORD, height=10,
                                                   font=("Arial", 10))
        self.data_text.pack(fill="both", expand=True, padx=10, pady=10)

        # Create data table
        columns = ("Mode", "Duration (s)", "Avg HR", "Max HR", "Frequency", "Jumps")
        self.data_table = ttk.Treeview(data_frame, columns=columns, show="headings", height=10)

        for col in columns:
            self.data_table.heading(col, text=col)
            self.data_table.column(col, width=100, anchor=tk.CENTER)

        self.data_table.pack(fill="both", expand=True, padx=10, pady=10)

        # Create status bar
        status_frame = tk.Frame(self, bg="#e0e0e0", height=30)
        status_frame.pack(fill="x", side=tk.BOTTOM)

        self.status_var = tk.StringVar(value="Ready")
        self.status_label = tk.Label(status_frame, textvariable=self.status_var,
                                     bg="#e0e0e0", font=("Arial", 10))
        self.status_label.pack(side=tk.LEFT, padx=10, pady=5)

        self.data_count_var = tk.StringVar(value="Data Count: 0")
        self.data_count_label = tk.Label(status_frame, textvariable=self.data_count_var,
                                         bg="#e0e0e0", font=("Arial", 10))
        self.data_count_label.pack(side=tk.RIGHT, padx=10, pady=5)

        # Initialize data file
        self.init_data_file()

    def init_data_file(self):
        """Initialize data storage file"""
        if not os.path.exists("JumpRopeData"):
            os.makedirs("JumpRopeData")
        self.data_file = os.path.join("JumpRopeData", f"JumpRopeData_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        with open(self.data_file, 'w', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            writer.writerow(["Mode", "Duration (s)", "Avg HR", "Max HR", "Frequency", "Jumps", "Record Time"])

    def refresh_ports(self):
        """Refresh available serial ports"""
        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]
        self.port_combobox['values'] = port_list
        if port_list:
            self.port_combobox.current(0)

    def toggle_connection(self):
        """Toggle serial connection status"""
        if self.serial_port and self.serial_port.is_open:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        """Connect to serial port"""
        port = self.port_var.get()
        baudrate = int(self.baudrate_var.get())

        if not port:
            messagebox.showerror("Error", "Please select a serial port")
            return

        try:
            self.serial_port = serial.Serial(port, baudrate, timeout=1)
            if self.serial_port.is_open:
                self.connect_button.config(text="Disconnect", bg="#f44336")
                self.status_var.set(f"Connected to {port}")

                # Start serial reading thread
                self.stop_thread.clear()
                self.serial_thread = threading.Thread(target=self.read_serial_data)
                self.serial_thread.daemon = True
                self.serial_thread.start()
        except Exception as e:
            messagebox.showerror("Connection Error", f"Cannot connect to {port}: {str(e)}")

    def disconnect(self):
        """Disconnect from serial port"""
        if self.serial_port and self.serial_port.is_open:
            self.stop_thread.set()
            if self.serial_thread and self.serial_thread.is_alive:
                self.serial_thread.join(timeout=1.0)
            self.serial_port.close()
            self.connect_button.config(text="Connect", bg="#4CAF50")
            self.status_var.set("Disconnected")

    def read_serial_data(self):
        """Thread function to read data from serial port"""
        while not self.stop_thread.is_set():
            try:
                if self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode('utf-8').strip()
                    if line:
                        self.process_data(line)
            except Exception as e:
                self.status_var.set(f"Error reading data: {str(e)}")
                time.sleep(0.1)

    def process_data(self, data_line):
        """Process received data"""
        try:
            # Parse data
            parts = data_line.split(',')
            if len(parts) == 6:
                mode, duration, avg_hr, max_hr, freq, count = map(float, parts)
                mode = int(mode)
                duration = int(duration)
                avg_hr = int(avg_hr)
                max_hr = int(max_hr)
                count = int(count)

                # Add to data list
                record_time = datetime.now().strftime('%H:%M:%S')
                data_entry = {
                    "mode": mode,
                    "exerciseDuration": duration,
                    "avgHeartRate": avg_hr,
                    "maxHeartRate": max_hr,
                    "finalFrequency": freq,
                    "finalJumpCount": count,
                    "recordTime": record_time
                }

                self.controller.serial_data.append(data_entry)
                self.controller.data_by_mode[mode].append(data_entry)

                # Update UI
                self.update_ui(data_entry)

                # Save to file
                self.save_to_file(data_entry)
            else:
                self.data_text.insert(tk.END, f"Format error: {data_line}\n")
                self.data_text.see(tk.END)
        except Exception as e:
            self.data_text.insert(tk.END, f"Error processing data: {str(e)}\n")
            self.data_text.see(tk.END)

    def update_ui(self, data):
        """Update UI display"""
        self.after(0, lambda: self._update_ui(data))

    def _update_ui(self, data):
        """Update UI in main thread"""
        # Update text display
        display_text = (f"Mode: {data['mode']}, "
                        f"Duration: {data['exerciseDuration']}s, "
                        f"Avg HR: {data['avgHeartRate']}BPM, "
                        f"Max HR: {data['maxHeartRate']}BPM, "
                        f"Frequency: {data['finalFrequency']:.1f} jumps/min, "
                        f"Jumps: {data['finalJumpCount']}\n")
        self.data_text.insert(tk.END, display_text)
        self.data_text.see(tk.END)

        # Update table
        mode_text = ["Timer Mode", "Countdown Mode", "Target Count Mode"][data['mode']]
        self.data_table.insert("", tk.END, values=(
            mode_text,
            data['exerciseDuration'],
            data['avgHeartRate'],
            data['maxHeartRate'],
            data['finalFrequency'],
            data['finalJumpCount']
        ))

        # Update data count
        self.data_count_var.set(f"Data Count: {len(self.controller.serial_data)}")

    def save_to_file(self, data):
        """Save data to CSV file"""
        try:
            with open(self.data_file, 'a', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow([
                    data['mode'],
                    data['exerciseDuration'],
                    data['avgHeartRate'],
                    data['maxHeartRate'],
                    data['finalFrequency'],
                    data['finalJumpCount'],
                    data['recordTime']
                ])
        except Exception as e:
            self.status_var.set(f"Error saving data: {str(e)}")


class ChartPage(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent, bg="#f0f0f0")
        self.controller = controller

        # Create navigation bar
        nav_frame = tk.Frame(self, bg="#e0e0e0", height=40)
        nav_frame.pack(fill="x")

        home_button = tk.Button(nav_frame, text="Home", command=lambda: controller.show_frame(MainPage),
                                bg="#e0e0e0", bd=0, font=("Arial", 10))
        home_button.pack(side=tk.LEFT, padx=10, pady=5)

        serial_button = tk.Button(nav_frame, text="Serial Connection",
                                  command=lambda: controller.show_frame(SerialPage),
                                  bg="#e0e0e0", bd=0, font=("Arial", 10))
        serial_button.pack(side=tk.LEFT, padx=10, pady=5)

        # Create chart control area
        control_frame = tk.LabelFrame(self, text="Chart Settings", font=("Arial", 12), bg="#f0f0f0")
        control_frame.pack(fill="x", padx=20, pady=10)

        # Mode selection
        tk.Label(control_frame, text="Select Mode:", font=("Arial", 10), bg="#f0f0f0").grid(row=0, column=0, padx=10,
                                                                                            pady=10)
        self.mode_var = tk.IntVar(value=0)

        mode_frame = tk.Frame(control_frame, bg="#f0f0f0")
        mode_frame.grid(row=0, column=1, padx=10, pady=10)

        for i, mode_text in enumerate(["Timer Mode", "Countdown Mode", "Target Count Mode"]):
            tk.Radiobutton(mode_frame, text=mode_text, variable=self.mode_var, value=i,
                           bg="#f0f0f0", font=("Arial", 10), command=self.update_chart).pack(side=tk.LEFT, padx=10)

        # Y-axis selection
        tk.Label(control_frame, text="Y-axis Data:", font=("Arial", 10), bg="#f0f0f0").grid(row=0, column=2, padx=10,
                                                                                            pady=10)
        self.y_axis_var = tk.StringVar(value="exerciseDuration")

        y_axis_frame = tk.Frame(control_frame, bg="#f0f0f0")
        y_axis_frame.grid(row=0, column=3, padx=10, pady=10)

        y_axis_options = {
            "exerciseDuration": "Duration (s)",
            "avgHeartRate": "Average Heart Rate",
            "maxHeartRate": "Maximum Heart Rate",
            "finalFrequency": "Jumping Frequency",
            "finalJumpCount": "Jumps"
        }

        for key, value in y_axis_options.items():
            tk.Radiobutton(y_axis_frame, text=value, variable=self.y_axis_var, value=key,
                           bg="#f0f0f0", font=("Arial", 10), command=self.update_chart).pack(anchor=tk.W, padx=10)

        # Refresh button
        refresh_button = tk.Button(control_frame, text="Refresh Chart", command=self.update_chart,
                                   bg="#4CAF50", fg="white", font=("Arial", 10))
        refresh_button.grid(row=0, column=4, padx=20, pady=10)

        # Create chart area
        chart_frame = tk.LabelFrame(self, text="Data Chart", font=("Arial", 12), bg="#f0f0f0")
        chart_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Create chart
        self.figure = plt.Figure(figsize=(8, 6), dpi=100)
        self.chart = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Create statistics area
        stats_frame = tk.LabelFrame(self, text="Statistics", font=("Arial", 12), bg="#f0f0f0")
        stats_frame.pack(fill="x", padx=20, pady=10)

        self.stats_text = tk.Text(stats_frame, height=4, font=("Arial", 10), wrap=tk.WORD)
        self.stats_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.stats_text.config(state=tk.DISABLED)

        # Initial chart update
        self.update_chart()

    def update_chart(self):
        """Update chart display"""
        # Get current selections
        mode = self.mode_var.get()
        y_axis = self.y_axis_var.get()

        # Get data for selected mode
        data = self.controller.data_by_mode.get(mode, [])

        # Clear chart
        self.chart.clear()

        # If data exists, plot the chart
        if data:
            # Prepare X and Y axis data
            x_data = list(range(1, len(data) + 1))
            y_data = [entry[y_axis] for entry in data]

            # Set Y-axis label mapping
            y_labels = {
                "exerciseDuration": "Duration (s)",
                "avgHeartRate": "Average Heart Rate (BPM)",
                "maxHeartRate": "Maximum Heart Rate (BPM)",
                "finalFrequency": "Jumping Frequency (jumps/min)",
                "finalJumpCount": "Jumps"
            }

            # Plot chart
            self.chart.plot(x_data, y_data, 'o-', color='#2196F3')
            self.chart.set_title(
                f"{['Timer Mode', 'Countdown Mode', 'Target Count Mode'][mode]} - {y_labels[y_axis]} Trend",
                fontsize=14)
            self.chart.set_xlabel("Record Number", fontsize=12)
            self.chart.set_ylabel(y_labels[y_axis], fontsize=12)
            self.chart.grid(True, linestyle='--', alpha=0.7)

            # Add data labels
            for x, y in zip(x_data, y_data):
                self.chart.annotate(f'{y}', (x, y), textcoords="offset points",
                                    xytext=(0, 10), ha='center')

            # Calculate statistics
            if y_axis in ["avgHeartRate", "maxHeartRate", "finalFrequency", "finalJumpCount", "exerciseDuration"]:
                avg_value = sum(y_data) / len(y_data)
                max_value = max(y_data)
                min_value = min(y_data)

                # Update statistics
                self.stats_text.config(state=tk.NORMAL)
                self.stats_text.delete(1.0, tk.END)
                self.stats_text.insert(tk.END,
                                       f"Data Points: {len(data)}\n"
                                       f"Average: {avg_value:.2f}\n"
                                       f"Maximum: {max_value}\n"
                                       f"Minimum: {min_value}")
                self.stats_text.config(state=tk.DISABLED)
        else:
            # Show message when no data available
            self.chart.text(0.5, 0.5, 'No data available. Please receive data via serial port first.',
                            horizontalalignment='center',
                            verticalalignment='center',
                            transform=self.chart.transAxes,
                            fontsize=14,
                            color='red',
                            alpha=0.7)
            self.chart.set_title("Data Chart", fontsize=14)
            self.chart.axis('off')

            # Clear statistics
            self.stats_text.config(state=tk.NORMAL)
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(tk.END, "No data available")
            self.stats_text.config(state=tk.DISABLED)

        # Update canvas
        self.figure.tight_layout()
        self.canvas.draw()


if __name__ == "__main__":
    app = SmartRopeApp()
    app.mainloop()