#=== Define package ===#
import time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import csv
import pyvisa
import  os


#=== Open VISA ===#
rm = pyvisa.ResourceManager()


#=== Define GPIB Address ===#
GPIBAddress_1 = 'GPIB0::24::INSTR'
GPIBAddress_2 = 'GPIB0::18::INSTR'

keithley_VDS = rm.open_resource(GPIBAddress_1)
keithley_VG = rm.open_resource(GPIBAddress_2)


#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#  MEASUREMENT PARAMETER  #--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

#==== Directory and Filename ====#
save_dir = "D:/2_Work/Research/Experiments/5_TMDs and device/Data/IV/20250909"
file_name = "20250909_MoS2_D2_60um-Ag-4"

#******* (Fixed VD, sweeping VG) *******#
#==== VDS parameter =====#
vds_from = 0.2  #in V
vds_to = 0.4 #in V
vds_step = 0.2 #in V
vds_delay = 0.5  # in seconds between steps
vds_current_limit = 0.5 #in A 

#==== VG parameter =====#
vg_from = -10 #in V
vg_to = 10  #in V
vg_step = 0.5 #in V
vg_delay = 0.2  # in seconds between steps
vg_current_limit = 0.5 #in A 

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


#=== Creating directory and CSV file ===#

csv_filename = os.path.join(save_dir, file_name + "-IDVG.csv")
if not os.path.exists(csv_filename):
    df = pd.DataFrame(columns=["VG (V)", "IDS (A)", "IG (A)"])
    df.to_csv(csv_filename, index=False)


#=== Setup Plot / activate interactive mode ===#
plt.ion()

fig1, ax1 = plt.subplots()
fig2, ax2 = plt.subplots()
x_data, y1_data, y2_data = [], [], []

line1, = ax1.plot(x_data, y1_data, marker="o")
line2, = ax2.plot(x_data, y1_data, marker="o")
ax1.set_xlabel("VG")
ax1.set_ylabel("ID")
ax1.set_title("ID-VG transfer curve")
ax2.set_xlabel("VG")
ax2.set_ylabel("IG")
ax2.set_title("IG-VG (Leak current))")



#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--# MEASUREMENT PROCESS  #--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#
try:
    # === Set VD ===#
    vds_set_from = 0
    vds_set_to = 0
 
    vd_measure = np.linspace(vds_from, vds_to, int((vds_to - vds_from)/vds_step) + 1)
    print(vd_measure)
    
    for i in vd_measure:
        vds_set_to = i
        vds_set_range = (vds_set_to - vds_set_from)/10
        vds_set = np.linspace(vds_set_from, vds_set_to, int((vds_set_to - vds_set_from)/vds_set_range) + 1)    

        if vds_set_to != 0:
            #===== Interloop VD =====#
            for j in vds_set:
                keithley_VDS.write(f":SOUR:VOLT {j};")
                keithley_VDS.write(":READ?;")
                init_resp = keithley_VDS.read() 

                print(f"{j}; {init_resp}" )

                time.sleep(vds_delay)
        else:
            vds_0 = 0
            keithley_VDS.write(f":SOUR:VOLT {vds_0};")
            keithley_VDS.write(":READ?;")
            init_resp = keithley_VDS.read() 

            print(f"0.0; {init_resp}")

        print(f"VDS = {vds_set_to}")
        time.sleep(0.5)

        #==== Append to CSV ====#
        new_row = pd.DataFrame([[vds_set_to, '', '']], columns=["VG (V)", "IDS (A)", "IG (A)"])
        new_row.to_csv(csv_filename, mode='a', header=False, index=False)

       
       #=== Start VG sweeping ===#
        if vg_from != 0:
            vg_init_step = vg_from/10
            vg_init = np.linspace(0, vg_from, int((vg_from - 0)/vg_init_step) + 1)
            for k in vg_init:
                keithley_VG.write(f":SOUR:VOLT {k}")
                keithley_VG.write(":READ?")
                response_Ig = keithley_VG.read()

                print(f"{k}; {response_Ig}")

                time.sleep(vg_delay)
        else:
            keithley_VG.write(f":SOUR:VOLT 0")

        
        vgs_sweep_for = np.linspace(vg_from, vg_to , int((vg_to - vg_from)/vg_step) + 1)
        
        for k in vgs_sweep_for:
            keithley_VG.write(f":SOUR:VOLT {k}")
            keithley_VG.write(":READ?")
            response_Ig = keithley_VG.read()

            keithley_VDS.write(":READ?")
            response_Ids = keithley_VDS.read() 
                    
            vg_meas = k
            ids_meas = float(response_Ids)
            ig_meas = float(response_Ig)
                    
            x_data.append(vg_meas)
            y1_data.append(ids_meas)
            y2_data.append(ig_meas)
                    
            #==== Update plot ====#
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

            #==== Append to CSV ====#
            new_row = pd.DataFrame([[vg_meas, ids_meas, ig_meas]], columns=["VG (V)", "IDS (A)", "IG (A)"])
            new_row.to_csv(csv_filename, mode='a', header=False, index=False)

            time.sleep(vg_delay)
        
        for k in reversed(vgs_sweep_for):
            keithley_VG.write(f":SOUR:VOLT {k}")
            keithley_VG.write(":READ?")
            response_Ig = keithley_VG.read()

            keithley_VDS.write(":READ?")
            response_Ids = keithley_VDS.read() 
                    
            vg_meas = k
            ids_meas = float(response_Ids)
            ig_meas = float(response_Ig)
                    
            x_data.append(vg_meas)
            y1_data.append(ids_meas)
            y2_data.append(ig_meas)
                    
            #==== Update plot ====#
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

            #==== Append to CSV ====#
            new_row = pd.DataFrame([[vg_meas, ids_meas, ig_meas]], columns=["VG (V)", "IDS (A)", "IG (A)"])
            new_row.to_csv(csv_filename, mode='a', header=False, index=False)

            time.sleep(vg_delay)
        
        #======= Return VG to 0 V ======#
        keithley_VG.write(f":SOUR:VOLT 0")

        time.sleep(vds_delay)
        vds_set_from = vds_set_to
    
    plt.show()


#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#


except KeyboardInterrupt:
    print("\nMeasurement interrupted by user.")

finally:
    print("Turning off output and resetting Keithley...")
    try:
        keithley_VDS.write(":OUTP OFF")
        keithley_VG.write(":OUTP OFF")
        keithley_VDS.write("*RST;")
        keithley_VG.write("*RST;")
    except Exception as e:
        print(f"Error during shutdown: {e}")
    keithley_VDS.close()
    keithley_VG.close()
    rm.close()
    plt.ioff()
    print("Cleanup done.")
