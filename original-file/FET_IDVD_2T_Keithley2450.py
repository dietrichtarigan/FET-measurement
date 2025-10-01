#=== Define package ===#
import time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import csv
import pyvisa
import os

#=== Open VISA ===# 
rm = pyvisa.ResourceManager()


#=== Define GPIB Address ===#
GPIBAddress_1 = 'GPIB0::24::INSTR' #Drain -Source
GPIBAddress_2 = 'GPIB0::18::INSTR' #Gate - source

keithley_VDS = rm.open_resource(GPIBAddress_1)
keithley_VG = rm.open_resource(GPIBAddress_2)

#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#  MEASUREMENT PARAMETER  #--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

#==== Directory and Filename ====#
save_dir = "D:/2_Work/Research/Experiments/5_TMDs and device/Data/IV/20250909"
file_name = "20250909_MoS2_D2_60um-Ag-4"

#******* (Fixed VG, sweeping VD) *******# 
#==== VG parameter =====
vg_from = 0 #in V
vg_to = 10  #in V
vg_step = 5 #in V
vg_delay = 0.5  # in seconds between steps
vg_current_limit = 0.1 #in A 

#==== VDS parameter =====
vds_from = -1 #in V
vds_to = 1  #in V
vds_step = 0.05 #in V
vds_delay = 0.2  # in seconds between steps
vds_current_limit = 0.1 #in A 

#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#


#=== set timeout, termination characters ===#
keithley_VDS.timeout = 5000  # in ms
keithley_VG.timeout = 5000  # in ms
keithley_VDS.write_termination = '\n'
keithley_VG.write_termination = '\n'
keithley_VDS.read_termination = '\n'
keithley_VG.read_termination = '\n'


#=== Instrument Initialization ===#
keithley_VDS.write('*RST')
keithley_VDS.write(':SOUR:FUNC VOLT')
keithley_VDS.write(':SOUR:VOLT:DEL 0')
keithley_VDS.write(':SENS:FUNC "CURR"')
keithley_VDS.write('SENS:CURR:NPLC 1')
keithley_VDS.write(f':SOUR:VOLT:ILIM:LEV {vds_current_limit}')
keithley_VDS.write(':OUTP ON')

keithley_VG.write('*RST')
keithley_VG.write(':SOUR:FUNC VOLT')
keithley_VG.write(':SOUR:VOLT:DEL 0')
keithley_VG.write(':SENS:FUNC "CURR"')
keithley_VG.write('SENS:CURR:NPLC 1')
keithley_VG.write(f':SOUR:VOLT:ILIM:LEV {vg_current_limit}')
keithley_VG.write(':OUTP ON')


#=== Directory and CSV file name ===#
csv_filename = os.path.join(save_dir, file_name + "-IDVD.csv")

if not os.path.exists(csv_filename):
    df = pd.DataFrame(columns=["VD (V)", "IDS (A)", "IG (A)"])
    df.to_csv(csv_filename, index=False)


#=== Setup Plot / activate interactive mode ===#
plt.ion()

fig1, ax1 = plt.subplots()
fig2, ax2 = plt.subplots()
x_data, y1_data, y2_data = [], [], []

line1, = ax1.plot(x_data, y1_data, marker="o")
line2, = ax2.plot(x_data, y1_data, marker="o")
ax1.set_xlabel("VD")
ax1.set_ylabel("ID")
ax1.set_title("ID-VD output curve")
ax2.set_xlabel("VD")
ax2.set_ylabel("IG")
ax2.set_title("IG-VD (Leak current))")



