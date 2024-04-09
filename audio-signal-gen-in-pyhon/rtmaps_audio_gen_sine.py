# ---------------- TEMPLATE ---------------------------------------
# This is a template to help you start writing PythonBridge code  -
# -----------------------------------------------------------------

from math import radians
import rtmaps.core as rt
import rtmaps.types
from rtmaps.base_component import BaseComponent  # base class

import numpy as np
import math

# Python class that will be called from RTMaps.
class rtmaps_python(BaseComponent):
    
    # Constructor has to call the BaseComponent parent class
    def __init__(self):
        BaseComponent.__init__(self)  # call base class constructor

    # Dynamic is called frequently:
    # - When loading the diagram
    # - When connecting or disconnecting a wire
    # Here you create your inputs, outputs and properties
    def Dynamic(self):
        # Define the output. The type is set to AUTO which means that the output will be typed automatically.
        # You don’t need to set the buffer_size, in that case it will be set automatically.
        self.add_output("audio_out", rtmaps.types.FLOAT32)
        self.add_property("audio_signal_frequency", 440.0)
        self.add_property("volume_percent", 50)
        
# Birth() will be called once at diagram execution startup
    def Birth(self):
        self.sample_rate = 44100 # Audio signal sampled at 44.1 kHz
        self.nb_channels = 2 # Stereo
        self.output_rate = 10 # Let's output 10 audio packets per second from our component...
        self.output_period = 100000 #... that means 100ms for each packet duration
        self.samples_per_packet = 4410 # Basically sample_rate / output_rate, but let's make sure we have a round value here.

        # Alloc our output buffers
        self.packet_size = self.samples_per_packet * self.nb_channels
        self.outputs[0].alloc_output_buffer(self.packet_size)

        # Build a lookup table for our waveform. Here a simple sine signal (that will prevent us from calling math.sin for each sample)
        self.sine_table = np.zeros(36000,dtype=np.float32)
        for i in range(36000):
            self.sine_table[i] = np.float32(math.sin(radians(i/100.0)))

        self.freq = 0 # Temp value, to be updated in first Core
        self.lut_increment = 0 # Temp value, to be updated in first Core
        
        self.count = 0        
        self.appointment = rt.current_time()
       

# Core() is called every time you have a new inputs available, depending on your chosen reading policy
    def Core(self):
        volume = self.get_property("volume_percent") / 100
        
        #This defines the increment to browse the LUT between subsequent audio samples
        #depending on the requested audio frequency.
        if (self.freq != self.get_property("audio_signal_frequency")):
            self.freq = self.get_property("audio_signal_frequency")
            self.lut_increment = 36000 * self.freq / self.sample_rate

        out = rtmaps.types.Ioelt()
        out.data = np.zeros(self.packet_size ,dtype=np.float32) # We need a float32 array.
        
        # Let's override our data sample "type" field by adding the FrequencyFlag and the MiscFlag.
        # Those flags will tell downstream components reading the data that the frequency and misc1, misc2 and misc3 fields are valid
        out.type = rt.DataTypes.CTypes.Float32 | rt.DataTypes.CTypes.FrequencyFlag | rt.DataTypes.CTypes.MiscFlag 
        out.frequency = self.sample_rate * 1000 # In mHz
        out.misc1 = self.nb_channels # Nb channels
        out.misc2 = 16  # Sampling bits. (Since we output float32s that we generate ourselves, 
                        # this doesn't make much sense. But 16 would be a common value for 
                        # audio signals with data type Stream8 and raw audio data in the packets.)
        out.misc3 = 0

        # This is where we fill our audio packet
        current_pos = 0
        for i in range(self.samples_per_packet):
            for j in range (self.nb_channels):
                out.data[current_pos] = self.sine_table[np.int(self.count)] * volume #Volume factor (1.0 = 100%)
                current_pos += 1
            self.count += self.lut_increment
            if (self.count >= 36000): # We've reached the end of our LUT. Let's start over.
                self.count -= 36000

        # Add common meta-data (vector size and timestamp)
        out.vector_size = self.packet_size 
        out.ts          = self.appointment  # The ioelt carries a timestamp that corresponds to the first sample in the packet.
                                            # Knowing the frequency of the signal (in out.frequency), and the number of channels (in out.misc1) 
                                            # any downstream component can compute the sampling time of each audio sample in the packet.
        
        # Publish our packet
        self.write("audio_out", out) 

        # Wait until next packet generation time
        self.appointment += self.output_period
        rt.wait(self.appointment)

# Death() will be called once at diagram execution shutdown
    def Death(self):
        pass
