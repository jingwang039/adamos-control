
import sys
import traceback
import serial 
import time
import log_maker

class lakeshore_224:
    def __init__(self, port, serial_nr, logger):
        self.logger = logger
        self.ser = serial.Serial(
            port            = port,
            baudrate        = 57600,
            timeout         = 5.0,
            parity          = serial.PARITY_ODD,
            stopbits        = serial.STOPBITS_ONE,
            bytesize        = serial.SEVENBITS)
        self.device_serial  = serial_nr
        
        self.check_id()
        self.turn_off_leds()


    #############################################################################
	#############################################################################
	# Main Commands
	#############################################################################
	#############################################################################

    def check_id(self):
        self.logger.debug("* check_id command entered (Lakeshore_Temperature_Monitor_224). *")
        self.ser.write(b"*IDN?\n")
        self.ser.flush()
        # The actual output of IDN? is ['LSCI', 'MODEL224', 'LSA21X5/OCD21X5/OCC21X5', '1.1\r\n']
        self.out = self.ser.readline().decode("ascii").split(",")
        if len(self.out) >= 3 and self.device_serial in self.out[2]:
            self.logger.info("Lakeshore Temperature Monitor 224 is connected.")
        else:
            self.logger.error("Lakeshore Temperature Monitor 224 is not connected!")


    def close_connection(self):
        self.logger.debug("* close_connection command entered (Lakeshore_Temperature_Monitor_224). *")
        self.ser.close()
        self.logger.debug("Lakeshore Temperature Monitor 224 connection is closed.")



    #############################################################################
	#############################################################################
	# Get Measurements
	#############################################################################
	#############################################################################
        
    def temperature_celsius(self):
        # Celcius Reading Querry. The "0" is to read all input values
        self.ser.write(b"CRDG? 0\n") 
        self.ser.flush()
        self.out = self.ser.readline().decode("ascii").split(",")
        try:
            if not str(self.out) == "":
                pass
            temperatures = [float(value) for value in self.out]
            return {"t_c2": temperatures[3],    #C2=3
                    "t_c3": temperatures[4],    #C3=4
                    "t_c4": temperatures[5],    #C4=5
                    "t_c5": temperatures[6],    #C5=6
                    "t_d1": temperatures[7],    #D1=7
                    "t_d2": temperatures[8],    #D2=8
                    "t_d3": temperatures[9],    #D3=9
                    "t_d4": temperatures[10],   #D4=10
                    "t_d5": temperatures[11]}   #D5=11
        except:
            self.logger.error("Could not read the temperatures from Lakeshore Temperature Monitor 224!")
            raise

    #############################################################################
	#############################################################################
	# Other functions
	#############################################################################
	#############################################################################

    
    def turn_off_leds(self):
        self.logger.debug("* turn_off_leds command entered (Lakeshore_Temperature_Monitor_224). *")
        self.ser.write(b"LEDS 0\n")
        self.ser.flush()
        # Check if LEDs are actually turned off by quering the instrument
        self.ser.write(b"LEDS?\n")
        self.ser.flush()
        self.out = self.ser.readline().decode("ascii").split(",")
        if  "0\r\n" in self.out:
            self.logger.debug("Front panel LEDs of Lakeshore Temperature Monitor 224 are turned OFF.")
        else:
            self.logger.error("Could not turn OFF front panel LEDs of Lakeshore Temperature Monitor 224!")


    def turn_on_leds(self):
        self.logger.debug("* turn_off_leds command entered (Lakeshore_Temperature_Monitor_224). *")
        self.ser.write(b"LEDS 1\n")
        self.ser.flush()
        # Check if LEDs are actually turned off by quering the instrument
        self.ser.write(b"LEDS?\n")
        self.ser.flush()
        if  "1\r\n" in self.out:
            self.logger.debug("Front panel LEDs of Lakeshore Temperature Monitor 224 are turned ON.")
        else:
            self.logger.error("Could not turn ON front panel LEDs of Lakeshore Temperature Monitor 224!")