#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--# MEASUREMENT PROCESS  #--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#
try:
    # === Set VG ===#
    vg_set_from = 0
    vg_set_to = 0
 
    vg_measure = np.linspace(vg_from, vg_to, int((vg_to - vg_from)/vg_step) + 1)
    print(vg_measure)
    
    for i in vg_measure:

        vg_set_to = i
        vg_set_range = (vg_set_to - vg_set_from)/10  

        if vg_set_to != 0:  
            vg_set = np.linspace(vg_set_from, vg_set_to, int((vg_set_to - vg_set_from)/vg_set_range) + 1)

            #====== Interloop VG =====#
            for j in vg_set:
                keithley_VG.write(f":SOUR:VOLT {j};")
                keithley_VG.write(":READ?;")
                init_resp = keithley_VG.read() 

                print(f"{j}; {init_resp}" )

                time.sleep(vg_delay)  
        else:
            vg_0 = 0
            keithley_VG.write(f":SOUR:VOLT {vg_0};")
            keithley_VG.write(":READ?;")
            init_resp = keithley_VG.read() 

            print(f"0.0; {init_resp}" )
        
        print(f"VG = {vg_set_to}")
        time.sleep(1)

        #=== Append to CSV ===#
        new_row = pd.DataFrame([[vg_set_to, '', '']], columns=["VD (V)", "IDS (A)", "IG (A)"])
        new_row.to_csv(csv_filename, mode='a', header=False, index=False)

        #=== Start VD sweeping ===#
              
        if vds_from != 0:
            vds_init_step = vds_from/10
            vds_init = np.linspace(0, vds_from, int((vds_from - 0)/vds_init_step) + 1)
            for k in vds_init:
                keithley_VDS.write(f":SOUR:VOLT {k}")
                keithley_VDS.write(":READ?")
                response_Ids = keithley_VDS.read()

                print(f"{k}; {response_Ids}")

                time.sleep(vds_delay)
        else:
            keithley_VDS.write(f":SOUR:VOLT 0")

        vds_sweep_for = np.linspace(vds_from, vds_to, int((vds_to - vds_from)/vds_step) + 1)
        
        for k in vds_sweep_for:
            keithley_VDS.write(f":SOUR:VOLT {k}")
            keithley_VDS.write(":READ?")
            response_Ids = keithley_VDS.read()

            keithley_VG.write(":READ?")
            response_Ig = keithley_VG.read() 
                    
            vds_meas = k
            ids_meas = float(response_Ids)
            ig_meas = float(response_Ig)
                    
            x_data.append(vds_meas)
            y1_data.append(ids_meas)
            y2_data.append(ig_meas)
                    
            #=== Update plot ===#
            line1.set_data(x_data, y1_data)
            ax1.relim()
            ax1.autoscale_view()
            fig1.canvas.draw()
            fig1.canvas.flush_events()
            line2.set_data(x_data, y2_data)
            ax2.relim()
            ax2.autoscale_view()
            fig2.canvas.draw()
            fig2.canvas.flush_events()

            print(f"{k}; {response_Ids}")

            #=== Append to CSV ===#
            new_row = pd.DataFrame([[vds_meas, ids_meas, ig_meas]], columns=["VD (V)", "IDS (A)", "IG (A)"])
            new_row.to_csv(csv_filename, mode='a', header=False, index=False)

            time.sleep(vds_delay)
        
        for k in reversed(vds_sweep_for):
            keithley_VDS.write(f":SOUR:VOLT {k}")
            keithley_VDS.write(":READ?")
            response_Ids = keithley_VDS.read()

            keithley_VG.write(":READ?")
            response_Ig = keithley_VG.read() 
                    
            vds_meas = k
            ids_meas = float(response_Ids)
            ig_meas = float(response_Ig)
                    
            x_data.append(vds_meas)
            y1_data.append(ids_meas)
            y2_data.append(ig_meas)
                    
            #=== Update plot ===#
            line1.set_data(x_data, y1_data)
            ax1.relim()
            ax1.autoscale_view()
            fig1.canvas.draw()
            fig1.canvas.flush_events()
            line2.set_data(x_data, y2_data)
            ax2.relim()
            ax2.autoscale_view()
            fig2.canvas.draw()
            fig2.canvas.flush_events()

            print(f"{k}; {response_Ids}")

            #=== Append to CSV ===#
            new_row = pd.DataFrame([[vds_meas, ids_meas, ig_meas]], columns=["VD (V)", "IDS (A)", "IG (A)"])
            new_row.to_csv(csv_filename, mode='a', header=False, index=False)

            time.sleep(vds_delay)
        
        #======= Return VD to 0 V ======#
        keithley_VDS.write(f":SOUR:VOLT 0")

        time.sleep(vg_delay)
        vg_set_from = vg_set_to
    
    plt.show()


#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#



except KeyboardInterrupt:
    print("\nMeasurement interrupted by user.")

finally:
    print("Turning off output and resetting Keithley...")
    try:
        keithley_VDS.write(":OUTP OFF")
        keithley_VG.write(":OUTP OFF")
        keithley_VDS.write("*RST")
        keithley_VG.write("*RST")
    except Exception as e:
        print(f"Error during shutdown: {e}")
    keithley_VDS.close()
    keithley_VG.close()
    rm.close()
    plt.ioff()
    print("Cleanup done.")
