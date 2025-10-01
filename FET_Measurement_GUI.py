"""
FET Measurement GUI Application
A modular GUI-based application for FET I-V measurements using Keithley 2450.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
import pyvisa
import os
from datetime import datetime
import queue

# Import configuration
try:
    from measurement_config import DEFAULT_SETTINGS
except ImportError:
    # Fallback default settings if config file is missing
    DEFAULT_SETTINGS = {
        'GPIB_VDS': 'GPIB0::24::INSTR',
        'GPIB_VG': 'GPIB0::18::INSTR',
        'VDS_CURRENT_LIMIT': 0.1,
        'VG_CURRENT_LIMIT': 0.1,
        'IDVD_DEFAULTS': {
            'VG_FROM': 0, 'VG_TO': 10, 'VG_STEP': 5, 'VG_DELAY': 0.5,
            'VDS_FROM': -1, 'VDS_TO': 1, 'VDS_STEP': 0.05, 'VDS_DELAY': 0.2
        },
        'IDVG_DEFAULTS': {
            'VDS_FROM': 0.2, 'VDS_TO': 0.4, 'VDS_STEP': 0.2, 'VDS_DELAY': 0.5,
            'VG_FROM': -10, 'VG_TO': 10, 'VG_STEP': 0.5, 'VG_DELAY': 0.2
        }
    }


class InstrumentController:
    """Handles all instrument communication and control."""
    
    def __init__(self):
        self.rm = None
        self.keithley_vds = None
        self.keithley_vg = None
        self.is_connected = False
        
    def connect_instruments(self, gpib_vds, gpib_vg):
        """Connect to the Keithley instruments."""
        try:
            self.rm = pyvisa.ResourceManager()
            self.keithley_vds = self.rm.open_resource(gpib_vds)
            self.keithley_vg = self.rm.open_resource(gpib_vg)
            
            # Set timeouts and termination
            for instr in [self.keithley_vds, self.keithley_vg]:
                instr.timeout = 5000
                instr.write_termination = '\n'
                instr.read_termination = '\n'
            
            self.is_connected = True
            return True, "Instruments connected successfully"
            
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
    
    def initialize_instruments(self, vds_limit, vg_limit):
        """Initialize the instruments with proper settings."""
        try:
            # Initialize VDS Keithley
            self.keithley_vds.write('*RST')
            self.keithley_vds.write(':SOUR:FUNC VOLT')
            self.keithley_vds.write(':SOUR:VOLT:DEL 0')
            self.keithley_vds.write(':SENS:FUNC "CURR"')
            self.keithley_vds.write('SENS:CURR:NPLC 1')
            self.keithley_vds.write(f':SOUR:VOLT:ILIM:LEV {vds_limit}')
            self.keithley_vds.write(':OUTP ON')
            
            # Initialize VG Keithley
            self.keithley_vg.write('*RST')
            self.keithley_vg.write(':SOUR:FUNC VOLT')
            self.keithley_vg.write(':SOUR:VOLT:DEL 0')
            self.keithley_vg.write(':SENS:FUNC "CURR"')
            self.keithley_vg.write('SENS:CURR:NPLC 1')
            self.keithley_vg.write(f':SOUR:VOLT:ILIM:LEV {vg_limit}')
            self.keithley_vg.write(':OUTP ON')
            
            return True, "Instruments initialized successfully"
            
        except Exception as e:
            return False, f"Initialization failed: {str(e)}"
    
    def set_voltage_and_read(self, instrument, voltage):
        """Set voltage and read current from specified instrument."""
        try:
            if instrument == 'vds':
                self.keithley_vds.write(f":SOUR:VOLT {voltage}")
                self.keithley_vds.write(":READ?")
                response = self.keithley_vds.read()
            elif instrument == 'vg':
                self.keithley_vg.write(f":SOUR:VOLT {voltage}")
                self.keithley_vg.write(":READ?")
                response = self.keithley_vg.read()
            else:
                raise ValueError("Invalid instrument specified")
                
            return float(response)
        except Exception as e:
            raise Exception(f"Measurement error: {str(e)}")
    
    def read_current(self, instrument):
        """Read current from specified instrument without changing voltage."""
        try:
            if instrument == 'vds':
                self.keithley_vds.write(":READ?")
                response = self.keithley_vds.read()
            elif instrument == 'vg':
                self.keithley_vg.write(":READ?")
                response = self.keithley_vg.read()
            else:
                raise ValueError("Invalid instrument specified")
                
            return float(response)
        except Exception as e:
            raise Exception(f"Read error: {str(e)}")
    
    def disconnect(self):
        """Safely disconnect from instruments."""
        try:
            if self.keithley_vds:
                self.keithley_vds.write(":OUTP OFF")
                self.keithley_vds.write("*RST")
                self.keithley_vds.close()
            
            if self.keithley_vg:
                self.keithley_vg.write(":OUTP OFF")
                self.keithley_vg.write("*RST")
                self.keithley_vg.close()
            
            if self.rm:
                self.rm.close()
                
            self.is_connected = False
            
        except Exception as e:
            print(f"Disconnect error: {str(e)}")


class DataManager:
    """Handles data storage and CSV file operations."""
    
    def __init__(self):
        self.csv_file = None
        self.data_buffer = []
        
    def initialize_csv(self, save_dir, filename, measurement_type):
        """Initialize CSV file with headers based on measurement type."""
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            
        if measurement_type == "IDVD":
            columns = ["VD (V)", "IDS (A)", "IG (A)"]
            csv_filename = f"{filename}-IDVD.csv"
        else:  # IDVG
            columns = ["VG (V)", "IDS (A)", "IG (A)"]
            csv_filename = f"{filename}-IDVG.csv"
            
        self.csv_file = os.path.join(save_dir, csv_filename)
        
        if not os.path.exists(self.csv_file):
            df = pd.DataFrame(columns=columns)
            df.to_csv(self.csv_file, index=False)
            
        return self.csv_file
    
    def append_data(self, data_row):
        """Append data to CSV file."""
        try:
            # Read existing data
            df = pd.read_csv(self.csv_file)
            
            # Add new row - fix for pandas FutureWarning
            if len(df) == 0:
                # If dataframe is empty, create new one
                df = pd.DataFrame([data_row], columns=df.columns)
            else:
                # Append to existing dataframe
                new_row = pd.DataFrame([data_row], columns=df.columns)
                df = pd.concat([df, new_row], ignore_index=True)
            
            # Save back to file
            df.to_csv(self.csv_file, index=False)
            
        except Exception as e:
            raise Exception(f"Data save error: {str(e)}")


class MeasurementController:
    """Controls the measurement process and communicates with GUI."""
    
    def __init__(self, instrument_ctrl, data_manager, data_queue):
        self.instrument_ctrl = instrument_ctrl
        self.data_manager = data_manager
        self.data_queue = data_queue
        self.is_measuring = False
        self.is_paused = False
        self.measurement_thread = None
        
    def start_idvd_measurement(self, params):
        """Start ID-VD measurement in a separate thread."""
        if self.is_measuring:
            return False, "Measurement already in progress"
            
        self.is_measuring = True
        self.is_paused = False
        
        self.measurement_thread = threading.Thread(
            target=self._idvd_measurement_worker, 
            args=(params,), 
            daemon=True
        )
        self.measurement_thread.start()
        return True, "Measurement started"
    
    def start_idvg_measurement(self, params):
        """Start ID-VG measurement in a separate thread."""
        if self.is_measuring:
            return False, "Measurement already in progress"
            
        self.is_measuring = True
        self.is_paused = False
        
        self.measurement_thread = threading.Thread(
            target=self._idvg_measurement_worker, 
            args=(params,), 
            daemon=True
        )
        self.measurement_thread.start()
        return True, "Measurement started"
    
    def pause_measurement(self):
        """Pause the current measurement."""
        self.is_paused = True
        
    def resume_measurement(self):
        """Resume the paused measurement."""
        self.is_paused = False
        
    def stop_measurement(self):
        """Stop the current measurement."""
        self.is_measuring = False
        self.is_paused = False
        
    def _idvd_measurement_worker(self, params):
        """Worker function for ID-VD measurement."""
        try:
            # Extract parameters
            vg_from, vg_to, vg_step = params['vg_range']
            vds_from, vds_to, vds_step = params['vds_range']
            vg_delay, vds_delay = params['delays']
            
            vg_values = np.linspace(vg_from, vg_to, int((vg_to - vg_from)/vg_step) + 1)
            total_points = len(vg_values) * len(np.linspace(vds_from, vds_to, int((vds_to - vds_from)/vds_step) + 1)) * 2
            current_point = 0
            
            for vg in vg_values:
                if not self.is_measuring:
                    break
                    
                # Set gate voltage gradually
                self._set_voltage_gradually('vg', vg, vg_delay)
                
                # Forward sweep
                vds_values = np.linspace(vds_from, vds_to, int((vds_to - vds_from)/vds_step) + 1)
                for vds in vds_values:
                    if not self.is_measuring:
                        break
                        
                    while self.is_paused:
                        time.sleep(0.1)
                        if not self.is_measuring:
                            break
                    
                    try:
                        ids = self.instrument_ctrl.set_voltage_and_read('vds', vds)
                        ig = self.instrument_ctrl.read_current('vg')
                        
                        # Send data to GUI
                        data_point = {
                            'vd': vds,
                            'ids': ids,
                            'ig': ig,
                            'vg': vg,
                            'progress': (current_point / total_points) * 100
                        }
                        self.data_queue.put(('data', data_point))
                        
                        # Save to CSV
                        self.data_manager.append_data([vds, ids, ig])
                        
                        current_point += 1
                        time.sleep(vds_delay)
                        
                    except Exception as e:
                        self.data_queue.put(('error', f"Measurement error: {str(e)}"))
                        break
                
                # Reverse sweep
                for vds in reversed(vds_values):
                    if not self.is_measuring:
                        break
                        
                    while self.is_paused:
                        time.sleep(0.1)
                        if not self.is_measuring:
                            break
                    
                    try:
                        ids = self.instrument_ctrl.set_voltage_and_read('vds', vds)
                        ig = self.instrument_ctrl.read_current('vg')
                        
                        data_point = {
                            'vd': vds,
                            'ids': ids,
                            'ig': ig,
                            'vg': vg,
                            'progress': (current_point / total_points) * 100
                        }
                        self.data_queue.put(('data', data_point))
                        self.data_manager.append_data([vds, ids, ig])
                        
                        current_point += 1
                        time.sleep(vds_delay)
                        
                    except Exception as e:
                        self.data_queue.put(('error', f"Measurement error: {str(e)}"))
                        break
                
                # Return VDS to 0V
                self.instrument_ctrl.set_voltage_and_read('vds', 0)
                time.sleep(vg_delay)
            
            self.data_queue.put(('complete', 'Measurement completed successfully'))
            
        except Exception as e:
            self.data_queue.put(('error', f"Measurement failed: {str(e)}"))
        finally:
            self.is_measuring = False
    
    def _idvg_measurement_worker(self, params):
        """Worker function for ID-VG measurement."""
        try:
            # Extract parameters
            vds_from, vds_to, vds_step = params['vds_range']
            vg_from, vg_to, vg_step = params['vg_range']
            vds_delay, vg_delay = params['delays']
            
            vds_values = np.linspace(vds_from, vds_to, int((vds_to - vds_from)/vds_step) + 1)
            total_points = len(vds_values) * len(np.linspace(vg_from, vg_to, int((vg_to - vg_from)/vg_step) + 1))
            current_point = 0
            
            for vds in vds_values:
                if not self.is_measuring:
                    break
                    
                # Set drain voltage gradually
                self._set_voltage_gradually('vds', vds, vds_delay)
                
                # Sweep gate voltage
                vg_values = np.linspace(vg_from, vg_to, int((vg_to - vg_from)/vg_step) + 1)
                for vg in vg_values:
                    if not self.is_measuring:
                        break
                        
                    while self.is_paused:
                        time.sleep(0.1)
                        if not self.is_measuring:
                            break
                    
                    try:
                        ids = self.instrument_ctrl.read_current('vds')
                        ig = self.instrument_ctrl.set_voltage_and_read('vg', vg)
                        
                        # Send data to GUI
                        data_point = {
                            'vg': vg,
                            'ids': ids,
                            'ig': ig,
                            'vds': vds,
                            'progress': (current_point / total_points) * 100
                        }
                        self.data_queue.put(('data', data_point))
                        
                        # Save to CSV
                        self.data_manager.append_data([vg, ids, ig])
                        
                        current_point += 1
                        time.sleep(vg_delay)
                        
                    except Exception as e:
                        self.data_queue.put(('error', f"Measurement error: {str(e)}"))
                        break
                
                time.sleep(vds_delay)
            
            self.data_queue.put(('complete', 'Measurement completed successfully'))
            
        except Exception as e:
            self.data_queue.put(('error', f"Measurement failed: {str(e)}"))
        finally:
            self.is_measuring = False
    
    def _set_voltage_gradually(self, instrument, target_voltage, delay):
        """Gradually set voltage to avoid sudden jumps."""
        try:
            if instrument == 'vds':
                current_voltage = 0  # Assume starting from 0V
            else:
                current_voltage = 0
                
            if target_voltage != current_voltage:
                steps = 10
                voltage_step = (target_voltage - current_voltage) / steps
                
                for i in range(steps + 1):
                    voltage = current_voltage + i * voltage_step
                    self.instrument_ctrl.set_voltage_and_read(instrument, voltage)
                    time.sleep(delay / steps)
                    
        except Exception as e:
            raise Exception(f"Voltage setting error: {str(e)}")


class FETMeasurementGUI:
    """Main GUI application class."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("FET I-V Measurement System - Real-time Live Data")
        
        # Make window responsive to different screen sizes
        self.setup_responsive_window()
        
        # Initialize components
        self.instrument_ctrl = InstrumentController()
        self.data_manager = DataManager()
        self.data_queue = queue.Queue()
        self.measurement_ctrl = MeasurementController(
            self.instrument_ctrl, self.data_manager, self.data_queue
        )
        
        # Data storage for plotting
        self.plot_data = {
            'vd': [], 'ids': [], 'ig': [], 'vg': []
        }
        
        # Animation and refresh settings for live data
        self.update_interval = 50  # milliseconds - faster for more responsive live updates
        self.max_plot_points = 1000  # Limit points for better performance
        
        # Create GUI elements
        self.create_widgets()
        self.setup_plots()
        
        # Start real-time data monitoring with higher frequency
        self.monitor_data_queue()
    
    def setup_responsive_window(self):
        """Setup responsive window that adapts to different screen sizes."""
        # Get screen dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Calculate optimal window size (80% of screen, with limits)
        min_width, min_height = 1000, 700
        max_width, max_height = 1600, 1000
        
        optimal_width = max(min_width, min(int(screen_width * 0.8), max_width))
        optimal_height = max(min_height, min(int(screen_height * 0.8), max_height))
        
        # Center window on screen
        x = (screen_width - optimal_width) // 2
        y = (screen_height - optimal_height) // 2
        
        self.root.geometry(f"{optimal_width}x{optimal_height}+{x}+{y}")
        self.root.minsize(min_width, min_height)
        
        # Make window resizable
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Handle window resize events
        self.root.bind('<Configure>', self.on_window_resize)
        
    def on_window_resize(self, event):
        """Handle window resize events to maintain proper layout."""
        if event.widget == self.root:
            # Update plot window size if it exists
            if hasattr(self, 'plot_window') and self.plot_window.winfo_exists():
                try:
                    # Resize plot window proportionally
                    main_width = self.root.winfo_width()
                    main_height = self.root.winfo_height()
                    
                    plot_width = max(600, int(main_width * 0.7))
                    plot_height = max(500, int(main_height * 0.8))
                    
                    self.plot_window.geometry(f"{plot_width}x{plot_height}")
                    
                    # Adjust plot layout
                    self.fig.tight_layout(pad=2.0)
                    if hasattr(self, 'canvas'):
                        self.canvas.draw_idle()
                except:
                    pass
        
    def create_widgets(self):
        """Create all GUI widgets."""
        # Create notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Connection tab
        self.create_connection_tab(notebook)
        
        # Measurement tabs
        self.create_idvd_tab(notebook)
        self.create_idvg_tab(notebook)
        
        # Status frame at bottom
        self.create_status_frame()
        
    def create_connection_tab(self, notebook):
        """Create instrument connection tab."""
        conn_frame = ttk.Frame(notebook)
        notebook.add(conn_frame, text="Connection")
        
        # GPIB Settings
        gpib_frame = ttk.LabelFrame(conn_frame, text="GPIB Settings")
        gpib_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(gpib_frame, text="VDS Keithley GPIB:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.gpib_vds_var = tk.StringVar(value=DEFAULT_SETTINGS['GPIB_VDS'])
        ttk.Entry(gpib_frame, textvariable=self.gpib_vds_var, width=20).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(gpib_frame, text="VG Keithley GPIB:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.gpib_vg_var = tk.StringVar(value=DEFAULT_SETTINGS['GPIB_VG'])
        ttk.Entry(gpib_frame, textvariable=self.gpib_vg_var, width=20).grid(row=1, column=1, padx=5, pady=5)
        
        # Current Limits
        limits_frame = ttk.LabelFrame(conn_frame, text="Current Limits")
        limits_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(limits_frame, text="VDS Current Limit (A):").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.vds_limit_var = tk.StringVar(value=str(DEFAULT_SETTINGS['VDS_CURRENT_LIMIT']))
        ttk.Entry(limits_frame, textvariable=self.vds_limit_var, width=10).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(limits_frame, text="VG Current Limit (A):").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.vg_limit_var = tk.StringVar(value=str(DEFAULT_SETTINGS['VG_CURRENT_LIMIT']))
        ttk.Entry(limits_frame, textvariable=self.vg_limit_var, width=10).grid(row=1, column=1, padx=5, pady=5)
        
        # Connection buttons
        btn_frame = ttk.Frame(conn_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        self.connect_btn = ttk.Button(btn_frame, text="Connect Instruments", command=self.connect_instruments)
        self.connect_btn.pack(side='left', padx=5)
        
        self.disconnect_btn = ttk.Button(btn_frame, text="Disconnect", command=self.disconnect_instruments, state='disabled')
        self.disconnect_btn.pack(side='left', padx=5)
        
        # Connection status
        self.conn_status_var = tk.StringVar(value="Not connected")
        ttk.Label(btn_frame, textvariable=self.conn_status_var).pack(side='left', padx=20)
        
    def create_idvd_tab(self, notebook):
        """Create ID-VD measurement tab."""
        idvd_frame = ttk.Frame(notebook)
        notebook.add(idvd_frame, text="ID-VD Measurement")
        
        # Parameters frame
        params_frame = ttk.LabelFrame(idvd_frame, text="Measurement Parameters")
        params_frame.pack(fill='x', padx=10, pady=5)
        
        # File settings
        file_frame = ttk.Frame(params_frame)
        file_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(file_frame, text="Save Directory:").pack(side='left')
        self.idvd_dir_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.idvd_dir_var, width=50).pack(side='left', padx=5)
        ttk.Button(file_frame, text="Browse", command=lambda: self.browse_directory(self.idvd_dir_var)).pack(side='left')
        
        filename_frame = ttk.Frame(params_frame)
        filename_frame.pack(fill='x', padx=5, pady=2)
        ttk.Label(filename_frame, text="Filename:").pack(side='left')
        self.idvd_filename_var = tk.StringVar(value=f"{datetime.now().strftime('%Y%m%d')}_sample")
        ttk.Entry(filename_frame, textvariable=self.idvd_filename_var, width=30).pack(side='left', padx=(5, 0))
        
        # VG parameters
        vg_frame = ttk.LabelFrame(params_frame, text="Gate Voltage (VG)")
        vg_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(vg_frame, text="From (V):").grid(row=0, column=0, padx=5, pady=2)
        self.idvd_vg_from_var = tk.StringVar(value=str(DEFAULT_SETTINGS['IDVD_DEFAULTS']['VG_FROM']))
        ttk.Entry(vg_frame, textvariable=self.idvd_vg_from_var, width=10).grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(vg_frame, text="To (V):").grid(row=0, column=2, padx=5, pady=2)
        self.idvd_vg_to_var = tk.StringVar(value=str(DEFAULT_SETTINGS['IDVD_DEFAULTS']['VG_TO']))
        ttk.Entry(vg_frame, textvariable=self.idvd_vg_to_var, width=10).grid(row=0, column=3, padx=5, pady=2)
        
        ttk.Label(vg_frame, text="Step (V):").grid(row=0, column=4, padx=5, pady=2)
        self.idvd_vg_step_var = tk.StringVar(value=str(DEFAULT_SETTINGS['IDVD_DEFAULTS']['VG_STEP']))
        ttk.Entry(vg_frame, textvariable=self.idvd_vg_step_var, width=10).grid(row=0, column=5, padx=5, pady=2)
        
        ttk.Label(vg_frame, text="Delay (s):").grid(row=1, column=0, padx=5, pady=2)
        self.idvd_vg_delay_var = tk.StringVar(value=str(DEFAULT_SETTINGS['IDVD_DEFAULTS']['VG_DELAY']))
        ttk.Entry(vg_frame, textvariable=self.idvd_vg_delay_var, width=10).grid(row=1, column=1, padx=5, pady=2)
        
        # VDS parameters
        vds_frame = ttk.LabelFrame(params_frame, text="Drain Voltage (VDS)")
        vds_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(vds_frame, text="From (V):").grid(row=0, column=0, padx=5, pady=2)
        self.idvd_vds_from_var = tk.StringVar(value=str(DEFAULT_SETTINGS['IDVD_DEFAULTS']['VDS_FROM']))
        ttk.Entry(vds_frame, textvariable=self.idvd_vds_from_var, width=10).grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(vds_frame, text="To (V):").grid(row=0, column=2, padx=5, pady=2)
        self.idvd_vds_to_var = tk.StringVar(value=str(DEFAULT_SETTINGS['IDVD_DEFAULTS']['VDS_TO']))
        ttk.Entry(vds_frame, textvariable=self.idvd_vds_to_var, width=10).grid(row=0, column=3, padx=5, pady=2)
        
        ttk.Label(vds_frame, text="Step (V):").grid(row=0, column=4, padx=5, pady=2)
        self.idvd_vds_step_var = tk.StringVar(value=str(DEFAULT_SETTINGS['IDVD_DEFAULTS']['VDS_STEP']))
        ttk.Entry(vds_frame, textvariable=self.idvd_vds_step_var, width=10).grid(row=0, column=5, padx=5, pady=2)
        
        ttk.Label(vds_frame, text="Delay (s):").grid(row=1, column=0, padx=5, pady=2)
        self.idvd_vds_delay_var = tk.StringVar(value=str(DEFAULT_SETTINGS['IDVD_DEFAULTS']['VDS_DELAY']))
        ttk.Entry(vds_frame, textvariable=self.idvd_vds_delay_var, width=10).grid(row=1, column=1, padx=5, pady=2)
        
        # Control buttons
        control_frame = ttk.Frame(idvd_frame)
        control_frame.pack(fill='x', padx=10, pady=5)
        
        self.idvd_start_btn = ttk.Button(control_frame, text="Start Measurement", command=self.start_idvd_measurement)
        self.idvd_start_btn.pack(side='left', padx=5)
        
        self.idvd_pause_btn = ttk.Button(control_frame, text="Pause", command=self.pause_measurement, state='disabled')
        self.idvd_pause_btn.pack(side='left', padx=5)
        
        self.idvd_stop_btn = ttk.Button(control_frame, text="Stop", command=self.stop_measurement, state='disabled')
        self.idvd_stop_btn.pack(side='left', padx=5)
        
        ttk.Button(control_frame, text="Clear Plots", command=self.clear_plot_data).pack(side='left', padx=5)
        
        # Progress bar
        self.idvd_progress = ttk.Progressbar(control_frame, mode='determinate')
        self.idvd_progress.pack(side='right', padx=10, fill='x', expand=True)
        
    def create_idvg_tab(self, notebook):
        """Create ID-VG measurement tab."""
        idvg_frame = ttk.Frame(notebook)
        notebook.add(idvg_frame, text="ID-VG Measurement")
        
        # Parameters frame
        params_frame = ttk.LabelFrame(idvg_frame, text="Measurement Parameters")
        params_frame.pack(fill='x', padx=10, pady=5)
        
        # File settings
        file_frame = ttk.Frame(params_frame)
        file_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(file_frame, text="Save Directory:").pack(side='left')
        self.idvg_dir_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.idvg_dir_var, width=50).pack(side='left', padx=5)
        ttk.Button(file_frame, text="Browse", command=lambda: self.browse_directory(self.idvg_dir_var)).pack(side='left')
        
        filename_frame = ttk.Frame(params_frame)
        filename_frame.pack(fill='x', padx=5, pady=2)
        ttk.Label(filename_frame, text="Filename:").pack(side='left')
        self.idvg_filename_var = tk.StringVar(value=f"{datetime.now().strftime('%Y%m%d')}_sample")
        ttk.Entry(filename_frame, textvariable=self.idvg_filename_var, width=30).pack(side='left', padx=(5, 0))
        
        # VDS parameters
        vds_frame = ttk.LabelFrame(params_frame, text="Drain Voltage (VDS)")
        vds_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(vds_frame, text="From (V):").grid(row=0, column=0, padx=5, pady=2)
        self.idvg_vds_from_var = tk.StringVar(value=str(DEFAULT_SETTINGS['IDVG_DEFAULTS']['VDS_FROM']))
        ttk.Entry(vds_frame, textvariable=self.idvg_vds_from_var, width=10).grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(vds_frame, text="To (V):").grid(row=0, column=2, padx=5, pady=2)
        self.idvg_vds_to_var = tk.StringVar(value=str(DEFAULT_SETTINGS['IDVG_DEFAULTS']['VDS_TO']))
        ttk.Entry(vds_frame, textvariable=self.idvg_vds_to_var, width=10).grid(row=0, column=3, padx=5, pady=2)
        
        ttk.Label(vds_frame, text="Step (V):").grid(row=0, column=4, padx=5, pady=2)
        self.idvg_vds_step_var = tk.StringVar(value=str(DEFAULT_SETTINGS['IDVG_DEFAULTS']['VDS_STEP']))
        ttk.Entry(vds_frame, textvariable=self.idvg_vds_step_var, width=10).grid(row=0, column=5, padx=5, pady=2)
        
        ttk.Label(vds_frame, text="Delay (s):").grid(row=1, column=0, padx=5, pady=2)
        self.idvg_vds_delay_var = tk.StringVar(value=str(DEFAULT_SETTINGS['IDVG_DEFAULTS']['VDS_DELAY']))
        ttk.Entry(vds_frame, textvariable=self.idvg_vds_delay_var, width=10).grid(row=1, column=1, padx=5, pady=2)
        
        # VG parameters
        vg_frame = ttk.LabelFrame(params_frame, text="Gate Voltage (VG)")
        vg_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(vg_frame, text="From (V):").grid(row=0, column=0, padx=5, pady=2)
        self.idvg_vg_from_var = tk.StringVar(value=str(DEFAULT_SETTINGS['IDVG_DEFAULTS']['VG_FROM']))
        ttk.Entry(vg_frame, textvariable=self.idvg_vg_from_var, width=10).grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(vg_frame, text="To (V):").grid(row=0, column=2, padx=5, pady=2)
        self.idvg_vg_to_var = tk.StringVar(value=str(DEFAULT_SETTINGS['IDVG_DEFAULTS']['VG_TO']))
        ttk.Entry(vg_frame, textvariable=self.idvg_vg_to_var, width=10).grid(row=0, column=3, padx=5, pady=2)
        
        ttk.Label(vg_frame, text="Step (V):").grid(row=0, column=4, padx=5, pady=2)
        self.idvg_vg_step_var = tk.StringVar(value=str(DEFAULT_SETTINGS['IDVG_DEFAULTS']['VG_STEP']))
        ttk.Entry(vg_frame, textvariable=self.idvg_vg_step_var, width=10).grid(row=0, column=5, padx=5, pady=2)
        
        ttk.Label(vg_frame, text="Delay (s):").grid(row=1, column=0, padx=5, pady=2)
        self.idvg_vg_delay_var = tk.StringVar(value=str(DEFAULT_SETTINGS['IDVG_DEFAULTS']['VG_DELAY']))
        ttk.Entry(vg_frame, textvariable=self.idvg_vg_delay_var, width=10).grid(row=1, column=1, padx=5, pady=2)
        
        # Control buttons
        control_frame = ttk.Frame(idvg_frame)
        control_frame.pack(fill='x', padx=10, pady=5)
        
        self.idvg_start_btn = ttk.Button(control_frame, text="Start Measurement", command=self.start_idvg_measurement)
        self.idvg_start_btn.pack(side='left', padx=5)
        
        self.idvg_pause_btn = ttk.Button(control_frame, text="Pause", command=self.pause_measurement, state='disabled')
        self.idvg_pause_btn.pack(side='left', padx=5)
        
        self.idvg_stop_btn = ttk.Button(control_frame, text="Stop", command=self.stop_measurement, state='disabled')
        self.idvg_stop_btn.pack(side='left', padx=5)
        
        ttk.Button(control_frame, text="Clear Plots", command=self.clear_plot_data).pack(side='left', padx=5)
        
        # Progress bar
        self.idvg_progress = ttk.Progressbar(control_frame, mode='determinate')
        self.idvg_progress.pack(side='right', padx=10, fill='x', expand=True)
        
    def create_status_frame(self):
        """Create status frame at bottom of window."""
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill='x', padx=10, pady=5)
        
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side='left')
        
        # Real-time values display
        values_frame = ttk.Frame(status_frame)
        values_frame.pack(side='right')
        
        ttk.Label(values_frame, text="Current Values:").pack(side='left', padx=5)
        self.current_values_var = tk.StringVar(value="VDS: 0V, IDS: 0A, VG: 0V, IG: 0A")
        ttk.Label(values_frame, textvariable=self.current_values_var).pack(side='left', padx=5)
        
    def setup_plots(self):
        """Setup matplotlib plots for real-time data visualization with responsive design."""
        # Create plot window with dynamic sizing
        self.plot_window = tk.Toplevel(self.root)
        self.plot_window.title("LIVE DATA - Real-time Measurement Plots")
        
        # Calculate initial plot window size based on main window
        main_width = self.root.winfo_reqwidth()
        main_height = self.root.winfo_reqheight()
        plot_width = max(700, int(main_width * 0.8))
        plot_height = max(550, int(main_height * 0.8))
        
        # Position plot window next to main window
        main_x = self.root.winfo_x() if self.root.winfo_x() > 0 else 100
        main_y = self.root.winfo_y() if self.root.winfo_y() > 0 else 100
        plot_x = main_x + main_width + 10
        plot_y = main_y
        
        self.plot_window.geometry(f"{plot_width}x{plot_height}+{plot_x}+{plot_y}")
        self.plot_window.protocol("WM_DELETE_WINDOW", self.hide_plot_window)
        
        # Make plot window resizable
        self.plot_window.columnconfigure(0, weight=1)
        self.plot_window.rowconfigure(0, weight=1)
        self.plot_window.minsize(600, 450)
        
        # Create matplotlib figure with responsive sizing
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(10, 8))
        self.fig.suptitle("LIVE MEASUREMENT DATA", fontsize=14, fontweight='bold', color='red')
        self.fig.tight_layout(pad=4.0)
        
        # Setup IDS plot with live styling
        self.line1, = self.ax1.plot([], [], 'b-o', markersize=3, linewidth=2, alpha=0.8)
        self.ax1.set_xlabel("Voltage (V)", fontsize=11)
        self.ax1.set_ylabel("IDS (A)", fontsize=11)
        self.ax1.set_title("Drain Current - Waiting for data...", fontsize=12)
        self.ax1.grid(True, alpha=0.3)
        self.ax1.set_facecolor('#f8f9fa')
        
        # Setup IG plot with live styling
        self.line2, = self.ax2.plot([], [], 'r-o', markersize=3, linewidth=2, alpha=0.8)
        self.ax2.set_xlabel("Voltage (V)", fontsize=11)
        self.ax2.set_ylabel("IG (A)", fontsize=11)
        self.ax2.set_title("Gate Current - Waiting for data...", fontsize=12)
        self.ax2.grid(True, alpha=0.3)
        self.ax2.set_facecolor('#f8f9fa')
        
        # Embed plot in tkinter with responsive layout
        self.canvas = FigureCanvasTkAgg(self.fig, self.plot_window)
        self.canvas.draw()
        canvas_widget = self.canvas.get_tk_widget()
        canvas_widget.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Add toolbar for interaction
        from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
        toolbar = NavigationToolbar2Tk(self.canvas, self.plot_window)
        toolbar.update()
        
        # Add status bar to plot window
        self.plot_status_frame = ttk.Frame(self.plot_window)
        self.plot_status_frame.pack(fill='x', padx=5, pady=2)
        
        self.plot_status_var = tk.StringVar(value="Ready for live data streaming...")
        ttk.Label(self.plot_status_frame, textvariable=self.plot_status_var, 
                 font=('Arial', 9)).pack(side='left')
        
        # Add live indicator
        self.live_indicator = ttk.Label(self.plot_status_frame, text="[OFFLINE]", 
                                       font=('Arial', 9, 'bold'), foreground='gray')
        self.live_indicator.pack(side='right')
        
        # Initially hide plot window
        self.plot_window.withdraw()
        
    def hide_plot_window(self):
        """Hide plot window instead of destroying it."""
        self.plot_window.withdraw()
        
    def show_plot_window(self):
        """Show plot window."""
        self.plot_window.deiconify()
        
    def browse_directory(self, var):
        """Browse for directory selection."""
        directory = filedialog.askdirectory()
        if directory:
            var.set(directory)
            
    def connect_instruments(self):
        """Connect to instruments."""
        gpib_vds = self.gpib_vds_var.get()
        gpib_vg = self.gpib_vg_var.get()
        vds_limit = float(self.vds_limit_var.get())
        vg_limit = float(self.vg_limit_var.get())
        
        success, message = self.instrument_ctrl.connect_instruments(gpib_vds, gpib_vg)
        
        if success:
            success, init_message = self.instrument_ctrl.initialize_instruments(vds_limit, vg_limit)
            if success:
                self.conn_status_var.set("Connected")
                self.connect_btn.config(state='disabled')
                self.disconnect_btn.config(state='normal')
                self.idvd_start_btn.config(state='normal')
                self.idvg_start_btn.config(state='normal')
                self.status_var.set("Instruments connected and initialized")
            else:
                messagebox.showerror("Initialization Error", init_message)
        else:
            messagebox.showerror("Connection Error", message)
            
    def disconnect_instruments(self):
        """Disconnect from instruments."""
        self.instrument_ctrl.disconnect()
        self.conn_status_var.set("Not connected")
        self.connect_btn.config(state='normal')
        self.disconnect_btn.config(state='disabled')
        self.idvd_start_btn.config(state='disabled')
        self.idvg_start_btn.config(state='disabled')
        self.status_var.set("Instruments disconnected")
        
    def start_idvd_measurement(self):
        """Start ID-VD measurement."""
        if not self.instrument_ctrl.is_connected:
            messagebox.showerror("Error", "Instruments not connected")
            return
            
        if not self.idvd_dir_var.get():
            messagebox.showerror("Error", "Please select save directory")
            return
            
        try:
            # Collect parameters
            params = {
                'vg_range': (
                    float(self.idvd_vg_from_var.get()),
                    float(self.idvd_vg_to_var.get()),
                    float(self.idvd_vg_step_var.get())
                ),
                'vds_range': (
                    float(self.idvd_vds_from_var.get()),
                    float(self.idvd_vds_to_var.get()),
                    float(self.idvd_vds_step_var.get())
                ),
                'delays': (
                    float(self.idvd_vg_delay_var.get()),
                    float(self.idvd_vds_delay_var.get())
                )
            }
            
            # Initialize CSV file
            self.data_manager.initialize_csv(
                self.idvd_dir_var.get(),
                self.idvd_filename_var.get(),
                "IDVD"
            )
            
            # Clear plot data and reset plots
            self.clear_plot_data()
            
            # Start measurement
            success, message = self.measurement_ctrl.start_idvd_measurement(params)
            
            if success:
                self.idvd_start_btn.config(state='disabled')
                self.idvd_pause_btn.config(state='normal')
                self.idvd_stop_btn.config(state='normal')
                self.status_var.set("ID-VD measurement started")
                self.show_plot_window()
            else:
                messagebox.showerror("Error", message)
                
        except ValueError as e:
            messagebox.showerror("Parameter Error", f"Invalid parameter: {str(e)}")
            
    def start_idvg_measurement(self):
        """Start ID-VG measurement."""
        if not self.instrument_ctrl.is_connected:
            messagebox.showerror("Error", "Instruments not connected")
            return
            
        if not self.idvg_dir_var.get():
            messagebox.showerror("Error", "Please select save directory")
            return
            
        try:
            # Collect parameters
            params = {
                'vds_range': (
                    float(self.idvg_vds_from_var.get()),
                    float(self.idvg_vds_to_var.get()),
                    float(self.idvg_vds_step_var.get())
                ),
                'vg_range': (
                    float(self.idvg_vg_from_var.get()),
                    float(self.idvg_vg_to_var.get()),
                    float(self.idvg_vg_step_var.get())
                ),
                'delays': (
                    float(self.idvg_vds_delay_var.get()),
                    float(self.idvg_vg_delay_var.get())
                )
            }
            
            # Initialize CSV file
            self.data_manager.initialize_csv(
                self.idvg_dir_var.get(),
                self.idvg_filename_var.get(),
                "IDVG"
            )
            
            # Clear plot data and reset plots
            self.clear_plot_data()
            
            # Start measurement
            success, message = self.measurement_ctrl.start_idvg_measurement(params)
            
            if success:
                self.idvg_start_btn.config(state='disabled')
                self.idvg_pause_btn.config(state='normal')
                self.idvg_stop_btn.config(state='normal')
                self.status_var.set("ID-VG measurement started")
                self.show_plot_window()
            else:
                messagebox.showerror("Error", message)
                
        except ValueError as e:
            messagebox.showerror("Parameter Error", f"Invalid parameter: {str(e)}")
            
    def pause_measurement(self):
        """Pause current measurement."""
        if self.measurement_ctrl.is_paused:
            self.measurement_ctrl.resume_measurement()
            self.idvd_pause_btn.config(text="Pause")
            self.idvg_pause_btn.config(text="Pause")
            self.status_var.set("Measurement resumed")
        else:
            self.measurement_ctrl.pause_measurement()
            self.idvd_pause_btn.config(text="Resume")
            self.idvg_pause_btn.config(text="Resume")
            self.status_var.set("Measurement paused")
            
    def stop_measurement(self):
        """Stop current measurement."""
        self.measurement_ctrl.stop_measurement()
        self.reset_measurement_buttons()
        self.status_var.set("Measurement stopped")
        
    def reset_measurement_buttons(self):
        """Reset measurement control buttons."""
        self.idvd_start_btn.config(state='normal')
        self.idvd_pause_btn.config(state='disabled', text="Pause")
        self.idvd_stop_btn.config(state='disabled')
        self.idvd_progress.config(value=0)
        
        self.idvg_start_btn.config(state='normal')
        self.idvg_pause_btn.config(state='disabled', text="Pause")
        self.idvg_stop_btn.config(state='disabled')
        self.idvg_progress.config(value=0)
        
        # Reset live indicators
        self.reset_live_indicators()
        
    def monitor_data_queue(self):
        """Monitor data queue for updates from measurement thread."""
        try:
            while True:
                message_type, data = self.data_queue.get_nowait()
                
                if message_type == 'data':
                    self.update_plots(data)
                    self.update_current_values(data)
                    self.update_live_indicators(data)
                    self.idvd_progress.config(value=data.get('progress', 0))
                    self.idvg_progress.config(value=data.get('progress', 0))
                    
                elif message_type == 'error':
                    messagebox.showerror("Measurement Error", data)
                    self.reset_measurement_buttons()
                    
                elif message_type == 'complete':
                    messagebox.showinfo("Measurement Complete", data)
                    self.reset_measurement_buttons()
                    
        except queue.Empty:
            pass
            
        # Schedule next check with higher frequency for live updates
        self.root.after(self.update_interval, self.monitor_data_queue)
        
    def update_plots(self, data):
        """Update real-time plots with new data - optimized for live streaming."""
        if 'vd' in data:  # ID-VD measurement
            self.plot_data['vd'].append(data['vd'])
            self.plot_data['ids'].append(data['ids'])
            self.plot_data['ig'].append(data['ig'])
            
            # Limit data points for better performance
            if len(self.plot_data['vd']) > self.max_plot_points:
                self.plot_data['vd'] = self.plot_data['vd'][-self.max_plot_points:]
                self.plot_data['ids'] = self.plot_data['ids'][-self.max_plot_points:]
                self.plot_data['ig'] = self.plot_data['ig'][-self.max_plot_points:]
            
            # Update IDS plot with live data
            self.line1.set_data(self.plot_data['vd'], self.plot_data['ids'])
            self.ax1.relim()
            self.ax1.autoscale_view()
            self.ax1.set_xlabel("VD (V)")
            self.ax1.set_ylabel("IDS (A)")
            self.ax1.set_title(f"LIVE: IDS vs VD (VG = {data.get('vg', 0):.1f}V) - Points: {len(self.plot_data['vd'])}")
            self.ax1.grid(True, alpha=0.3)
            
            # Update IG plot with live data
            self.line2.set_data(self.plot_data['vd'], self.plot_data['ig'])
            self.ax2.relim()
            self.ax2.autoscale_view()
            self.ax2.set_xlabel("VD (V)")
            self.ax2.set_ylabel("IG (A)")
            self.ax2.set_title(f"LIVE: IG vs VD (VG = {data.get('vg', 0):.1f}V) - Points: {len(self.plot_data['vd'])}")
            self.ax2.grid(True, alpha=0.3)
            
        elif 'vg' in data:  # ID-VG measurement
            self.plot_data['vg'].append(data['vg'])
            self.plot_data['ids'].append(data['ids'])
            self.plot_data['ig'].append(data['ig'])
            
            # Limit data points for better performance
            if len(self.plot_data['vg']) > self.max_plot_points:
                self.plot_data['vg'] = self.plot_data['vg'][-self.max_plot_points:]
                self.plot_data['ids'] = self.plot_data['ids'][-self.max_plot_points:]
                self.plot_data['ig'] = self.plot_data['ig'][-self.max_plot_points:]
            
            # Update IDS plot with live data
            self.line1.set_data(self.plot_data['vg'], self.plot_data['ids'])
            self.ax1.relim()
            self.ax1.autoscale_view()
            self.ax1.set_xlabel("VG (V)")
            self.ax1.set_ylabel("IDS (A)")
            self.ax1.set_title(f"LIVE: IDS vs VG (VDS = {data.get('vds', 0):.1f}V) - Points: {len(self.plot_data['vg'])}")
            self.ax1.grid(True, alpha=0.3)
            
            # Update IG plot with live data
            self.line2.set_data(self.plot_data['vg'], self.plot_data['ig'])
            self.ax2.relim()
            self.ax2.autoscale_view()
            self.ax2.set_xlabel("VG (V)")
            self.ax2.set_ylabel("IG (A)")
            self.ax2.set_title(f"LIVE: IG vs VG (VDS = {data.get('vds', 0):.1f}V) - Points: {len(self.plot_data['vg'])}")
            self.ax2.grid(True, alpha=0.3)
        
        # Use draw_idle() instead of draw() for better performance in live updates
        try:
            self.canvas.draw_idle()
            
            # Force GUI update for smoother real-time display
            self.root.update_idletasks()
        except Exception as e:
            # If matplotlib has issues, fall back to basic draw
            try:
                self.canvas.draw()
            except:
                # If all else fails, skip this update
                pass
        
    def update_current_values(self, data):
        """Update current values display."""
        if 'vd' in data:  # ID-VD measurement
            values_text = f"VDS: {data['vd']:.3f}V, IDS: {data['ids']:.6e}A, VG: {data.get('vg', 0):.1f}V, IG: {data['ig']:.6e}A"
        elif 'vg' in data:  # ID-VG measurement
            values_text = f"VG: {data['vg']:.3f}V, IDS: {data['ids']:.6e}A, VDS: {data.get('vds', 0):.1f}V, IG: {data['ig']:.6e}A"
        else:
            values_text = "No data"
            
        self.current_values_var.set(values_text)
    
    def update_live_indicators(self, data):
        """Update live streaming indicators and status."""
        if hasattr(self, 'live_indicator'):
            self.live_indicator.config(text="[LIVE]", foreground='red')
            
        if hasattr(self, 'plot_status_var'):
            data_rate = len(self.plot_data.get('vd', []) + self.plot_data.get('vg', []))
            if 'vd' in data:
                status_text = f"Streaming ID-VD data... Points: {data_rate} | VD: {data['vd']:.3f}V | IDS: {data['ids']:.2e}A"
            elif 'vg' in data:
                status_text = f"Streaming ID-VG data... Points: {data_rate} | VG: {data['vg']:.3f}V | IDS: {data['ids']:.2e}A"
            else:
                status_text = "Processing live data..."
            
            self.plot_status_var.set(status_text)
    
    def reset_live_indicators(self):
        """Reset live indicators when measurement stops."""
        if hasattr(self, 'live_indicator'):
            self.live_indicator.config(text="[OFFLINE]", foreground='gray')
            
        if hasattr(self, 'plot_status_var'):
            self.plot_status_var.set("Measurement stopped - Ready for new data")
    
    def clear_plot_data(self):
        """Clear all plot data and reset plots for new measurement."""
        self.plot_data = {'vd': [], 'ids': [], 'ig': [], 'vg': []}
        
        try:
            if hasattr(self, 'line1') and hasattr(self, 'line2'):
                # Clear plot lines
                self.line1.set_data([], [])
                self.line2.set_data([], [])
                
                # Reset plot titles
                self.ax1.set_title("Drain Current - Waiting for data...", fontsize=12)
                self.ax2.set_title("Gate Current - Waiting for data...", fontsize=12)
                
                # Clear axes
                self.ax1.clear()
                self.ax2.clear()
                
                # Recreate plot lines with styling
                self.line1, = self.ax1.plot([], [], 'b-o', markersize=3, linewidth=2, alpha=0.8)
                self.line2, = self.ax2.plot([], [], 'r-o', markersize=3, linewidth=2, alpha=0.8)
                
                # Restore grid and background
                for ax in [self.ax1, self.ax2]:
                    ax.grid(True, alpha=0.3)
                    ax.set_facecolor('#f8f9fa')
                
                # Set labels
                self.ax1.set_xlabel("Voltage (V)")
                self.ax1.set_ylabel("IDS (A)")
                self.ax2.set_xlabel("Voltage (V)")
                self.ax2.set_ylabel("IG (A)")
                
                # Redraw canvas with error handling
                try:
                    self.canvas.draw_idle()
                except:
                    self.canvas.draw()
        except Exception as e:
            print(f"Warning: Could not clear plots: {e}")
        
    def on_closing(self):
        """Handle application closing."""
        if self.measurement_ctrl.is_measuring:
            if messagebox.askokcancel("Quit", "Measurement in progress. Stop measurement and quit?"):
                self.measurement_ctrl.stop_measurement()
                time.sleep(0.5)  # Allow measurement to stop
            else:
                return
                
        self.instrument_ctrl.disconnect()
        self.root.destroy()


def main():
    """Main application entry point."""
    root = tk.Tk()
    app = FETMeasurementGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()